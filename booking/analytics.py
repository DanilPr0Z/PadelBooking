"""
Аналитика для админ-панели по бронированиям
Финансы, загруженность, операционные метрики
"""

from django.db.models import Count, Sum, Avg, Q, F, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour, ExtractWeekDay
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Booking, Court, Payment


def get_financial_stats(start_date=None, end_date=None):
    """
    Финансовая статистика

    Returns:
        - Доход (revenue)
        - Прибыль (profit)
        - Прогнозы (forecast)
        - Динамика по дням/месяцам
    """
    today = timezone.now().date()

    if not start_date:
        start_date = today - timedelta(days=30)
    if not end_date:
        end_date = today

    # Подтвержденные бронирования за период
    bookings = Booking.objects.filter(
        date__range=[start_date, end_date],
        status='confirmed'
    ).select_related('court')

    # Общий доход
    total_revenue = sum(float(booking.total_price) for booking in bookings)

    # Оплаченные платежи
    paid_payments = Payment.objects.filter(
        booking__date__range=[start_date, end_date],
        status='paid'
    ).aggregate(
        total_paid=Sum('amount'),
        avg_payment=Avg('amount'),
        count=Count('id')
    )

    # Динамика дохода по дням (вычисляем в Python из-за ограничений SQLite)
    daily_data = {}
    for booking in bookings:
        day = booking.date
        hours = (booking.end_time.hour - booking.start_time.hour)
        revenue = float(booking.court.price_per_hour) * hours

        if day not in daily_data:
            daily_data[day] = {'day': day, 'revenue': 0, 'bookings_count': 0}
        daily_data[day]['revenue'] += revenue
        daily_data[day]['bookings_count'] += 1

    daily_revenue = sorted(daily_data.values(), key=lambda x: x['day'])

    # Динамика по месяцам (последние 12) - также вычисляем в Python
    twelve_months_ago = today - timedelta(days=365)
    monthly_bookings = Booking.objects.filter(
        date__gte=twelve_months_ago,
        status='confirmed'
    ).select_related('court').order_by('date')

    monthly_data = {}
    for booking in monthly_bookings:
        month = booking.date.replace(day=1)  # Первый день месяца
        hours = (booking.end_time.hour - booking.start_time.hour)
        revenue = float(booking.court.price_per_hour) * hours

        if month not in monthly_data:
            monthly_data[month] = {'month': month, 'revenue': 0, 'bookings_count': 0}
        monthly_data[month]['revenue'] += revenue
        monthly_data[month]['bookings_count'] += 1

    monthly_revenue = sorted(monthly_data.values(), key=lambda x: x['month'])

    # Прогноз на следующий месяц (средний доход * 30 дней)
    days_in_period = max((end_date - start_date).days, 1)
    avg_daily_revenue = total_revenue / days_in_period
    forecast_next_month = avg_daily_revenue * 30

    # Топ источники дохода (корты) - вычисляем в Python
    court_data = {}
    for booking in bookings:
        court_id = booking.court.id
        court_name = booking.court.name
        hours = (booking.end_time.hour - booking.start_time.hour)
        revenue = float(booking.court.price_per_hour) * hours

        if court_id not in court_data:
            court_data[court_id] = {
                'court__id': court_id,
                'court__name': court_name,
                'revenue': 0,
                'bookings_count': 0
            }
        court_data[court_id]['revenue'] += revenue
        court_data[court_id]['bookings_count'] += 1

    revenue_by_court = sorted(court_data.values(), key=lambda x: x['revenue'], reverse=True)

    return {
        'total_revenue': float(total_revenue),
        'paid_amount': float(paid_payments['total_paid'] or 0),
        'unpaid_amount': float(total_revenue - (paid_payments['total_paid'] or 0)),
        'avg_payment': float(paid_payments['avg_payment'] or 0),
        'payments_count': paid_payments['count'],

        'daily_revenue': list(daily_revenue),
        'monthly_revenue': list(monthly_revenue),

        'forecast_next_month': float(forecast_next_month),
        'avg_daily_revenue': float(avg_daily_revenue),

        'revenue_by_court': list(revenue_by_court),

        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': days_in_period
        }
    }


def get_occupancy_stats(start_date=None, end_date=None):
    """
    Статистика загруженности кортов и тренеров
    """
    today = timezone.now().date()

    if not start_date:
        start_date = today - timedelta(days=30)
    if not end_date:
        end_date = today

    # Всего возможных часов (8:00-22:00 = 14 часов)
    WORKING_HOURS = 14
    days_in_period = (end_date - start_date).days + 1
    courts_count = Court.objects.filter(is_available=True).count()

    total_possible_hours = WORKING_HOURS * days_in_period * courts_count

    # Занятые часы
    bookings = Booking.objects.filter(
        date__range=[start_date, end_date],
        status__in=['pending', 'confirmed']
    ).select_related('court')

    total_booked_hours = sum(
        (booking.end_time.hour - booking.start_time.hour)
        for booking in bookings
    )

    # Процент загруженности
    occupancy_rate = (total_booked_hours / total_possible_hours * 100) if total_possible_hours > 0 else 0

    # Загруженность по кортам - вычисляем в Python
    court_stats = {}
    for booking in bookings:
        court_id = booking.court.id
        court_name = booking.court.name
        hours = (booking.end_time.hour - booking.start_time.hour)

        if court_id not in court_stats:
            court_stats[court_id] = {
                'court__id': court_id,
                'court__name': court_name,
                'booked_hours': 0,
                'bookings_count': 0
            }
        court_stats[court_id]['booked_hours'] += hours
        court_stats[court_id]['bookings_count'] += 1

    # Добавляем процент для каждого корта
    court_occupancy_list = []
    for court in court_stats.values():
        possible = WORKING_HOURS * days_in_period
        court['occupancy_rate'] = (court['booked_hours'] / possible * 100) if possible > 0 else 0
        court_occupancy_list.append(court)

    court_occupancy_list.sort(key=lambda x: x['booked_hours'], reverse=True)

    # Загруженность по часам (пиковые часы) - вычисляем в Python
    hourly_stats = {}
    for booking in bookings:
        hour = booking.start_time.hour
        if hour not in hourly_stats:
            hourly_stats[hour] = {'hour': hour, 'bookings_count': 0}
        hourly_stats[hour]['bookings_count'] += 1

    hourly_occupancy = sorted(hourly_stats.values(), key=lambda x: x['hour'])

    # Загруженность по дням недели - вычисляем в Python
    weekday_stats = {}
    for booking in bookings:
        weekday = booking.date.isoweekday()  # 1=Monday, 7=Sunday
        hours = (booking.end_time.hour - booking.start_time.hour)

        if weekday not in weekday_stats:
            weekday_stats[weekday] = {'weekday': weekday, 'bookings_count': 0, 'hours': 0}
        weekday_stats[weekday]['bookings_count'] += 1
        weekday_stats[weekday]['hours'] += hours

    weekday_occupancy = sorted(weekday_stats.values(), key=lambda x: x['weekday'])

    # Загруженность тренеров - вычисляем в Python
    coach_stats = {}
    for booking in bookings.filter(coach__isnull=False):
        coach_id = booking.coach.id
        hours = (booking.end_time.hour - booking.start_time.hour)

        if coach_id not in coach_stats:
            coach_stats[coach_id] = {
                'coach__id': coach_id,
                'coach__first_name': booking.coach.first_name,
                'coach__last_name': booking.coach.last_name,
                'sessions_count': 0,
                'total_hours': 0
            }
        coach_stats[coach_id]['sessions_count'] += 1
        coach_stats[coach_id]['total_hours'] += hours

    coach_occupancy = sorted(coach_stats.values(), key=lambda x: x['sessions_count'], reverse=True)

    return {
        'overall_occupancy_rate': round(occupancy_rate, 2),
        'total_booked_hours': total_booked_hours,
        'total_possible_hours': total_possible_hours,
        'total_bookings': bookings.count(),

        'court_occupancy': court_occupancy_list,
        'hourly_occupancy': list(hourly_occupancy),
        'weekday_occupancy': list(weekday_occupancy),
        'coach_occupancy': list(coach_occupancy),

        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': days_in_period
        }
    }


def get_clients_stats(start_date=None, end_date=None):
    """
    Статистика клиентов

    Returns:
        - Активность клиентов
        - Удержание (retention)
        - LTV (Lifetime Value)
    """
    from django.contrib.auth.models import User

    today = timezone.now().date()

    if not start_date:
        start_date = today - timedelta(days=30)
    if not end_date:
        end_date = today

    # Новые пользователи за период
    new_users = User.objects.filter(
        date_joined__date__range=[start_date, end_date]
    ).count()

    # Активные пользователи (сделали хотя бы одно бронирование)
    active_users = User.objects.filter(
        Q(bookings_created__date__range=[start_date, end_date]) |
        Q(bookings_as_partner__date__range=[start_date, end_date])
    ).distinct().count()

    # Топ активные клиенты
    top_clients_qs = User.objects.filter(
        Q(bookings_created__date__range=[start_date, end_date]) |
        Q(bookings_as_partner__date__range=[start_date, end_date])
    ).annotate(
        bookings_count=Count('bookings_created', distinct=True) + Count('bookings_as_partner', distinct=True)
    ).order_by('-bookings_count')[:10]

    top_clients = []
    for user in top_clients_qs:
        # Считаем потраченные деньги
        user_bookings = Booking.objects.filter(
            user=user,
            date__range=[start_date, end_date],
            status='confirmed'
        )
        total_spent = sum(float(b.total_price) for b in user_bookings)

        top_clients.append({
            'id': user.id,
            'name': user.get_full_name() or user.username,
            'bookings_count': user.bookings_count,
            'total_spent': total_spent
        })

    # LTV (средняя сумма потраченная пользователем)
    all_users_with_bookings = User.objects.filter(
        bookings_created__date__range=[start_date, end_date],
        bookings_created__status='confirmed'
    ).distinct()

    total_ltv = 0
    users_count = 0
    for user in all_users_with_bookings:
        user_bookings = Booking.objects.filter(
            user=user,
            date__range=[start_date, end_date],
            status='confirmed'
        )
        total_ltv += sum(float(b.total_price) for b in user_bookings)
        users_count += 1

    avg_ltv = (total_ltv / users_count) if users_count > 0 else 0

    # Retention (повторные бронирования)
    users_with_multiple_bookings = User.objects.filter(
        bookings_created__date__range=[start_date, end_date]
    ).annotate(
        bookings_count=Count('bookings_created')
    ).filter(bookings_count__gt=1).count()

    retention_rate = (users_with_multiple_bookings / active_users * 100) if active_users > 0 else 0

    # Распределение по частоте игр
    frequency_distribution = User.objects.filter(
        bookings_created__date__range=[start_date, end_date]
    ).annotate(
        bookings_count=Count('bookings_created')
    ).values('bookings_count').annotate(
        users_count=Count('id')
    ).order_by('bookings_count')

    return {
        'new_users': new_users,
        'active_users': active_users,
        'top_clients': top_clients,

        'avg_ltv': float(avg_ltv),
        'retention_rate': round(retention_rate, 2),
        'users_with_multiple_bookings': users_with_multiple_bookings,

        'frequency_distribution': list(frequency_distribution),

        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': (end_date - start_date).days
        }
    }
