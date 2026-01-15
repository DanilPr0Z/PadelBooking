
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import UserProfile, PlayerRating


class Command(BaseCommand):
    help = 'Создает группу тренеров и назначает необходимые разрешения'

    def handle(self, *args, **kwargs):
        # Создаем группу тренеров
        coach_group, created = Group.objects.get_or_create(name='Тренеры')

        if created:
            self.stdout.write(self.style.SUCCESS('Группа "Тренеры" создана'))
        else:
            self.stdout.write(self.style.WARNING('Группа "Тренеры" уже существует'))

        # Получаем разрешения для моделей
        user_content_type = ContentType.objects.get_for_model(UserProfile)
        rating_content_type = ContentType.objects.get_for_model(PlayerRating)

        # Разрешения для управления пользователями
        permissions = [
            'view_userprofile',
            'change_userprofile',
        ]

        # Разрешения для управления рейтингами
        rating_permissions = [
            'view_playerrating',
            'change_playerrating',
            'add_playerrating',
            'delete_playerrating',
        ]

        # Добавляем разрешения к группе
        for perm_codename in permissions:
            try:
                perm = Permission.objects.get(
                    content_type=user_content_type,
                    codename=perm_codename
                )
                coach_group.permissions.add(perm)
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Разрешение {perm_codename} не найдено'))

        for perm_codename in rating_permissions:
            try:
                perm = Permission.objects.get(
                    content_type=rating_content_type,
                    codename=perm_codename
                )
                coach_group.permissions.add(perm)
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Разрешение {perm_codename} не найдено'))

        self.stdout.write(self.style.SUCCESS('Разрешения назначены группе "Тренеры"'))

        # Выводим информацию о группе
        coach_permissions = coach_group.permissions.all()
        self.stdout.write(f'\nГруппа "Тренеры" имеет {coach_permissions.count()} разрешений:')

        for perm in coach_permissions:
            self.stdout.write(f'  - {perm.name}')

