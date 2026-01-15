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
from django.utils import timezone


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
    verification_code = models.CharField(max_length=6, blank=True, null=True, verbose_name='Код подтверждения телефона')

    # Email verification fields
    email_verified = models.BooleanField(default=False, verbose_name='Email подтвержден')
    email_verification_code = models.CharField(max_length=6, blank=True, null=True, verbose_name='Код подтверждения email')
    email_pending = models.EmailField(
        blank=True,
        null=True,
        verbose_name='Email в ожидании подтверждения',
        help_text='Новый email, ожидающий подтверждения'
    )

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
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        if full_name:
            return f"{full_name} - {self.phone}"
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

    def generate_email_verification_code(self):
        """Генерация кода подтверждения email"""
        import random
        self.email_verification_code = f"{random.randint(100000, 999999)}"
        self.save()
        print(
            f"ГЕНЕРАЦИЯ КОДА EMAIL: Для пользователя {self.user.username}, email {self.user.email}, код: {self.email_verification_code}")
        return self.email_verification_code

    def verify_email(self, code):
        """Подтверждение email"""
        print(f"ПРОВЕРКА КОДА EMAIL ДЛЯ {self.user.username}:")
        print(f"  Введенный код: {code}")
        print(f"  Код в БД: {self.email_verification_code}")
        print(f"  Совпадение: {str(self.email_verification_code) == str(code)}")

        if self.email_verification_code and str(self.email_verification_code) == str(code):
            self.email_verified = True
            self.email_verification_code = None
            self.save()
            print(f"  ✅ EMAIL ПОДТВЕРЖДЕН!")
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

    def get_rating(self):
        """Получить или создать рейтинг для пользователя"""
        from .models import PlayerRating

        if not hasattr(self.user, 'rating'):
            # Создаем рейтинг по умолчанию
            rating = PlayerRating.objects.create(
                user=self.user,
                numeric_rating=1.00,
                level='D'
            )
            return rating
        return self.user.rating


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


class PlayerRating(models.Model):
    """Модель рейтинга игрока в падл-теннисе"""

    # Буквенные уровни с описанием
    RATING_LEVELS = [
        ('D', 'Уровень 1 (D): Новичок'),
        ('D+', 'Уровень 1+ (D+): Начинающий'),
        ('C-', 'Уровень 2 (C-): Начинающий / Слабый средний'),
        ('C', 'Уровень 2+ (C): Средний'),
        ('C+', 'Уровень 3 (C+): Средний / Крепкий любитель'),
        ('B-', 'Уровень 3+ (B-): Крепкий любитель'),
        ('B', 'Уровень 4 (B): Продвинутый'),
        ('B+', 'Уровень 4+ (B+): Топ-любитель'),
        ('A', 'Уровень 5/5+ (A): Кандидат/Мастер спорта'),
        ('PRO', 'Уровень 6-7 (Pro): Профессионал'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='rating',
        verbose_name='Игрок'
    )

    # Цифровой рейтинг (например: 2.75, 4.20 и т.д.)
    numeric_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.00,
        verbose_name='Числовой рейтинг',
        help_text='Значение от 1.00 до 7.00'
    )

    # Буквенный уровень (автоматически вычисляется из числового)
    level = models.CharField(
        max_length=10,
        choices=RATING_LEVELS,
        default='D',
        verbose_name='Уровень',
        editable=False  # Нельзя менять напрямую, только через numeric_rating
    )

    # Кто и когда изменил рейтинг
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ratings_updated',
        verbose_name='Кем обновлен'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    # Комментарий тренера
    coach_comment = models.TextField(
        blank=True,
        verbose_name='Комментарий тренера'
    )

    # История изменений рейтинга (JSON поле для хранения изменений)
    rating_history = models.JSONField(
        default=list,
        blank=True,
        verbose_name='История рейтинга'
    )

    class Meta:
        verbose_name = 'Рейтинг игрока'
        verbose_name_plural = 'Рейтинги игроков'
        ordering = ['-numeric_rating']

    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        display_name = full_name if full_name else self.user.username
        return f"{display_name}: {self.level} ({self.numeric_rating})"

    def calculate_level(self, rating_value=None):
        """Определяет буквенный уровень на основе числового рейтинга"""
        if rating_value is None:
            rating_value = float(self.numeric_rating)

        if 1.00 <= rating_value <= 1.50:
            return 'D'
        elif 1.60 <= rating_value <= 2.50:
            return 'D+'
        elif 2.60 <= rating_value <= 3.00:
            return 'C-'
        elif 3.10 <= rating_value <= 3.50:
            return 'C'
        elif 3.60 <= rating_value <= 4.00:
            return 'C+'
        elif 4.10 <= rating_value <= 4.50:
            return 'B-'
        elif 4.60 <= rating_value <= 5.00:
            return 'B'
        elif 5.10 <= rating_value <= 5.50:
            return 'B+'
        elif 5.60 <= rating_value <= 6.50:
            return 'A'
        elif 6.60 <= rating_value <= 7.00:
            return 'PRO'
        else:
            return 'D'  # По умолчанию

    def get_level_display_full(self):
        """Полное описание уровня"""
        for code, name in self.RATING_LEVELS:
            if code == self.level:
                return name
        return self.get_level_display()

    def save(self, *args, **kwargs):
        """Автоматически вычисляем уровень при сохранении"""
        # Преобразуем в float для сравнений
        rating_float = float(self.numeric_rating)

        # Ограничиваем значения
        if rating_float < 1.00:
            self.numeric_rating = 1.00
        elif rating_float > 7.00:
            self.numeric_rating = 7.00

        # Вычисляем уровень
        self.level = self.calculate_level(float(self.numeric_rating))

        super().save(*args, **kwargs)

    def add_to_history(self, old_rating, new_rating, updated_by, comment=''):
        """Добавляет запись в историю изменений"""
        history_entry = {
            'date': timezone.now().isoformat(),
            'old_rating': float(old_rating),
            'new_rating': float(new_rating),
            'old_level': self.calculate_level(float(old_rating)),
            'new_level': self.calculate_level(float(new_rating)),
            'updated_by': updated_by.username if updated_by else 'system',
            'updated_by_id': updated_by.id if updated_by else None,
            'comment': comment
        }

        self.rating_history.append(history_entry)

        # Ограничиваем историю последними 50 изменениями
        if len(self.rating_history) > 50:
            self.rating_history = self.rating_history[-50:]

        self.save()

    def get_progress_percentage(self):
        """Процент прогресса внутри текущего уровня"""
        rating = float(self.numeric_rating)

        # Диапазоны для каждого уровня
        ranges = {
            'D': (1.00, 1.50),
            'D+': (1.60, 2.50),
            'C-': (2.60, 3.00),
            'C': (3.10, 3.50),
            'C+': (3.60, 4.00),
            'B-': (4.10, 4.50),
            'B': (4.60, 5.00),
            'B+': (5.10, 5.50),
            'A': (5.60, 6.50),
            'PRO': (6.60, 7.00)
        }

        if self.level in ranges:
            min_val, max_val = ranges[self.level]

            # Рассчитываем прогресс
            if rating <= min_val:
                return 0
            elif rating >= max_val:
                return 100

            progress = ((rating - min_val) / (max_val - min_val)) * 100
            return max(0, min(100, progress))  # Гарантируем границы 0-100%

        return 0

    def get_range_min(self):
        """Возвращает минимальное значение для текущего уровня"""
        ranges = {
            'D': 1.00,
            'D+': 1.60,
            'C-': 2.60,
            'C': 3.10,
            'C+': 3.60,
            'B-': 4.10,
            'B': 4.60,
            'B+': 5.10,
            'A': 5.60,
            'PRO': 6.60
        }
        return float(ranges.get(self.level, 1.00))

    def get_range_max(self):
        """Возвращает максимальное значение для текущего уровня"""
        ranges = {
            'D': 1.50,
            'D+': 2.50,
            'C-': 3.00,
            'C': 3.50,
            'C+': 4.00,
            'B-': 4.50,
            'B': 5.00,
            'B+': 5.50,
            'A': 6.50,
            'PRO': 7.00
        }
        return float(ranges.get(self.level, 7.00))


class CoachProfile(models.Model):
    """Профиль тренера"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='coach_profile',
        verbose_name='Тренер'
    )
    qualifications = models.TextField(
        blank=True,
        verbose_name='Квалификация и сертификаты'
    )
    specialization = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Специализация',
        help_text='Например: начинающие, продвинутые, дети, взрослые'
    )
    experience_years = models.IntegerField(
        default=0,
        verbose_name='Опыт работы (лет)'
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Часовая ставка'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    bio = models.TextField(
        blank=True,
        verbose_name='О себе'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации как тренер'
    )
    coach_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=5.0,
        verbose_name='Рейтинг тренера'
    )
    contact_info = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Контактная информация'
    )

    class Meta:
        verbose_name = 'Профиль тренера'
        verbose_name_plural = 'Профили тренеров'

    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        display_name = full_name if full_name else self.user.username
        return f"Тренер: {display_name}"


class TrainingSession(models.Model):
    """Тренировочная сессия"""

    STATUS_CHOICES = [
        ('scheduled', 'Запланирована'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершена'),
        ('cancelled', 'Отменена'),
    ]

    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='coach_sessions',
        verbose_name='Тренер'
    )
    player = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='training_sessions',
        verbose_name='Игрок'
    )
    court = models.ForeignKey(
        'booking.Court',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Корт'
    )
    date = models.DateField(verbose_name='Дата тренировки')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        verbose_name='Статус'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Заметки тренера'
    )
    player_feedback = models.TextField(
        blank=True,
        verbose_name='Отзыв игрока'
    )
    rating_given = models.BooleanField(
        default=False,
        verbose_name='Рейтинг обновлен'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Тренировочная сессия'
        verbose_name_plural = 'Тренировочные сессии'
        ordering = ['-date', '-start_time']

    def __str__(self):
        coach_name = f"{self.coach.first_name} {self.coach.last_name}".strip() or self.coach.username
        player_name = f"{self.player.first_name} {self.player.last_name}".strip() or self.player.username
        return f"Тренировка: {coach_name} - {player_name} ({self.date})"


class Notification(models.Model):
    """Уведомления пользователей"""

    NOTIFICATION_TYPES = [
        ('registration', 'Регистрация'),
        ('phone_verification', 'Подтверждение телефона'),
        ('booking_created', 'Бронирование создано'),
        ('booking_confirmed', 'Бронирование подтверждено'),
        ('booking_cancelled', 'Бронирование отменено'),
        ('booking_reminder_24h', 'Напоминание за 24 часа'),
        ('booking_reminder_1h', 'Напоминание за 1 час'),
        ('payment_success', 'Оплата успешна'),
        ('payment_failed', 'Ошибка оплаты'),
        ('payment_pending', 'Ожидает оплаты'),
        ('rating_updated', 'Рейтинг обновлен'),
        ('booking_invitation', 'Приглашение в бронирование'),
        ('invitation_accepted', 'Приглашение принято'),
        ('invitation_declined', 'Приглашение отклонено'),
        ('partner_joined', 'Партнёр присоединился'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Пользователь'
    )
    type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        db_index=True,
        verbose_name='Тип уведомления'
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Заголовок'
    )
    message = models.TextField(verbose_name='Сообщение')
    email_sent = models.BooleanField(
        default=False,
        verbose_name='Email отправлен'
    )
    sms_sent = models.BooleanField(
        default=False,
        verbose_name='SMS отправлено'
    )
    push_sent = models.BooleanField(
        default=False,
        verbose_name='Push отправлено'
    )
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Прочитано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Дата создания'
    )
    read_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата прочтения'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные данные'
    )

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        display_name = full_name if full_name else self.user.username
        return f"{display_name} - {self.get_type_display()}"

    def mark_as_read(self):
        """Отметить уведомление как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class PlayerCoachRelationship(models.Model):
    """Связь между игроком и тренером"""

    player = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='coaches',
        verbose_name='Игрок'
    )
    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='players',
        verbose_name='Тренер'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активная связь'
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата назначения'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
    )

    class Meta:
        verbose_name = 'Связь игрок-тренер'
        verbose_name_plural = 'Связи игрок-тренер'
        unique_together = ('player', 'coach')

    def __str__(self):
        player_name = f"{self.player.first_name} {self.player.last_name}".strip() or self.player.username
        coach_name = f"{self.coach.first_name} {self.coach.last_name}".strip() or self.coach.username
        return f"{player_name} - {coach_name}"