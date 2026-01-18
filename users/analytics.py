"""
Модуль аналитики для игроков и администраторов
Статистика игр, активности, предпочтений
"""

from django.db.models import Count, Sum, Q, Avg, F, Case, When, Value, IntegerField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDate, ExtractWeekDay
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict
from booking.models import Booking, Court
from .models import PlayerRating
from django.contrib.auth.models import User


def get_player_stats(user):
    """
    Полная статистика игрока

    Возвращает:
    - Общие показатели (игры, часы, траты)
    - Любимые корты и партнеры
    - Активность по месяцам/неделям
    - Прогресс рейтинга
    """
    today = timezone.now().date()

    # Все завершенные игры пользователя (как создатель или партнер)
    completed_bookings = Booking.objects.filter(
        Q(user=user) | Q(partners=user),
        status='confirmed',
        date__lte=today
    ).select_related('court').prefetch_related('partners')

    # Будущие игры
    upcoming_bookings = Booking.objects.filter(
        Q(user=user) | Q(partners=user),
        status__in=['pending', 'confirmed'],
        date__gte=today
    ).select_related('court').prefetch_related('partners')

    # Общая статистика
    total_games = completed_bookings.count()
    total_hours = sum(_calculate_duration(b) for b in completed_bookings)

    # Расчет затрат
    total_spent = 0
    for booking in completed_bookings:
        if booking.user == user:
            # Если создатель - платит за корт
            total_spent += float(booking.total_price)
        else:
            # Если партнер - платит свою долю
            total_spent += float(booking.price_per_person)

    # Любимый корт
    favorite_court = completed_bookings.values(
        'court__id', 'court__name'
    ).annotate(
        games_count=Count('id')
    ).order_by('-games_count').first()

    # Любимые партнеры (топ-5)
    favorite_partners = []
    partner_stats = defaultdict(int)

    for booking in completed_bookings:
        if booking.user == user:
            # Считаем партнеров из бронирований где мы создатель
            for partner in booking.partners.all():
                partner_stats[partner.id] += 1
        elif user in booking.partners.all():
            # Считаем создателя если мы партнер
            partner_stats[booking.user.id] += 1
            # И других партнеров
            for partner in booking.partners.all():
                if partner != user:
                    partner_stats[partner.id] += 1

    # Топ-5 партнеров
    sorted_partners = sorted(partner_stats.items(), key=lambda x: x[1], reverse=True)[:5]
    for partner_id, games_count in sorted_partners:
        try:
            partner = User.objects.get(id=partner_id)
            favorite_partners.append({
                'user': partner,
                'games_count': games_count,
                'full_name': f"{partner.first_name} {partner.last_name}".strip() or partner.username
            })
        except User.DoesNotExist:
            continue

    # Активность по месяцам (последние 12 месяцев)
    twelve_months_ago = today - timedelta(days=365)
    monthly_activity = completed_bookings.filter(
        date__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        games=Count('id')
    ).order_by('month')

    # Активность по дням недели
    weekday_activity = completed_bookings.annotate(
        weekday=ExtractWeekDay('date')
    ).values('weekday').annotate(
        games=Count('id')
    ).order_by('weekday')

    weekday_names = {
        1: 'Воскресенье',
        2: 'Понедельник',
        3: 'Вторник',
        4: 'Среда',
        5: 'Четверг',
        6: 'Пятница',
        7: 'Суббота'
    }

    weekday_stats = [
        {
            'day': weekday_names.get(item['weekday'], 'Неизвестно'),
            'games': item['games']
        }
        for item in weekday_activity
    ]

    # Прогресс рейтинга (если есть история)
    rating_progress = []
    current_rating = None

    try:
        player_rating = user.rating
        rating_history = player_rating.rating_history or []

        # Берем последние 10 изменений
        rating_progress = rating_history[-10:] if len(rating_history) > 10 else rating_history

        current_rating = {
            'numeric': float(player_rating.numeric_rating),
            'level': player_rating.level,
            'progress_percentage': player_rating.get_progress_percentage()
        }
    except (PlayerRating.DoesNotExist, AttributeError):
        current_rating = None
        rating_progress = []

    # Частота игр (среднее за последние 4 недели)
    four_weeks_ago = today - timedelta(weeks=4)
    recent_games = completed_bookings.filter(date__gte=four_weeks_ago).count()
    games_per_week = round(recent_games / 4, 1)

    # Достижения (простая система бейджей)
    achievements = _calculate_achievements(
        total_games,
        total_hours,
        len(favorite_partners),
        games_per_week
    )

    return {
        'total_games': total_games,
        'total_hours': round(total_hours, 1),
        'total_spent': round(total_spent, 2),
        'upcoming_games': upcoming_bookings.count(),
        'games_per_week': games_per_week,

        'favorite_court': favorite_court,
        'favorite_partners': favorite_partners,

        'monthly_activity': list(monthly_activity),
        'weekday_stats': weekday_stats,

        'current_rating': current_rating,
        'rating_progress': rating_progress,

        'achievements': achievements,
    }


def get_calendar_events(user, start_date, end_date):
    """
    Получить события для календаря в формате FullCalendar

    Args:
        user: Пользователь
        start_date: Начало периода
        end_date: Конец периода

    Returns:
        List событий в формате FullCalendar
    """
    bookings = Booking.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).select_related('court', 'user', 'user__profile').prefetch_related('partners')

    events = []

    for booking in bookings:
        # Определяем цвет в зависимости от статуса и отношения к пользователю
        is_my_booking = booking.user == user or user in booking.partners.all()

        if is_my_booking:
            if booking.status == 'confirmed':
                color = '#10b981'  # Зеленый - моё подтвержденное
            elif booking.status == 'pending':
                color = '#f59e0b'  # Оранжевый - моё ожидает
            else:
                color = '#6b7280'  # Серый - отменено
        else:
            if booking.status in ['pending', 'confirmed']:
                color = '#3b82f6'  # Синий - чужое
            else:
                continue  # Не показываем чужие отмененные

        # Формируем название
        creator_name = f"{booking.user.first_name} {booking.user.last_name}".strip() or booking.user.username

        if is_my_booking:
            title = f"🎾 {booking.court.name}"
            if booking.partners.exists():
                title += f" ({booking.partners.count() + 1} игроков)"
        else:
            title = f"Занято: {booking.court.name}"

        # Создаем datetime объекты
        start_datetime = timezone.make_aware(
            datetime.combine(booking.date, booking.start_time)
        )
        end_datetime = timezone.make_aware(
            datetime.combine(booking.date, booking.end_time)
        )

        event = {
            'id': booking.id,
            'title': title,
            'start': start_datetime.isoformat(),
            'end': end_datetime.isoformat(),
            'color': color,
            'extendedProps': {
                'bookingId': booking.id,
                'courtId': booking.court.id,
                'courtName': booking.court.name,
                'creatorName': creator_name,
                'status': booking.status,
                'price': float(booking.total_price),
                'isMine': is_my_booking,
                'canJoin': booking.looking_for_partner and not booking.is_full and not is_my_booking,
                'partnersCount': booking.partners.count(),
                'maxPlayers': booking.max_players,
            }
        }

        events.append(event)

    return events


def get_available_slots(court_id, date):
    """
    Получить доступные слоты для бронирования на конкретный день

    Args:
        court_id: ID корта
        date: Дата (date object)

    Returns:
        List доступных временных слотов
    """
    try:
        court = Court.objects.get(id=court_id)
    except Court.DoesNotExist:
        return []

    # Рабочие часы (можно вынести в настройки)
    WORKING_HOURS_START = 8
    WORKING_HOURS_END = 22
    SLOT_DURATION = 1  # часы

    # Получаем занятые слоты
    existing_bookings = Booking.objects.filter(
        court=court,
        date=date,
        status__in=['pending', 'confirmed']
    ).values('start_time', 'end_time')

    occupied_slots = []
    for booking in existing_bookings:
        start = booking['start_time'].hour + booking['start_time'].minute / 60
        end = booking['end_time'].hour + booking['end_time'].minute / 60
        occupied_slots.append((start, end))

    # Генерируем свободные слоты
    available_slots = []
    current_hour = WORKING_HOURS_START

    while current_hour < WORKING_HOURS_END:
        slot_start = current_hour
        slot_end = current_hour + SLOT_DURATION

        # Проверяем, не занят ли слот
        is_occupied = False
        for occupied_start, occupied_end in occupied_slots:
            if not (slot_end <= occupied_start or slot_start >= occupied_end):
                is_occupied = True
                break

        if not is_occupied:
            available_slots.append({
                'start': f"{int(slot_start):02d}:00",
                'end': f"{int(slot_end):02d}:00",
                'price': float(court.price_per_hour) * SLOT_DURATION
            })

        current_hour += SLOT_DURATION

    return available_slots


def get_admin_dashboard_stats():
    """
    Статистика для администратора
    """
    today = timezone.now().date()

    # Сегодняшние бронирования
    today_bookings = Booking.objects.filter(date=today)

    # Выручка за сегодня
    today_revenue = today_bookings.filter(
        status='confirmed'
    ).aggregate(
        total=Sum('court__price_per_hour')
    )['total'] or 0

    # Загруженность кортов (%)
    total_hours = (22 - 8)  # Рабочие часы
    courts_count = Court.objects.filter(is_available=True).count()
    total_possible_bookings = total_hours * courts_count

    actual_bookings = today_bookings.filter(status__in=['pending', 'confirmed']).count()
    occupancy_rate = round((actual_bookings / total_possible_bookings * 100) if total_possible_bookings > 0 else 0, 1)

    # Популярные времена
    popular_times = Booking.objects.filter(
        date__gte=today - timedelta(days=30),
        status='confirmed'
    ).annotate(
        hour=F('start_time__hour')
    ).values('hour').annotate(
        bookings=Count('id')
    ).order_by('-bookings')[:5]

    # Выручка по кортам (за месяц)
    revenue_by_court = Booking.objects.filter(
        date__gte=today - timedelta(days=30),
        status='confirmed'
    ).values(
        'court__name'
    ).annotate(
        revenue=Sum('court__price_per_hour'),
        bookings=Count('id')
    ).order_by('-revenue')

    # Новые пользователи за неделю
    new_users_week = User.objects.filter(
        date_joined__gte=today - timedelta(days=7)
    ).count()

    return {
        'today_bookings': today_bookings.count(),
        'today_revenue': float(today_revenue),
        'occupancy_rate': occupancy_rate,
        'popular_times': list(popular_times),
        'revenue_by_court': list(revenue_by_court),
        'new_users_this_week': new_users_week,
    }


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def _calculate_duration(booking):
    """Рассчитать продолжительность бронирования в часах"""
    start_dt = datetime.combine(booking.date, booking.start_time)
    end_dt = datetime.combine(booking.date, booking.end_time)

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    duration_seconds = (end_dt - start_dt).total_seconds()
    return duration_seconds / 3600


def _calculate_achievements(total_games, total_hours, partners_count, games_per_week):
    """
    Рассчитать достижения (бейджи) игрока

    Returns:
        List словарей с достижениями
    """
    achievements = []

    # Достижения по количеству игр
    game_milestones = [
        (1, "🎾 Первая игра", "Сыграли первую игру!", "bronze"),
        (10, "🏆 Новичок", "10 игр сыграно", "bronze"),
        (50, "⭐ Любитель", "50 игр сыграно", "silver"),
        (100, "💎 Профи", "100 игр сыграно", "gold"),
        (250, "👑 Мастер", "250 игр сыграно", "platinum"),
        (500, "🔥 Легенда", "500 игр сыграно", "diamond"),
    ]

    for threshold, title, description, badge_type in game_milestones:
        if total_games >= threshold:
            achievements.append({
                'title': title,
                'description': description,
                'type': badge_type,
                'unlocked': True,
                'progress': 100,
            })
        else:
            # Следующее достижение с прогрессом
            progress = int((total_games / threshold) * 100)
            achievements.append({
                'title': title,
                'description': description,
                'type': badge_type,
                'unlocked': False,
                'progress': progress,
            })
            break  # Показываем только следующее недостигнутое

    # Достижения по часам
    if total_hours >= 100:
        achievements.append({
            'title': "⏰ Марафонец",
            'description': f"{int(total_hours)} часов на корте",
            'type': 'gold',
            'unlocked': True,
            'progress': 100,
        })

    # Достижения по социальности
    if partners_count >= 10:
        achievements.append({
            'title': "🤝 Командный игрок",
            'description': f"Играли с {partners_count} разными партнерами",
            'type': 'silver',
            'unlocked': True,
            'progress': 100,
        })

    # Достижения по регулярности
    if games_per_week >= 3:
        achievements.append({
            'title': "🔥 Активист",
            'description': f"{games_per_week} игр в неделю",
            'type': 'gold',
            'unlocked': True,
            'progress': 100,
        })

    return achievements
