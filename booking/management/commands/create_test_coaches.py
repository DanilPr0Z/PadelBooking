"""
Management command для создания тестовых тренеров
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from users.models import CoachProfile, UserProfile


class Command(BaseCommand):
    help = 'Создает тестовых тренеров для демонстрации'

    def handle(self, *args, **options):
        # Создаем или получаем группу "Тренеры"
        coaches_group, created = Group.objects.get_or_create(name='Тренеры')
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Создана группа "Тренеры"'))
        else:
            self.stdout.write('ℹ️  Группа "Тренеры" уже существует')

        # Данные тренеров
        coaches_data = [
            {
                'username': 'coach_ivan',
                'email': 'ivan@example.com',
                'first_name': 'Иван',
                'last_name': 'Петров',
                'password': 'testpass123',
                'phone': '+79161234567',
                'qualifications': 'Мастер спорта по теннису, сертифицированный тренер PTR Level 2',
                'specialization': 'Начинающие и средний уровень',
                'experience_years': 8,
                'hourly_rate': 2500,
                'bio': 'Профессиональный тренер с 8-летним опытом. Специализируюсь на работе с начинающими игроками и игроками среднего уровня.',
                'coach_rating': 4.8,
            },
            {
                'username': 'coach_maria',
                'email': 'maria@example.com',
                'first_name': 'Мария',
                'last_name': 'Соколова',
                'password': 'testpass123',
                'phone': '+79162345678',
                'qualifications': 'КМС по теннису, сертификат ITF Level 1',
                'specialization': 'Продвинутые игроки, спарринг-партнер',
                'experience_years': 5,
                'hourly_rate': 3000,
                'bio': 'Работаю с продвинутыми игроками. Помогу улучшить технику и тактику игры.',
                'coach_rating': 4.9,
            },
            {
                'username': 'coach_alex',
                'email': 'alex@example.com',
                'first_name': 'Алексей',
                'last_name': 'Новиков',
                'password': 'testpass123',
                'phone': '+79163456789',
                'qualifications': 'Профессиональный теннисист, участник ATP Challenger Tour',
                'specialization': 'Все уровни, индивидуальный подход',
                'experience_years': 12,
                'hourly_rate': 4000,
                'bio': 'Профессиональный спортсмен с 12-летним опытом. Индивидуальный подход к каждому ученику.',
                'coach_rating': 5.0,
            },
        ]

        created_count = 0
        for coach_data in coaches_data:
            # Проверяем, существует ли уже этот пользователь
            if User.objects.filter(username=coach_data['username']).exists():
                self.stdout.write(f'⚠️  Тренер {coach_data["username"]} уже существует, пропускаем')
                continue

            # Создаем пользователя
            user = User.objects.create_user(
                username=coach_data['username'],
                email=coach_data['email'],
                first_name=coach_data['first_name'],
                last_name=coach_data['last_name'],
                password=coach_data['password']
            )

            # Добавляем в группу тренеров
            user.groups.add(coaches_group)

            # Создаем или обновляем UserProfile
            user_profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={'phone': coach_data['phone']}
            )

            # Создаем профиль тренера
            CoachProfile.objects.create(
                user=user,
                qualifications=coach_data['qualifications'],
                specialization=coach_data['specialization'],
                experience_years=coach_data['experience_years'],
                hourly_rate=coach_data['hourly_rate'],
                bio=coach_data['bio'],
                coach_rating=coach_data['coach_rating'],
                is_active=True
            )

            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Создан тренер: {coach_data["first_name"]} {coach_data["last_name"]} '
                    f'({coach_data["hourly_rate"]}₽/час, рейтинг {coach_data["coach_rating"]})'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Готово! Создано {created_count} новых тренеров'
            )
        )
