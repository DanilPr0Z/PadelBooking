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

    # Динамика дохода по дням
    daily_revenue = bookings.annotate(
        day=TruncDate('date')
    ).values('day').annotate(
        revenue=Sum(
            F('court__price_per_hour') *
            (F('end_time__hour') - F('start_time__hour')),
            output_field=DecimalField()
        ),
        bookings_count=Count('id')
    ).order_by('day')

    # Динамика по месяцам (последние 12)
    twelve_months_ago = today - timedelta(days=365)
    monthly_revenue = Booking.objects.filter(
        date__gte=twelve_months_ago,
        status='confirmed'
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        revenue=Sum(
            F('court__price_per_hour') *
            (F('end_time__hour') - F('start_time__hour')),
            output_field=DecimalField()
        ),
        bookings_count=Count('id')
    ).order_by('month')

    # Прогноз на следующий месяц (средний доход * 30 дней)
    days_in_period = max((end_date - start_date).days, 1)
    avg_daily_revenue = total_revenue / days_in_period
    forecast_next_month = avg_daily_revenue * 30

    # Топ источники дохода (корты)
    revenue_by_court = bookings.values(
        'court__id', 'court__name'
    ).annotate(
        revenue=Sum(
            F('court__price_per_hour') *
            (F('end_time__hour') - F('start_time__hour')),
            output_field=DecimalField()
        ),
        bookings_count=Count('id')
    ).order_by('-revenue')

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

    # Загруженность по кортам
    court_occupancy = bookings.values(
        'court__id', 'court__name'
    ).annotate(
        booked_hours=Sum(
            F('end_time__hour') - F('start_time__hour'),
            output_field=DecimalField()
        ),
        bookings_count=Count('id')
    ).order_by('-booked_hours')

    # Добавляем процент для каждого корта
    court_occupancy_list = []
    for court in court_occupancy:
        possible = WORKING_HOURS * days_in_period
        court['occupancy_rate'] = (float(court['booked_hours']) / possible * 100) if possible > 0 else 0
        court_occupancy_list.append(court)

    # Загруженность по часам (пиковые часы)
    hourly_occupancy = bookings.annotate(
        hour=ExtractHour('start_time')
    ).values('hour').annotate(
        bookings_count=Count('id')
    ).order_by('hour')

    # Загруженность по дням недели (0=Sunday, 1=Monday, etc.)
    weekday_occupancy = bookings.annotate(
        weekday=ExtractWeekDay('date')
    ).values('weekday').annotate(
        bookings_count=Count('id'),
        hours=Sum(
            F('end_time__hour') - F('start_time__hour'),
            output_field=DecimalField()
        )
    ).order_by('weekday')

    # Загруженность тренеров
    coach_occupancy = bookings.filter(
        coach__isnull=False
    ).values(
        'coach__id',
        'coach__first_name',
        'coach__last_name'
    ).annotate(
        sessions_count=Count('id'),
        total_hours=Sum(
            F('end_time__hour') - F('start_time__hour'),
            output_field=DecimalField()
        )
    ).order_by('-sessions_count')

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
