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
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label='Имя',
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите ваше имя',
            'class': 'form-input',
            'id': 'regFirstName'
        }),
        error_messages={
            'required': 'Имя обязательно',
        }
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        label='Фамилия',
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите вашу фамилию',
            'class': 'form-input',
            'id': 'regLastName'
        }),
        error_messages={
            'required': 'Фамилия обязательна',
        }
    )

    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={
            'placeholder': 'example@email.com',
            'class': 'form-input',
            'id': 'regEmail'
        }),
        error_messages={
            'required': 'Email обязателен',
            'invalid': 'Введите корректный email адрес',
        }
    )

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
        fields = ['first_name', 'last_name', 'email', 'phone', 'password1', 'password2']
        help_texts = {
            'password1': 'Пароль должен содержать минимум 8 символов',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поля обязательными в HTML
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True
        self.fields['password1'].required = True
        self.fields['password2'].required = True

    def clean_phone(self):
        from .utils import normalize_phone

        phone = self.cleaned_data.get('phone', '').strip()

        if not phone:
            raise ValidationError('Номер телефона обязателен')

        # Нормализуем телефон используя утилиту
        try:
            formatted_phone = normalize_phone(phone)
        except ValidationError as e:
            raise ValidationError(f'Некорректный номер телефона: {e}')

        # Извлекаем цифры для проверки других форматов
        phone_digits = formatted_phone[1:]  # Убираем +

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

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()

        if not first_name:
            raise ValidationError('Имя обязательно')

        if len(first_name) < 2:
            raise ValidationError('Имя должно содержать минимум 2 символа')

        if len(first_name) > 150:
            raise ValidationError('Имя не должно превышать 150 символов')

        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()

        if not last_name:
            raise ValidationError('Фамилия обязательна')

        if len(last_name) < 2:
            raise ValidationError('Фамилия должна содержать минимум 2 символа')

        if len(last_name) > 150:
            raise ValidationError('Фамилия не должна превышать 150 символов')

        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()

        if not email:
            raise ValidationError('Email обязателен')

        # Проверяем уникальность email
        if User.objects.filter(email=email).exists():
            raise ValidationError('Этот email уже зарегистрирован')

        return email

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

        # Получаем данные из формы
        first_name = self.cleaned_data.get('first_name')
        last_name = self.cleaned_data.get('last_name')
        email = self.cleaned_data.get('email')

        # Устанавливаем first_name, last_name и email
        user.first_name = first_name
        user.last_name = last_name
        user.email = email

        # Генерируем уникальный username из email
        # Берем часть до @ и добавляем уникальный номер если нужно
        email_base = email.split('@')[0]
        # Очищаем от недопустимых символов
        username_base = re.sub(r'[^\w.@+-]', '_', email_base)[:30]  # Ограничиваем длину

        # Находим уникальный username
        username = username_base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{username_base}_{counter}"
            counter += 1

        user.username = username

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
                print(f"Имя: {user.first_name} {user.last_name}")
                print(f"Email: {user.email}")
                print(f"Телефон: {profile.phone}")
                print(f"Username (автогенерация): {user.username}")
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
        label='Email или телефон',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Введите email или номер телефона',
            'id': 'loginIdentifier'
        }),
        help_text='Можно ввести email или номер телефона (+7...)'
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
            raise ValidationError('Введите email или номер телефона')

        # Проверяем, похоже ли на телефон (содержит цифры и мало букв)
        digit_count = sum(c.isdigit() for c in identifier)
        if digit_count >= 7:  # Если есть 7+ цифр, скорее всего телефон
            # Пытаемся нормализовать телефон
            normalized_phone = UserProfile.objects.normalize_phone(identifier)
            if normalized_phone:
                # Пытаемся найти пользователя по телефону
                user = UserProfile.objects.get_user_by_phone(identifier)
                if user:
                    return {'type': 'phone', 'value': normalized_phone, 'username': user.username}
                else:
                    raise ValidationError('Пользователь с таким номером телефона не найден')

        # Проверяем, похоже ли на email (содержит @)
        if '@' in identifier:
            email = identifier.lower()
            try:
                user = User.objects.get(email=email)
                return {'type': 'email', 'value': email, 'username': user.username}
            except User.DoesNotExist:
                raise ValidationError('Пользователь с таким email не найден')

        # Если не телефон и не email
        raise ValidationError('Введите корректный email или номер телефона')

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
            # Проверка уже выполнена в clean_identifier
            pass

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
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Введите ваше имя'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Введите вашу фамилию'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'example@email.com'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['phone'].initial = self.instance.profile.phone
        # Делаем поля обязательными
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['email'].required = True

    def clean_phone(self):
        from .utils import normalize_phone

        phone = self.cleaned_data.get('phone', '').strip()

        if not phone:
            raise ValidationError('Номер телефона обязателен')

        # Нормализуем телефон используя утилиту
        try:
            formatted_phone = normalize_phone(phone)
        except ValidationError as e:
            raise ValidationError(f'Некорректный номер телефона: {e}')

        # Извлекаем цифры для проверки других форматов
        phone_digits = formatted_phone[1:]  # Убираем +

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

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()

        if not first_name:
            raise ValidationError('Имя обязательно')

        if len(first_name) < 2:
            raise ValidationError('Имя должно содержать минимум 2 символа')

        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()

        if not last_name:
            raise ValidationError('Фамилия обязательна')

        if len(last_name) < 2:
            raise ValidationError('Фамилия должна содержать минимум 2 символа')

        return last_name

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()

        if not email:
            raise ValidationError('Email обязателен')

        # Проверяем уникальность email (исключая текущего пользователя)
        qs = User.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError('Этот email уже используется другим пользователем')

        return email

from django import forms
from .models import PlayerRating


class PlayerRatingForm(forms.ModelForm):
    """Форма для изменения рейтинга игрока (доступна только тренерам)"""

    class Meta:
        model = PlayerRating
        fields = ['numeric_rating', 'coach_comment']
        widgets = {
            'numeric_rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '1.00',
                'max': '7.00',
                'placeholder': 'Введите значение от 1.00 до 7.00'
            }),
            'coach_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Комментарий тренера о навыках игрока'
            })
        }
        labels = {
            'numeric_rating': 'Числовой рейтинг',
            'coach_comment': 'Комментарий тренера'
        }
        help_texts = {
            'numeric_rating': 'Значение от 1.00 (новичок) до 7.00 (профессионал)',
        }

    def clean_numeric_rating(self):
        numeric_rating = self.cleaned_data.get('numeric_rating')

        if numeric_rating < 1.00 or numeric_rating > 7.00:
            raise forms.ValidationError('Рейтинг должен быть в диапазоне от 1.00 до 7.00')

        return round(float(numeric_rating), 2)