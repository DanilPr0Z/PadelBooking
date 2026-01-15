from django.core.management.base import BaseCommand
from booking.models import Court
from decimal import Decimal

class Command(BaseCommand):
    help = 'Создает тестовые корты для системы бронирования'

    def handle(self, *args, **kwargs):
        # Удаляем существующие корты (опционально)
        # Court.objects.all().delete()
        
        # Создаем тестовые корты
        courts = [
            {
                'name': 'Корт №1 (Центральный)',
                'description': 'Профессиональный корт с искусственным покрытием. Идеально подходит для соревнований.',
                'price_per_hour': Decimal('1500.00'),
                'is_available': True
            },
            {
                'name': 'Корт №2 (Стандарт)',
                'description': 'Стандартный корт для тренировок и любительских игр.',
                'price_per_hour': Decimal('1200.00'),
                'is_available': True
            },
            {
                'name': 'Корт №3 (Крытый)',
                'description': 'Крытый корт с системой кондиционирования. Доступен в любую погоду.',
                'price_per_hour': Decimal('1800.00'),
                'is_available': True
            },
            {
                'name': 'Корт №4 (Панорамный)',
                'description': 'Корт с панорамным видом на город. Отличное место для игры на закате.',
                'price_per_hour': Decimal('2000.00'),
                'is_available': True
            },
            {
                'name': 'Корт №5 (Тренировочный)',
                'description': 'Корт для начинающих и тренировок с тренером.',
                'price_per_hour': Decimal('1000.00'),
                'is_available': True
            },
        ]
        
        created_count = 0
        for court_data in courts:
            court, created = Court.objects.get_or_create(
                name=court_data['name'],
                defaults={
                    'description': court_data['description'],
                    'price_per_hour': court_data['price_per_hour'],
                    'is_available': court_data['is_available']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Создан корт: {court.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Корт уже существует: {court.name}'))
        
        self.stdout.write(self.style.SUCCESS(f'Создано {created_count} новых кортов'))