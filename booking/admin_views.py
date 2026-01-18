"""
Кастомные views для админ-панели бронирований
Расписание кортов, API для drag-and-drop
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
import json

from .models import Booking, Court, BookingHistory
from django.contrib.auth.models import User


@staff_member_required
def courts_schedule_view(request):
    """
    Недельное расписание всех кортов
    """
    # Получаем параметры
    week_start_str = request.GET.get('week_start')

    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        # Начало текущей недели (понедельник)
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    # Получаем все корты
    courts = Court.objects.filter(is_available=True).order_by('name')

    context = {
        'courts': courts,
        'week_start': week_start,
        'week_end': week_end,
        'prev_week': (week_start - timedelta(days=7)).isoformat(),
        'next_week': (week_start + timedelta(days=7)).isoformat(),
    }

    return render(request, 'admin_custom/schedule/courts_schedule.html', context)


@staff_member_required
@require_http_methods(["GET"])
def bookings_list_api(request):
    """
    API: Получить список бронирований для календаря
    GET /admin-panel/schedule/api/bookings/?start=2024-01-01&end=2024-01-07
    """
    try:
        start_date_str = request.GET.get('start')
        end_date_str = request.GET.get('end')

        if not start_date_str or not end_date_str:
            return JsonResponse({'error': 'start and end parameters are required'}, status=400)

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Фильтры
        status_filter = request.GET.get('status')  # pending, confirmed, cancelled
        court_id = request.GET.get('court_id')

        bookings_qs = Booking.objects.filter(
            date__range=[start_date, end_date]
        ).select_related('user', 'court', 'coach').prefetch_related('partners')

        if status_filter:
            bookings_qs = bookings_qs.filter(status=status_filter)

        if court_id:
            bookings_qs = bookings_qs.filter(court_id=court_id)

        # Сериализация для FullCalendar
        events = []
        for booking in bookings_qs:
            # Строим datetime для start и end
            start_datetime = datetime.combine(booking.date, booking.start_time)
            end_datetime = datetime.combine(booking.date, booking.end_time)

            # Цвета по статусам
            color_map = {
                'pending': '#fbbf24',  # желтый
                'confirmed': '#9ef01a',  # зеленый
                'cancelled': '#ef4444',  # красный
                'completed': '#6b7280',  # серый
            }

            event = {
                'id': booking.id,
                'resourceId': str(booking.court.id),  # Для resource view
                'title': f"{booking.user.get_full_name() or booking.user.username}",
                'start': start_datetime.isoformat(),
                'end': end_datetime.isoformat(),
                'backgroundColor': color_map.get(booking.status, '#3b82f6'),
                'borderColor': color_map.get(booking.status, '#3b82f6'),
                'extendedProps': {
                    'booking_id': booking.id,
                    'court_name': booking.court.name,
                    'user_name': booking.user.get_full_name() or booking.user.username,
                    'status': booking.status,
                    'total_price': str(booking.total_price),
                    'coach_name': booking.coach.get_full_name() if booking.coach else None,
                    'partners_count': booking.partners.count(),
                }
            }
            events.append(event)

        return JsonResponse(events, safe=False)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in bookings_list_api: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["POST"])
def booking_quick_create_api(request):
    """
    API: Быстрое создание бронирования (клик по пустой ячейке)
    POST /admin-panel/schedule/api/booking/create/
    Body: {
        court_id, user_id, date, start_time, end_time, status
    }
    """
    try:
        data = json.loads(request.body)

        # Валидация обязательных полей
        required_fields = ['court_id', 'user_id', 'date', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return JsonResponse({'error': f'{field} is required'}, status=400)

        # Получаем объекты
        court = get_object_or_404(Court, id=data['court_id'])
        user = get_object_or_404(User, id=data['user_id'])

        # Парсим дату и время
        booking_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        end_time = datetime.strptime(data['end_time'], '%H:%M').time()

        # Проверка пересечений
        overlapping = Booking.objects.filter(
            court=court,
            date=booking_date,
            status__in=['pending', 'confirmed']
        ).filter(
            Q(start_time__lt=end_time, end_time__gt=start_time)
        )

        if overlapping.exists():
            return JsonResponse({
                'error': 'Это время уже занято'
            }, status=400)

        # Создаем бронирование
        booking = Booking.objects.create(
            user=user,
            court=court,
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            status=data.get('status', 'confirmed'),
            booking_type=data.get('booking_type', 'regular'),
        )

        # Добавляем тренера если указан
        if 'coach_id' in data and data['coach_id']:
            coach = get_object_or_404(User, id=data['coach_id'])
            booking.coach = coach
            booking.save()

        # Логируем в историю
        BookingHistory.objects.create(
            booking=booking,
            changed_by=request.user,
            action='created',
            field_name='status',
            old_value='',
            new_value=booking.status
        )

        return JsonResponse({
            'success': True,
            'booking_id': booking.id,
            'message': 'Бронирование создано'
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in booking_quick_create_api: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["PATCH", "PUT"])
def booking_update_api(request, booking_id):
    """
    API: Обновление бронирования (drag-and-drop)
    PATCH /admin-panel/schedule/api/booking/<id>/update/
    Body: {
        date?, start_time?, end_time?, court_id?, status?
    }
    """
    try:
        booking = get_object_or_404(Booking, id=booking_id)
        data = json.loads(request.body)

        # Сохраняем старые значения для истории
        old_values = {
            'date': booking.date,
            'start_time': booking.start_time,
            'end_time': booking.end_time,
            'court': booking.court,
            'status': booking.status,
        }

        # Обновляем поля
        if 'date' in data:
            booking.date = datetime.strptime(data['date'], '%Y-%m-%d').date()

        if 'start_time' in data:
            booking.start_time = datetime.strptime(data['start_time'], '%H:%M').time()

        if 'end_time' in data:
            booking.end_time = datetime.strptime(data['end_time'], '%H:%M').time()

        if 'court_id' in data:
            booking.court = get_object_or_404(Court, id=data['court_id'])

        if 'status' in data:
            booking.status = data['status']

        # Проверка пересечений (исключая само бронирование)
        overlapping = Booking.objects.filter(
            court=booking.court,
            date=booking.date,
            status__in=['pending', 'confirmed']
        ).exclude(id=booking.id).filter(
            Q(start_time__lt=booking.end_time, end_time__gt=booking.start_time)
        )

        if overlapping.exists():
            return JsonResponse({
                'error': 'Это время уже занято'
            }, status=400)

        booking.save()

        # Логируем изменения
        for field, old_value in old_values.items():
            new_value = getattr(booking, field)
            if old_value != new_value:
                BookingHistory.objects.create(
                    booking=booking,
                    changed_by=request.user,
                    action='updated',
                    field_name=field,
                    old_value=str(old_value),
                    new_value=str(new_value)
                )

        return JsonResponse({
            'success': True,
            'message': 'Бронирование обновлено'
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in booking_update_api: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["DELETE"])
def booking_delete_api(request, booking_id):
    """
    API: Отмена бронирования
    DELETE /admin-panel/schedule/api/booking/<id>/delete/
    """
    try:
        booking = get_object_or_404(Booking, id=booking_id)

        # Логируем перед удалением
        BookingHistory.objects.create(
            booking=booking,
            changed_by=request.user,
            action='cancelled',
            field_name='status',
            old_value=booking.status,
            new_value='cancelled'
        )

        # Меняем статус вместо удаления
        booking.status = 'cancelled'
        booking.save()

        return JsonResponse({
            'success': True,
            'message': 'Бронирование отменено'
        })

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in booking_delete_api: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def coach_schedule_view(request, coach_id):
    """
    Расписание конкретного тренера
    """
    coach = get_object_or_404(User, id=coach_id)

    # Проверяем что это действительно тренер
    if not hasattr(coach, 'coach_profile'):
        return JsonResponse({'error': 'Это не тренер'}, status=400)

    # Получаем параметры
    week_start_str = request.GET.get('week_start')

    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    context = {
        'coach': coach,
        'week_start': week_start,
        'week_end': week_end,
        'prev_week': (week_start - timedelta(days=7)).isoformat(),
        'next_week': (week_start + timedelta(days=7)).isoformat(),
    }

    return render(request, 'admin_custom/schedule/coach_schedule.html', context)
