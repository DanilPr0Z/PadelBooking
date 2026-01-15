
from django.contrib.auth.models import Group
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

