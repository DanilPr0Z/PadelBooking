from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
import re
import random
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
from PIL import Image
import io
from django.conf import settings


class UserProfileManager(models.Manager):
    def normalize_phone(self, phone):
        """Нормализует номер телефона для сравнения"""
        if not phone:
            return None

        # Убираем все нецифровые символы
        digits = re.sub(r'\D', '', str(phone))

        if not digits:
            return None

        # Нормализуем российский номер
        if len(digits) == 10 and digits.startswith('9'):
            digits = '7' + digits
        elif len(digits) == 11 and digits.startswith('8'):
            digits = '7' + digits[1:]
        elif len(digits) == 10:
            digits = '7' + digits

        # Должно быть 11 цифр для российского номера
        if len(digits) != 11:
            return None

        return '+' + digits

    def get_user_by_phone(self, phone):
        """Найти пользователя по номеру телефона"""
        # Нормализуем номер
        normalized_phone = self.normalize_phone(phone)
        if not normalized_phone:
            return None

        # Ищем профиль с таким номером
        try:
            profile = UserProfile.objects.get(phone=normalized_phone)
            return profile.user
        except UserProfile.DoesNotExist:
            # Пробуем другие форматы
            phone_digits = normalized_phone[1:]  # Убираем +

            # Формат без + в начале
            try:
                profile = UserProfile.objects.get(phone=phone_digits)
                return profile.user
            except UserProfile.DoesNotExist:
                pass

            # Формат с 8 в начале
            try:
                profile = UserProfile.objects.get(phone='8' + phone_digits[1:])
                return profile.user
            except UserProfile.DoesNotExist:
                pass

        return None


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Валидатор для номера телефона
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Номер телефона должен быть в формате: '+79123456789'"
    )

    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        unique=True,
        verbose_name='Номер телефона'
    )

    phone_verified = models.BooleanField(default=False, verbose_name='Телефон подтвержден')
    verification_code = models.CharField(max_length=6, blank=True, null=True)

    birth_date = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')

    # Дополнительные поля
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Аватар')
    preferences = models.JSONField(default=dict, blank=True, verbose_name='Предпочтения')

    objects = UserProfileManager()

    class Meta:
        indexes = [
            models.Index(fields=['phone']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['phone'],
                name='unique_userprofile_phone'
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.phone}"

    def clean(self):
        """Проверка перед сохранением - строгая проверка уникальности"""
        super().clean()

        if not self.phone:
            raise ValidationError({'phone': 'Номер телефона обязателен'})

        # Нормализуем телефон для проверки
        normalized = self.__class__.objects.normalize_phone(self.phone)
        if not normalized:
            raise ValidationError({'phone': 'Неверный формат номера телефона'})

        # Проверяем уникальность
        qs = UserProfile.objects.filter(phone=normalized)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.exists():
            existing_users = [p.user.username for p in qs]
            raise ValidationError({
                'phone': f'Номер телефона {normalized} уже используется пользователями: {", ".join(existing_users)}'
            })

        # Устанавливаем нормализованный номер
        self.phone = normalized

    def save(self, *args, **kwargs):
        """Сохраняем с атомарной проверкой уникальности"""
        # Всегда вызываем clean для валидации
        self.full_clean()

        # Сохраняем с блокировкой транзакции
        try:
            with transaction.atomic():
                super().save(*args, **kwargs)
        except IntegrityError as e:
            # Ловим ошибку уникальности из базы данных
            if 'unique' in str(e).lower() or 'phone' in str(e).lower():
                # Пытаемся найти, кто уже использует этот телефон
                try:
                    existing = UserProfile.objects.get(phone=self.phone)
                    raise ValidationError({
                        'phone': f'Номер телефона {self.phone} уже используется пользователем {existing.user.username}'
                    })
                except UserProfile.DoesNotExist:
                    raise ValidationError({
                        'phone': f'Номер телефона {self.phone} уже зарегистрирован'
                    })
            raise

    def generate_verification_code(self):
        """Генерация кода подтверждения телефона"""
        import random
        self.verification_code = f"{random.randint(100000, 999999)}"
        self.save()
        print(
            f"ГЕНЕРАЦИЯ КОДА: Для пользователя {self.user.username}, телефон {self.phone}, код: {self.verification_code}")
        return self.verification_code

    def verify_phone(self, code):
        """Подтверждение телефона"""
        print(f"ПРОВЕРКА КОДА ДЛЯ {self.user.username}:")
        print(f"  Введенный код: {code}")
        print(f"  Код в БД: {self.verification_code}")
        print(f"  Тип введенного: {type(code)}")
        print(f"  Тип в БД: {type(self.verification_code)}")
        print(f"  Совпадение: {str(self.verification_code) == str(code)}")

        if self.verification_code and str(self.verification_code) == str(code):
            self.phone_verified = True
            self.verification_code = None
            self.save()
            print(f"  ✅ ТЕЛЕФОН ПОДТВЕРЖДЕН!")
            return True

        print(f"  ❌ НЕВЕРНЫЙ КОД!")
        return False

    def save_avatar(self, image_file):
        """Сохранение аватарки с обработкой"""
        try:
            # Проверяем расширение файла
            filename = image_file.name.lower()
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            if not any(filename.endswith(ext) for ext in allowed_extensions):
                raise ValidationError('Недопустимый формат файла. Разрешены: JPG, PNG, GIF, WebP')

            # Проверяем размер файла
            max_size = 5 * 1024 * 1024  # 5MB
            if image_file.size > max_size:
                raise ValidationError(f'Файл слишком большой. Максимальный размер: {max_size // 1024 // 1024}MB')

            # Удаляем старую аватарку если есть
            if self.avatar:
                old_path = self.avatar.path
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Генерируем уникальное имя файла
            import uuid
            ext = os.path.splitext(filename)[1]
            new_filename = f'avatar_{self.user.id}_{uuid.uuid4().hex[:8]}{ext}'

            # Обрабатываем изображение
            img = Image.open(image_file)

            # Конвертируем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Создаем квадратное изображение
            width, height = img.size
            min_size = min(width, height)

            # Обрезаем до квадрата
            left = (width - min_size) // 2
            top = (height - min_size) // 2
            right = (width + min_size) // 2
            bottom = (height + min_size) // 2
            img = img.crop((left, top, right, bottom))

            # Изменяем размер до 300x300
            img = img.resize((300, 300), Image.Resampling.LANCZOS)

            # Сохраняем аватарку
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            # Сохраняем в поле модели
            self.avatar.save(new_filename, ContentFile(buffer.read()), save=True)

            return True

        except Exception as e:
            print(f"Ошибка при сохранении аватарки: {str(e)}")
            raise ValidationError(f'Ошибка при обработке изображения: {str(e)}')

    def get_avatar_url(self):
        """Получение URL аватарки"""
        if self.avatar:
            return self.avatar.url
        return None

    def delete_avatar(self):
        """Удаление аватарки"""
        if self.avatar:
            try:
                # Получаем путь к файлу
                if hasattr(self.avatar, 'path'):
                    path = self.avatar.path
                    if os.path.exists(path):
                        os.remove(path)

                # Удаляем поле из модели
                self.avatar.delete(save=False)
                self.avatar = None
                self.save()
                return True
            except Exception as e:
                print(f"Ошибка при удалении аватарки: {str(e)}")
                return False
        return False


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Создать профиль при создании пользователя"""
    # Пропускаем создание профиля, если он уже создается через форму регистрации
    if created and not getattr(instance, '_creating_profile_via_form', False):
        try:
            with transaction.atomic():
                import time
                # Генерируем уникальный временный телефон
                timestamp = int(time.time() * 1000) % 1000000
                base_phone = f'+7980{timestamp:06d}'

                # Убеждаемся в уникальности
                phone = base_phone
                counter = 1
                while UserProfile.objects.filter(phone=phone).exists() and counter < 100:
                    phone = f'+7980{(timestamp + counter) % 1000000:06d}'
                    counter += 1

                if counter >= 100:
                    # Если не удалось найти уникальный, генерируем случайный
                    import random
                    phone = f'+7980{random.randint(1000000, 9999999)}'

                UserProfile.objects.create(user=instance, phone=phone)
        except Exception as e:
            # Если ошибка, логируем но не падаем
            import sys
            print(f"Ошибка создания профиля для {instance.username}: {e}", file=sys.stderr)