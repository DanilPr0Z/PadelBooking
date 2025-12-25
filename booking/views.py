# booking/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from datetime import datetime, timedelta
import logging
from .models import Court, Booking

from django.urls import reverse

logger = logging.getLogger(__name__)


# ========== ОСНОВНЫЕ VIEW ==========

def booking_page(request):
    """Страница бронирования кортов"""
    courts = Court.objects.filter(is_available=True).order_by('name')
    today_date = timezone.now().date()
    return render(request, 'booking.html', {
        'courts': courts,
        'today_date': today_date
    })


@require_GET
def get_available_slots(request):
    """
    API: возвращает слоты доступности для корта и даты
    ТОЛЬКО ОДИНОЧНЫЕ СЛОТЫ ПО 1 ЧАСУ
    """
    court_id = request.GET.get('court')
    date_str = request.GET.get('date')

    if not court_id or not date_str:
        return JsonResponse({
            'success': False,
            'message': 'Необходимо указать корт и дату'
        })

    try:
        court = Court.objects.filter(id=court_id, is_available=True).first()
        if not court:
            return JsonResponse({
                'success': False,
                'message': 'Корт не найден или недоступен'
            })

        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = timezone.now().date()

        if booking_date < today:
            return JsonResponse({
                'success': False,
                'message': 'Нельзя бронировать корт на прошедшую дату'
            })

        # Получаем существующие бронирования
        existing_bookings = Booking.objects.filter(
            court=court,
            date=booking_date,
            status__in=['pending', 'confirmed']
        )

        # Словарь занятых часов
        booked_hours = {}
        for booking in existing_bookings:
            start_hour = booking.start_time.hour
            end_hour = booking.end_time.hour
            for hour in range(start_hour, end_hour):
                booked_hours[hour] = True

        # Рабочие часы: 8:00 - 22:00
        WORKING_HOURS_START = 8
        WORKING_HOURS_END = 22

        all_slots = []
        current_hour = timezone.now().hour if booking_date == today else -1

        for hour in range(WORKING_HOURS_START, WORKING_HOURS_END):
            is_available = hour not in booked_hours

            # Если сегодня, нельзя бронировать прошедшее время
            if booking_date == today and hour < current_hour:
                is_available = False

            all_slots.append({
                'start_time': f"{hour:02d}:00",
                'end_time': f"{(hour + 1):02d}:00",
                'is_available': is_available,
                'duration': 1,
                'hour': hour
            })

        # Подсчет статистики
        available_count = sum(1 for slot in all_slots if slot['is_available'])

        result = {
            'success': True,
            'slots': all_slots,
            'court_price': float(court.price_per_hour),
            'court_name': court.name,
            'court_id': court.id,
            'date': date_str,
            'date_formatted': booking_date.strftime('%d.%m.%Y'),
            'available_count': available_count,
            'total_slots': len(all_slots)
        }

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in get_available_slots: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка загрузки слотов'
        }, status=500)


# booking/views.py
@login_required
@require_POST
def create_booking(request):
    """
    Создание бронирования БЕЗ ограничения в 3 слота в день
    """
    try:
        court_id = request.POST.get('court_id')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        duration = request.POST.get('duration', '1')

        if not all([court_id, date_str, start_time_str]):
            messages.error(request, 'Все поля должны быть заполнены')
            return redirect('booking')

        court = get_object_or_404(Court, id=court_id, is_available=True)

        # Парсим дату и время
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()

        # Рассчитываем end_time если не указан
        if not end_time_str and duration:
            hours = int(duration)
            end_hour = int(start_time_str.split(':')[0]) + hours
            end_time = datetime.strptime(f"{end_hour:02d}:00", '%H:%M').time()
        else:
            end_time = datetime.strptime(end_time_str, '%H:%M').time()

        today = timezone.now().date()
        current_time = timezone.now().time()

        # Валидация даты
        if booking_date < today:
            messages.error(request, 'Нельзя бронировать корт на прошедшую дату')
            return redirect('booking')

        if booking_date == today and start_time < current_time:
            messages.error(request, 'Нельзя бронировать корт на прошедшее время сегодня')
            return redirect('booking')

        # Проверка времени
        if end_time <= start_time:
            messages.error(request, 'Время окончания должно быть позже времени начала')
            return redirect('booking')

        # Проверка продолжительности
        start_dt = datetime.combine(booking_date, start_time)
        end_dt = datetime.combine(booking_date, end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        if duration_hours < 1:
            messages.error(request, 'Минимальная продолжительность бронирования - 1 час')
            return redirect('booking')

        if duration_hours > 3:
            messages.error(request, 'Максимальная продолжительность бронирования - 3 часа')
            return redirect('booking')

        # Проверка рабочих часов
        WORKING_HOURS_START = datetime.strptime('08:00', '%H:%M').time()
        WORKING_HOURS_END = datetime.strptime('22:00', '%H:%M').time()

        if start_time < WORKING_HOURS_START or end_time > WORKING_HOURS_END:
            messages.error(request, 'Бронирование доступно только с 08:00 до 22:00')
            return redirect('booking')

        # УБРАН ЛИМИТ НА 3 СЛОТА В ДЕНЬ!
        # Пользователь может бронировать сколько угодно слотов

        # Проверка пересечений
        with transaction.atomic():
            existing_bookings = Booking.objects.select_for_update().filter(
                court=court,
                date=booking_date,
                status__in=['pending', 'confirmed']
            )

            for booking in existing_bookings:
                if (booking.start_time <= start_time < booking.end_time or
                        booking.start_time < end_time <= booking.end_time or
                        (start_time <= booking.start_time and end_time >= booking.end_time)):
                    conflict_start = booking.start_time.strftime('%H:%M')
                    conflict_end = booking.end_time.strftime('%H:%M')

                    messages.error(
                        request,
                        f'Выбранное время уже занято с {conflict_start} до {conflict_end}'
                    )
                    return redirect('booking')

            # Создаем бронирование
            booking = Booking.objects.create(
                user=request.user,
                court=court,
                date=booking_date,
                start_time=start_time,
                end_time=end_time,
                status='pending'
            )

        # Очищаем кэш
        clear_slots_cache(court_id=court_id, date_str=date_str)

        # КРАСИВОЕ УВЕДОМЛЕНИЕ (будет показано через showMessage из main.js)
        duration_hours_int = int(duration_hours)

        if duration_hours_int == 1:
            duration_text = "1 час"
        elif 2 <= duration_hours_int <= 4:
            duration_text = f"{duration_hours_int} часа"
        else:
            duration_text = f"{duration_hours_int} часов"

        # ПРОСТОЕ СООБЩЕНИЕ (фронтенд сам сделает красивое)
        success_message = f'Бронирование успешно создано! {court.name}, {booking_date.strftime("%d.%m.%Y")}, {start_time_str}-{end_time.strftime("%H:%M")}, {duration_text}, {int(booking.total_price)} руб.'

        messages.success(request, success_message)

        # Редирект
        return redirect(f"{reverse('profile')}?tab=bookings")

    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}", exc_info=True)
        messages.error(request, f'Ошибка при бронировании: {str(e)}')
        return redirect('booking')


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Отмена бронирования"""
    try:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)

        if booking.status == 'cancelled':
            return JsonResponse({
                'success': False,
                'message': 'Это бронирование уже отменено'
            })

        today = timezone.now().date()
        if booking.date < today:
            return JsonResponse({
                'success': False,
                'message': 'Нельзя отменить прошедшее бронирование'
            })

        # Проверяем время (нельзя отменить менее чем за 1 час до начала)
        if booking.date == today:
            current_time = timezone.now().time()
            time_until_start = datetime.combine(today, booking.start_time) - datetime.combine(today, current_time)
            if time_until_start.total_seconds() < 3600:
                return JsonResponse({
                    'success': False,
                    'message': 'Нельзя отменить бронирование менее чем за 1 час до начала'
                })

        # Сохраняем данные для очистки кэша
        court_id = booking.court.id
        date_str = booking.date.strftime('%Y-%m-%d')

        # Отменяем бронирование
        booking.status = 'cancelled'
        booking.save()

        # Очищаем кэш
        clear_slots_cache(court_id=court_id, date_str=date_str)

        logger.info(f"Booking {booking_id} cancelled by user {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': 'Бронирование успешно отменено',
            'booking_id': booking_id
        })

    except Exception as e:
        logger.error(f"Error cancelling booking {booking_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при отмене бронирования'
        })


@login_required
@require_POST
def confirm_booking(request, booking_id):
    """Подтверждение бронирования за 24 часа до начала"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status != 'pending':
        return JsonResponse({
            'success': False,
            'message': 'Это бронирование уже подтверждено или отменено'
        })

    if not booking.can_confirm:
        return JsonResponse({
            'success': False,
            'message': f'Подтверждение возможно только за 24 часа до начала. Доступно через {booking.hours_until_confirmation} ч.'
        })

    if booking.confirm():
        return JsonResponse({
            'success': True,
            'message': 'Бронирование успешно подтверждено!'
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Не удалось подтвердить бронирование'
        })


@login_required
@require_GET
def get_booking_info(request, booking_id):
    """Получить информацию о бронировании"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    return JsonResponse({
        'success': True,
        'booking': {
            'id': booking.id,
            'court_name': booking.court.name,
            'date': booking.date.strftime('%d.%m.%Y'),
            'time': f"{booking.start_time.strftime('%H:%M')} - {booking.end_time.strftime('%H:%M')}",
            'price': booking.total_price,
            'status': booking.status,
            'can_confirm': booking.can_confirm
        }
    })


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def clear_slots_cache(court_id=None, date_str=None):
    """Очистка кэша слотов"""
    try:
        if court_id and date_str:
            cache.delete(f'slots_{court_id}_{date_str}')
            cache.delete(f'court_{court_id}')

        elif court_id:
            today = timezone.now().date()
            keys_to_delete = []

            for i in range(90):
                future_date = today + timedelta(days=i)
                date_key = future_date.strftime('%Y-%m-%d')
                keys_to_delete.append(f'slots_{court_id}_{date_key}')

            for i in range(0, len(keys_to_delete), 100):
                cache.delete_many(keys_to_delete[i:i + 100])

            cache.delete(f'court_{court_id}')

    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")


# ========== ПРОВЕРКА ДОСТУПНОСТИ ==========

@login_required
@require_POST
def check_availability(request):
    """Проверка доступности слота перед бронированием (AJAX)"""
    try:
        court_id = request.POST.get('court_id')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        duration = request.POST.get('duration', '1')

        if not all([court_id, date_str, start_time_str]):
            return JsonResponse({
                'success': False,
                'message': 'Все поля обязательны'
            })

        court = get_object_or_404(Court, id=court_id)
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()

        # Рассчитываем end_time
        hours = int(duration)
        end_hour = int(start_time_str.split(':')[0]) + hours
        end_time = datetime.strptime(f"{end_hour:02d}:00", '%H:%M').time()

        # Проверяем существующие бронирования
        existing_bookings = Booking.objects.filter(
            court=court,
            date=booking_date,
            status__in=['pending', 'confirmed']
        )

        for booking in existing_bookings:
            if (booking.start_time <= start_time < booking.end_time or
                    booking.start_time < end_time <= booking.end_time or
                    (start_time <= booking.start_time and end_time >= booking.end_time)):
                return JsonResponse({
                    'success': False,
                    'available': False,
                    'message': 'Выбранное время уже занято'
                })

        return JsonResponse({
            'success': True,
            'available': True,
            'message': 'Время доступно для бронирования'
        })

    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при проверке доступности'
        })