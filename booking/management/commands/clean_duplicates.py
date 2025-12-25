import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paddle_booking.settings')
django.setup()

from django.contrib.auth.models import User
from users.models import UserProfile


def normalize_phone(phone):
    """Нормализует номер телефона для сравнения"""
    if not phone:
        return None

    # Убираем все нецифровые символы
    digits = re.sub(r'\D', '', str(phone))

    if not digits:
        return None

    # Нормализуем российский номер
    if digits.startswith('8'):
        digits = '7' + digits[1:]
    elif digits.startswith('9'):
        digits = '7' + digits

    if not digits.startswith('7'):
        digits = '7' + digits

    # Должно быть 11 цифр
    if len(digits) != 11:
        return None

    return '+' + digits


def clean_database():
    print("=== ОЧИСТКА БАЗЫ ДАННЫХ ОТ ДУБЛИКАТОВ ===\n")

    # 1. Удаляем тестовых пользователей (кроме admin)
    test_users = User.objects.filter(username__startswith='KAMEHb')
    print(f"Найдено тестовых пользователей: {test_users.count()}")

    for user in test_users:
        print(f"  Удаляю: {user.username}")
        user.delete()

    # 2. Находим дубликаты телефонов
    print("\n=== ПОИСК ДУБЛИКАТОВ ТЕЛЕФОНОВ ===")

    # Собираем все профили с телефонами
    profiles = UserProfile.objects.exclude(phone__isnull=True).exclude(phone='')
    print(f"Всего профилей с телефонами: {profiles.count()}")

    # Группируем по нормализованным телефонам
    phone_groups = {}
    for profile in profiles:
        normalized = normalize_phone(profile.phone)
        if normalized:
            if normalized not in phone_groups:
                phone_groups[normalized] = []
            phone_groups[normalized].append(profile)

    # Находим дубликаты
    duplicates = {phone: profiles for phone, profiles in phone_groups.items()
                  if len(profiles) > 1}

    print(f"Найдено дубликатов: {len(duplicates)}")

    if duplicates:
        print("\nИсправляю дубликаты...")
        for phone, dup_profiles in duplicates.items():
            print(f"\nТелефон: {phone}")
            print(f"  Найден у {len(dup_profiles)} пользователей:")

            # Оставляем телефон у первого пользователя (самого старого)
            dup_profiles.sort(key=lambda p: p.created_at)
            keep_profile = dup_profiles[0]

            for i, profile in enumerate(dup_profiles):
                if i == 0:
                    print(f"  ✓ Оставляю у: {profile.user.username} (создан: {profile.created_at})")
                else:
                    print(f"  ✗ Удаляю у: {profile.user.username}")

                    # Удаляем пользователя полностью
                    profile.user.delete()

    # 3. Создаем профили для пользователей без профилей
    print("\n=== СОЗДАНИЕ ПРОФИЛЕЙ ===")
    users_without_profiles = []
    for user in User.objects.all():
        try:
            user.profile
        except UserProfile.DoesNotExist:
            users_without_profiles.append(user)

    if users_without_profiles:
        print(f"Пользователей без профилей: {len(users_without_profiles)}")
        for user in users_without_profiles:
            # Создаем уникальный временный телефон
            import time
            timestamp = int(time.time() * 1000) % 100000000
            temp_phone = f'+7980{timestamp:08d}'[:12]  # Ограничиваем длину

            UserProfile.objects.create(
                user=user,
                phone=temp_phone
            )
            print(f"  Создан профиль для: {user.username} (телефон: {temp_phone})")
    else:
        print("Все пользователи имеют профили")

    # 4. Итоговая проверка
    print("\n=== ИТОГ ===")
    print(f"Всего пользователей: {User.objects.count()}")
    print(f"Всего профилей: {UserProfile.objects.count()}")

    # Проверяем уникальность телефонов
    all_phones = []
    for profile in UserProfile.objects.all():
        if profile.phone:
            all_phones.append(profile.phone)

    unique_phones = set(all_phones)
    print(f"Уникальных телефонов: {len(unique_phones)}")
    print(f"Всего телефонов в базе: {len(all_phones)}")

    if len(unique_phones) != len(all_phones):
        print("ВНИМАНИЕ: Есть дубликаты телефонов!")
    else:
        print("✓ Все телефоны уникальны")


if __name__ == "__main__":
    clean_database()