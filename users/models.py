from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator
import hashlib
import secrets


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

    def __str__(self):
        return f"{self.user.username} - {self.phone}"

    def generate_verification_code(self):
        """Генерация кода подтверждения телефона"""
        self.verification_code = secrets.choice('1234567890') + \
                                 secrets.choice('1234567890') + \
                                 secrets.choice('1234567890') + \
                                 secrets.choice('1234567890')
        self.save()
        return self.verification_code

    def verify_phone(self, code):
        """Подтверждение телефона"""
        if self.verification_code == code:
            self.phone_verified = True
            self.verification_code = None
            self.save()
            return True
        return False


# Сигналы для автоматического создания профиля
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()