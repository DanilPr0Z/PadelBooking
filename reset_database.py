import os
import shutil
import django
from pathlib import Path
import sys

# Определяем путь к проекту
current_file = Path(__file__).resolve()
PROJECT_ROOT = current_file.parent

# Проверяем, есть ли manage.py в этой директории
if not (PROJECT_ROOT / 'manage.py').exists():
    print("❌ Ошибка: Не найден manage.py.")
    print(f"   Текущая директория: {PROJECT_ROOT}")
    print("   Убедитесь, что скрипт находится в той же папке, что и manage.py")
    sys.exit(1)

print(f"✓ Найден manage.py в: {PROJECT_ROOT}")

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paddle_booking.settings')
try:
    django.setup()
except Exception as e:
    print(f"❌ Ошибка инициализации Django: {e}")
    sys.exit(1)

from django.core.management import execute_from_command_line
from django.contrib.auth.models import User
from django.conf import settings
from django.db import connection

BASE_DIR = settings.BASE_DIR
DB_FILE = BASE_DIR / 'db.sqlite3'
MEDIA_ROOT = Path(settings.MEDIA_ROOT)
APPS = ['booking', 'users']


def wipe_db():
    """Удаление базы данных"""
    print("\n⏳ Удаление базы данных...")
    if DB_FILE.exists():
        try:
            connection.close()
            DB_FILE.unlink()
            print(f"✓ Удалён файл БД: {DB_FILE.name}")
        except Exception as e:
            print(f"✗ Ошибка удаления БД: {e}")
            return False
    else:
        print(f"ℹ️  Файл БД не найден: {DB_FILE}")
    return True


def wipe_migrations():
    """Удаление файлов миграций"""
    print("\n⏳ Очистка миграций...")
    for app in APPS:
        mig_dir = BASE_DIR / app / 'migrations'
        if not mig_dir.exists():
            continue

        try:
            for item in mig_dir.iterdir():
                if item.is_file() and item.name != '__init__.py' and item.suffix == '.py':
                    item.unlink()
                elif item.is_dir() and item.name == '__pycache__':
                    shutil.rmtree(item, ignore_errors=True)
            print(f"✓ Миграции {app} очищены")
        except Exception as e:
            print(f"✗ Ошибка удаления миграций {app}: {e}")


def wipe_media():
    """Очистка медиафайлов"""
    print("\n⏳ Очистка медиафайлов...")
    if MEDIA_ROOT.exists():
        try:
            for item in MEDIA_ROOT.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                elif item.is_file():
                    item.unlink()
            print(f"✓ Медиафайлы очищены")
        except Exception as e:
            print(f"✗ Ошибка очистки медиа: {e}")
    else:
        print(f"ℹ️  Папка media не существует: {MEDIA_ROOT}")


def recreate_migrations_and_db():
    """Создание миграций и базы данных"""
    print("\n⏳ Создание миграций...")
    try:
        execute_from_command_line(['manage.py', 'makemigrations'])
        print("✓ Миграции созданы")
    except Exception as e:
        print(f"✗ Ошибка создания миграций: {e}")
        return False

    print("\n⏳ Применение миграций...")
    try:
        execute_from_command_line(['manage.py', 'migrate'])
        print("✓ Миграции применены")
        return True
    except Exception as e:
        print(f"✗ Ошибка применения миграций: {e}")
        return False


def create_superuser():
    """Создание суперпользователя"""
    print("\n⏳ Создание суперпользователя...")
    try:
        User.objects.filter(username='admin').delete()

        su = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )

        from users.models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=su)
        profile.phone = '+79100000001'
        profile.phone_verified = True
        profile.save()

        print("✓ Суперпользователь создан")
        return True

    except Exception as e:
        print(f"✗ Ошибка создания суперпользователя: {e}")
        return False


def create_test_courts():
    """Создание тестовых кортов"""
    print("\n⏳ Создание тестовых кортов...")
    try:
        from booking.models import Court

        Court.objects.all().delete()

        courts = [
            {
                'name': 'Корт 1',
                'description': 'Основной теннисный корт с покрытием Professional',
                'price_per_hour': 1500.00,
                'is_available': True
            },
            {
                'name': 'Корт 2',
                'description': 'VIP корт с освещением и трибунами',
                'price_per_hour': 2500.00,
                'is_available': True
            },
            {
                'name': 'Корт 3',
                'description': 'Тренировочный корт для начинающих',
                'price_per_hour': 1000.00,
                'is_available': True
            },
        ]

        for court_data in courts:
            Court.objects.create(**court_data)

        print(f"✓ Создано {len(courts)} тестовых корта")
        return True

    except Exception as e:
        print(f"ℹ️  Не удалось создать тестовые корты: {e}")
        return False


def reset_database():
    print("\n" + "=" * 60)
    print("🚨 ПОЛНЫЙ СБРОС СИСТЕМЫ БРОНИРОВАНИЯ")
    print("=" * 60)

    wipe_migrations_choice = input("\nУдалять файлы миграций? (yes/no) [no]: ").strip().lower()
    if wipe_migrations_choice == '':
        wipe_migrations_choice = 'no'

    wipe_media_choice = input("Удалять медиафайлы? (yes/no) [no]: ").strip().lower()
    if wipe_media_choice == '':
        wipe_media_choice = 'no'

    print("\n" + "=" * 60)

    success = True

    if wipe_migrations_choice == 'yes':
        wipe_migrations()

    if wipe_media_choice == 'yes':
        wipe_media()

    if not wipe_db():
        success = False

    if success:
        if not recreate_migrations_and_db():
            success = False

    if success:
        if not create_superuser():
            success = False

    if success:
        test_courts = input("\nСоздать тестовые корты? (yes/no) [yes]: ").strip().lower()
        if test_courts == '' or test_courts != 'no':
            create_test_courts()

    print("\n" + "=" * 60)
    if success:
        print("✅ СБРОС УСПЕШНО ЗАВЕРШЕН")
        print("\n📋 Доступные данные:")
        print("• Суперпользователь: admin / admin123")
        print("• 3 тестовых корта")
        print("\n🔗 Ссылки:")
        print("• Админка: http://localhost:8000/admin/")
        print("• Бронирование: http://localhost:8000/booking/")
    else:
        print("❌ СБРОС НЕ УДАЛСЯ")
    print("=" * 60)


if __name__ == "__main__":
    print("⚠️  ВНИМАНИЕ: Этот скрипт удалит все данные в системе!")
    print("   Включая пользователей, бронирования, корты и медиафайлы.\n")

    confirm = input("Вы уверены, что хотите продолжить? (yes/no): ").strip().lower()

    if confirm == 'yes':
        try:
            reset_database()
        except KeyboardInterrupt:
            print("\n\n❌ Прервано пользователем")
        except Exception as e:
            print(f"\n❌ Непредвиденная ошибка: {e}")
            import traceback

            traceback.print_exc()
    else:
        print("Отменено.")