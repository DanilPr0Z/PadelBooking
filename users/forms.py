from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from .models import UserProfile
import re
import os


class EmailUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control email-input',
            'placeholder': 'Введите email'
        })
    )

    class Meta:
        model = User
        fields = ['email']

    def clean_email(self):
        email = self.cleaned_data.get('email')

        # Проверяем уникальность email (исключая текущего пользователя)
        qs = User.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Этот email уже используется другим пользователем")

        return email


class PhoneVerificationForm(forms.Form):
    verification_code = forms.CharField(
        max_length=6,
        min_length=4,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите код из SMS',
            'maxlength': '6'
        })
    )


class AvatarUploadForm(forms.Form):
    avatar = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'avatar-upload-input',
            'accept': '.jpg,.jpeg,.png,.gif,.webp',
            'style': 'display: none;'
        })
    )

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')

        if not avatar:
            raise forms.ValidationError('Выберите файл для загрузки')

        # Проверка размера файла
        if avatar.size > 5 * 1024 * 1024:  # 5MB
            raise forms.ValidationError('Размер файла не должен превышать 5MB')

        # Проверка расширения
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        ext = os.path.splitext(avatar.name)[1].lower()
        if ext not in allowed_extensions:
            raise forms.ValidationError('Недопустимый формат файла. Разрешены: JPG, PNG, GIF, WebP')

        return avatar


class RegistrationForm(UserCreationForm):
    phone = forms.CharField(
        max_length=20,
        required=True,
        label='Номер телефона',
        widget=forms.TextInput(attrs={
            'placeholder': '+7 (999) 123-45-67',
            'class': 'form-input',
            'id': 'regPhone'
        }),
        help_text='Введите российский номер телефона (11 цифр, начинается с +7)',
        error_messages={
            'required': 'Номер телефона обязателен',
        }
    )

    class Meta:
        model = User
        fields = ['username', 'phone', 'password1', 'password2']
        help_texts = {
            'username': 'Обязательное поле. Не более 150 символов. Только буквы, цифры и @/./+/-/_',
            'password1': 'Пароль должен содержать минимум 8 символов',
        }
        error_messages = {
            'username': {
                'unique': 'Это имя пользователя уже занято',
                'required': 'Имя пользователя обязательно',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поля обязательными в HTML
        self.fields['username'].required = True
        self.fields['password1'].required = True
        self.fields['password2'].required = True

    def clean_phone(self):
        """Строгая проверка телефона с нормализацией"""
        phone = self.cleaned_data.get('phone', '').strip()

        if not phone:
            raise ValidationError('Номер телефона обязателен для заполнения')

        # Сохраняем оригинал для сообщений об ошибке
        original_phone = phone

        # Удаляем все нецифровые символы
        phone_digits = re.sub(r'\D', '', phone)

        if not phone_digits:
            raise ValidationError('Введите корректный номер телефона')

        # Проверяем длину
        if len(phone_digits) < 10:
            raise ValidationError('Номер слишком короткий. Минимум 10 цифр.')

        if len(phone_digits) > 11:
            raise ValidationError('Номер слишком длинный. Максимум 11 цифр.')

        # Нормализуем номер к формату +7XXXXXXXXXX
        if len(phone_digits) == 10 and phone_digits.startswith('9'):
            # Формат: 9123456789 -> +79123456789
            phone_digits = '7' + phone_digits
        elif len(phone_digits) == 11 and phone_digits.startswith('8'):
            # Формат: 89123456789 -> +79123456789
            phone_digits = '7' + phone_digits[1:]
        elif len(phone_digits) == 10:
            # Формат: 1234567890 -> +71234567890 (но это не российский)
            phone_digits = '7' + phone_digits
        elif len(phone_digits) == 11 and not phone_digits.startswith('7'):
            # Если 11 цифр но не начинается с 7, добавляем 7 в начало
            if phone_digits.startswith('8'):
                phone_digits = '7' + phone_digits[1:]
            else:
                phone_digits = '7' + phone_digits

        # Теперь должно быть 11 цифр и начинаться с 7
        if len(phone_digits) != 11 or not phone_digits.startswith('7'):
            raise ValidationError('Российский номер телефона должен содержать 11 цифр и начинаться с +7')

        formatted_phone = '+' + phone_digits

        # СТРОГАЯ проверка уникальности
        # 1. Проверяем точное совпадение
        if UserProfile.objects.filter(phone=formatted_phone).exists():
            existing = UserProfile.objects.get(phone=formatted_phone)
            raise ValidationError(f'Номер телефона уже используется пользователем {existing.user.username}')

        # 2. Проверяем другие форматы этого же номера
        other_formats = [
            '8' + phone_digits[1:],  # 89123456789
            phone_digits,  # 79123456789
            phone_digits[1:],  # 9123456789
            '7' + phone_digits[1:],  # 79123456789 (дубль)
        ]

        # Убираем дубликаты
        other_formats = list(set(other_formats))

        for fmt in other_formats:
            if fmt != formatted_phone and UserProfile.objects.filter(phone=fmt).exists():
                existing = UserProfile.objects.get(phone=fmt)
                raise ValidationError(
                    f'Этот номер телефона (в формате {fmt}) уже используется пользователем {existing.user.username}')

        # 3. Проверяем нормализованные версии существующих номеров
        for profile in UserProfile.objects.exclude(phone__isnull=True).exclude(phone=''):
            existing_normalized = UserProfile.objects.normalize_phone(profile.phone)
            if existing_normalized == formatted_phone:
                raise ValidationError(f'Этот номер телефона уже используется пользователем {profile.user.username}')

        return formatted_phone

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()

        if not username:
            raise ValidationError('Имя пользователя обязательно')

        if len(username) < 3:
            raise ValidationError('Имя пользователя должно содержать минимум 3 символа')

        if len(username) > 150:
            raise ValidationError('Имя пользователя не должно превышать 150 символов')

        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError(
                'Имя пользователя содержит недопустимые символы. Разрешены только буквы, цифры и @/./+/-/_')

        # Проверяем уникальность
        if User.objects.filter(username=username).exists():
            raise ValidationError('Это имя пользователя уже занято')

        return username

    def clean(self):
        """Дополнительная проверка всей формы"""
        cleaned_data = super().clean()

        # Проверяем совпадение паролей
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'Пароли не совпадают')

        return cleaned_data

    def save(self, commit=True):
        """Атомарное сохранение пользователя с проверкой уникальности телефона"""
        user = super().save(commit=False)

        if not commit:
            return user

        try:
            with transaction.atomic():
                # Помечаем, что создаем профиль через форму (чтобы сигнал не создавал временный)
                user._creating_profile_via_form = True

                # 1. Сохраняем пользователя
                user.save()

                # 2. Получаем телефон
                phone = self.cleaned_data.get('phone')
                if not phone:
                    raise ValidationError('Номер телефона обязателен')

                # 3. Удаляем временный профиль, если он был создан сигналом
                # (на всякий случай, хотя с флагом выше не должен создаться)
                UserProfile.objects.filter(user=user).delete()

                # 4. Проверяем уникальность телефона еще раз (на случай race condition)
                if UserProfile.objects.filter(phone=phone).exists():
                    # Ищем, кто уже использует этот телефон
                    existing = UserProfile.objects.filter(phone=phone).first()
                    if existing:
                        raise ValidationError(
                            f'Номер телефона {phone} уже используется пользователем {existing.user.username}'
                        )
                    else:
                        raise ValidationError(f'Номер телефона {phone} уже зарегистрирован')

                # 5. Проверяем другие форматы
                phone_digits = phone[1:]  # Убираем +
                other_formats = ['8' + phone_digits, phone_digits[1:]]

                for fmt in other_formats:
                    if UserProfile.objects.filter(phone=fmt).exists():
                        existing = UserProfile.objects.filter(phone=fmt).first()
                        raise ValidationError(
                            f'Номер телефона уже используется пользователем {existing.user.username}'
                        )

                # 6. Создаем профиль
                profile = UserProfile(user=user, phone=phone)

                # 7. Генерируем код подтверждения
                profile.generate_verification_code()

                # 8. Сохраняем профиль (внутри будет еще одна проверка)
                profile.save()

                # 9. Логируем успешную регистрацию
                print(f"\n{'=' * 50}")
                print(f"УСПЕШНАЯ РЕГИСТРАЦИЯ")
                print(f"Пользователь: {user.username}")
                print(f"Телефон: {profile.phone}")
                print(f"Уникальный ID: {user.id}")
                print(f"{'=' * 50}\n")

                return user

        except ValidationError as e:
            # Если есть ValidationError, пробрасываем его
            raise e
        except IntegrityError as e:
            # Ошибка уникальности из базы данных
            if 'unique' in str(e).lower() or 'phone' in str(e).lower():
                raise ValidationError('Этот номер телефона уже зарегистрирован')
            raise ValidationError(f'Ошибка при регистрации: {str(e)}')
        except Exception as e:
            raise ValidationError(f'Неизвестная ошибка: {str(e)}')
        finally:
            # Удаляем флаг
            if hasattr(user, '_creating_profile_via_form'):
                delattr(user, '_creating_profile_via_form')


class LoginForm(forms.Form):
    identifier = forms.CharField(
        max_length=150,
        required=True,
        label='Имя пользователя или телефон',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите имя пользователя или номер телефона',
            'id': 'loginIdentifier'
        }),
        help_text='Можно ввести имя пользователя или номер телефона (+7...)'
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите пароль',
            'id': 'loginPassword'
        }),
        label='Пароль'
    )

    def clean_identifier(self):
        identifier = self.cleaned_data.get('identifier', '').strip()

        if not identifier:
            raise ValidationError('Введите имя пользователя или номер телефона')

        # Проверяем, похоже ли на телефон (содержит цифры)
        if any(char.isdigit() for char in identifier):
            # Пытаемся нормализовать телефон
            normalized_phone = UserProfile.objects.normalize_phone(identifier)
            if normalized_phone:
                # Пытаемся найти пользователя по телефону
                user = UserProfile.objects.get_user_by_phone(identifier)
                if user:
                    return {'type': 'phone', 'value': normalized_phone, 'username': user.username}

        # Если не телефон или не нашли по телефону, считаем username
        if len(identifier) < 3:
            raise ValidationError('Имя пользователя должно содержать минимум 3 символа')

        if len(identifier) > 150:
            raise ValidationError('Имя пользователя не должно превышать 150 символов')

        if not re.match(r'^[\w.@+-]+$', identifier):
            raise ValidationError(
                'Имя пользователя содержит недопустимые символы. Разрешены только буквы, цифры и @/./+/-/_')

        return {'type': 'username', 'value': identifier, 'username': identifier}

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError('Введите пароль')
        return password

    def clean(self):
        """Дополнительная проверка формы"""
        cleaned_data = super().clean()

        identifier_data = cleaned_data.get('identifier')
        password = cleaned_data.get('password')

        if identifier_data and password:
            # Проверяем существование пользователя
            if identifier_data['type'] == 'username':
                # Для username проверяем существование пользователя
                if not User.objects.filter(username=identifier_data['value']).exists():
                    self.add_error('identifier', 'Пользователь с таким именем не найден')
            else:
                # Для телефона проверяем существование профиля
                if not UserProfile.objects.get_user_by_phone(identifier_data['value']):
                    self.add_error('identifier', 'Пользователь с таким номером телефона не найден')

        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=20,
        required=True,
        label='Номер телефона',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '+7 (999) 123-45-67'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        error_messages = {
            'username': {
                'unique': 'Это имя пользователя уже занято',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['phone'].initial = self.instance.profile.phone

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()

        if not phone:
            raise ValidationError('Номер телефона обязателен')

        # Используем ту же логику нормализации, что и в RegistrationForm
        phone_digits = re.sub(r'\D', '', phone)

        if not phone_digits:
            raise ValidationError('Введите корректный номер телефона')

        if len(phone_digits) < 10 or len(phone_digits) > 11:
            raise ValidationError('Номер телефона должен содержать 10-11 цифр')

        # Нормализуем
        if len(phone_digits) == 10:
            phone_digits = '7' + phone_digits
        elif len(phone_digits) == 11 and phone_digits.startswith('8'):
            phone_digits = '7' + phone_digits[1:]

        if len(phone_digits) != 11 or not phone_digits.startswith('7'):
            raise ValidationError('Российский номер должен содержать 11 цифр и начинаться с +7')

        formatted_phone = '+' + phone_digits

        # Проверка уникальности (исключая текущего пользователя)
        if self.instance and hasattr(self.instance, 'profile'):
            # Проверяем все форматы
            other_formats = [
                formatted_phone,
                '8' + phone_digits[1:],
                phone_digits,
                phone_digits[1:],
            ]

            for fmt in other_formats:
                qs = UserProfile.objects.filter(phone=fmt).exclude(user=self.instance)
                if qs.exists():
                    users = [p.user.username for p in qs]
                    raise ValidationError(f'Этот номер телефона уже используется: {", ".join(users)}')

        return formatted_phone