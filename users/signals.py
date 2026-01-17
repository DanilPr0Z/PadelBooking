# Создадим файл signals.py:
from django.apps import AppConfig
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import PlayerRating


@receiver(post_save, sender=User)
def create_player_rating(sender, instance, created, **kwargs):
    """Создать рейтинг при создании пользователя"""
    if created:
        # Используем get_or_create для избежания IntegrityError при повторном срабатывании
        PlayerRating.objects.get_or_create(
            user=instance,
            defaults={'numeric_rating': 1.00, 'level': 'D'}
        )


# В apps.py добавим:
class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        import users.signals  # Импортируем сигналы