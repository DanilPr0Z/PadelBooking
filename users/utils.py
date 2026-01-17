import re
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from .models import CoachProfile, User


def is_coach(user):
    """Проверка, является ли пользователь тренером"""
    if not user.is_authenticated:
        return False

    # Проверяем по группе
    if user.groups.filter(name='Тренеры').exists():
        return True

    # Проверяем по профилю тренера
    try:
        return user.coach_profile.is_active
    except CoachProfile.DoesNotExist:
        return False

    return False


def get_coach_profile(user):
    """Получить профиль тренера"""
    try:
        return user.coach_profile
    except CoachProfile.DoesNotExist:
        return None


def get_coaches():
    """Получить всех активных тренеров"""
    return User.objects.filter(
        groups__name='Тренеры',
        coach_profile__is_active=True
    ).select_related('coach_profile').order_by('username')


def assign_coach_to_player(player, coach):
    """Назначить тренера игроку"""
    from .models import PlayerCoachRelationship

    if not is_coach(coach):
        raise ValueError(f"Пользователь {coach.username} не является тренером")

    # Проверяем, есть ли уже связь
    existing = PlayerCoachRelationship.objects.filter(
        player=player,
        coach=coach
    ).first()

    if existing:
        # Активируем существующую связь
        existing.is_active = True
        existing.save()
        return existing
    else:
        # Создаем новую связь
        return PlayerCoachRelationship.objects.create(
            player=player,
            coach=coach,
            is_active=True
        )


def get_player_coaches(player):
    """Получить тренеров игрока"""
    from .models import PlayerCoachRelationship

    return User.objects.filter(
        coaches__player=player,
        coaches__is_active=True
    ).distinct()


def get_coach_players(coach):
    """Получить игроков тренера"""
    from .models import PlayerCoachRelationship

    return User.objects.filter(
        players__coach=coach,
        players__is_active=True
    ).distinct()


# ========== УТИЛИТЫ ДЛЯ ТЕЛЕФОНА ==========

def normalize_phone(phone):
    """
    Нормализует номер телефона к формату +7XXXXXXXXXX

    Принимает различные форматы:
    - +7 (912) 345-67-89
    - 8 (912) 345-67-89
    - 79123456789
    - 89123456789
    - 9123456789

    Возвращает: +79123456789
    """
    if not phone:
        raise ValidationError("Телефон не может быть пустым")

    # Удаляем все символы кроме цифр и +
    phone_digits = re.sub(r'[^\d+]', '', phone)

    # Удаляем + если есть
    phone_digits = phone_digits.replace('+', '')

    # Проверяем длину
    if len(phone_digits) < 10:
        raise ValidationError("Телефон слишком короткий")

    if len(phone_digits) > 11:
        raise ValidationError("Телефон слишком длинный")

    # Нормализуем к формату +7XXXXXXXXXX
    if phone_digits.startswith('8') and len(phone_digits) == 11:
        # 89123456789 -> +79123456789
        phone_digits = '7' + phone_digits[1:]
    elif phone_digits.startswith('7') and len(phone_digits) == 11:
        # 79123456789 -> +79123456789
        pass
    elif len(phone_digits) == 10:
        # 9123456789 -> +79123456789
        phone_digits = '7' + phone_digits
    else:
        raise ValidationError("Неверный формат телефона")

    return '+' + phone_digits


def get_user_by_phone(phone):
    """
    Находит пользователя по номеру телефона
    Проверяет все возможные форматы
    """
    from .models import UserProfile

    try:
        normalized = normalize_phone(phone)
    except ValidationError:
        return None

    # Пытаемся найти по нормализованному телефону
    try:
        profile = UserProfile.objects.get(phone=normalized)
        return profile.user
    except UserProfile.DoesNotExist:
        pass

    # Пытаемся найти по другим форматам
    phone_digits = re.sub(r'[^\d]', '', phone)

    # Генерируем возможные варианты
    variants = set()

    if phone_digits.startswith('8') and len(phone_digits) == 11:
        variants.add('+7' + phone_digits[1:])
        variants.add('+' + phone_digits)
    elif phone_digits.startswith('7') and len(phone_digits) == 11:
        variants.add('+' + phone_digits)
        variants.add('+8' + phone_digits[1:])
    elif len(phone_digits) == 10:
        variants.add('+7' + phone_digits)
        variants.add('+8' + phone_digits)

    for variant in variants:
        try:
            profile = UserProfile.objects.get(phone=variant)
            return profile.user
        except UserProfile.DoesNotExist:
            continue

    return None


def format_phone_display(phone):
    """
    Форматирует телефон для отображения
    +79123456789 -> +7 (912) 345-67-89
    """
    if not phone:
        return ""

    # Удаляем все кроме цифр
    digits = re.sub(r'\D', '', phone)

    if len(digits) == 11 and digits[0] in ('7', '8'):
        # +7 (XXX) XXX-XX-XX
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    elif len(digits) == 10:
        # +7 (XXX) XXX-XX-XX
        return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"

    return phone
