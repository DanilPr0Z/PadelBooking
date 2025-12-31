from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from datetime import datetime, timedelta
from django.urls import reverse
from django.db.models import Q
from .models import Court, Booking
import traceback


import logging
logger = logging.getLogger(__name__)


from django.utils.html import escape

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
    court_id = request.GET.get('court')
    date_str = request.GET.get('date')

    print(f"🔍 DEBUG: get_available_slots called with court={court_id}, date={date_str}")
    print(f"🔍 DEBUG: Current time: {timezone.now().time()}")

    if not court_id or not date_str:
        return JsonResponse({
            'success': False,
            'message': 'Необходимо указать корт и дату'
        })

    try:
        court = Court.objects.filter(id=court_id, is_available=True).first()
        if not court:
            print(f"❌ DEBUG: Court not found or not available: {court_id}")
            return JsonResponse({
                'success': False,
                'message': 'Корт не найден или недоступен'
            })

        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = timezone.now().date()
        current_time = timezone.now().time()

        print(f"🔍 DEBUG: booking_date={booking_date}, today={today}")
        print(f"🔍 DEBUG: current_time={current_time}")

        if booking_date < today:
            print(f"❌ DEBUG: Booking date is in the past: {booking_date}")
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

        print(f"🔍 DEBUG: Found {existing_bookings.count()} existing bookings")

        # Словарь занятых часов
        booked_hours = {}
        for booking in existing_bookings:
            start_hour = booking.start_time.hour
            end_hour = booking.end_time.hour
            for hour in range(start_hour, end_hour):
                booked_hours[hour] = True
            print(f"🔍 DEBUG: Booking from {start_hour}:00 to {end_hour}:00")

        # Рабочие часы: 8:00 - 22:00
        WORKING_HOURS_START = 8
        WORKING_HOURS_END = 22

        all_slots = []

        # Только если сегодняшняя дата
        if booking_date == today:
            current_hour = current_time.hour
            print(f"🔍 DEBUG: Today! Current hour: {current_hour}")
        else:
            current_hour = -1  # Будущая дата, все часы доступны
            print(f"🔍 DEBUG: Future date! All hours available")

        for hour in range(WORKING_HOURS_START, WORKING_HOURS_END):
            is_available = hour not in booked_hours

            # Если сегодня, нельзя бронировать прошедшее время
            if booking_date == today and hour < current_hour:
                is_available = False
                print(f"🔍 DEBUG: Hour {hour}:00 is in the past (current hour: {current_hour})")

            all_slots.append({
                'start_time': f"{hour:02d}:00",
                'end_time': f"{(hour + 1):02d}:00",
                'is_available': is_available,
                'duration': 1,
                'hour': hour
            })

        # Подсчет статистики
        available_count = sum(1 for slot in all_slots if slot['is_available'])

        print(f"🔍 DEBUG: Available slots: {available_count}/{len(all_slots)}")
        print(f"🔍 DEBUG: Booked hours dict: {booked_hours}")

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

        print(f"✅ DEBUG: Returning JSON response with {len(all_slots)} slots")
        print(f"✅ DEBUG: Slots availability: {[(s['start_time'], s['is_available']) for s in all_slots]}")

        response = JsonResponse(result)
        response['Content-Type'] = 'application/json; charset=utf-8'
        return response

    except Exception as e:
        print(f"🔥 ERROR in get_available_slots: {str(e)}")
        print(f"🔥 ERROR traceback: {traceback.format_exc()}")

        logger.error(f"Error in get_available_slots: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка загрузки слотов'
        }, status=500)

@login_required
@require_POST
def create_booking(request):
    """
    Создание бронирования с КРАСИВЫМ HTML сообщением
    БЕЗ ограничения на количество слотов в день
    """
    try:
        court_id = request.POST.get('court_id')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        duration = request.POST.get('duration', '1')

        # Валидация обязательных полей
        if not all([court_id, date_str, start_time_str]):
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Все поля должны быть заполнены
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
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

        # 1. Валидация даты
        if booking_date < today:
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Нельзя бронировать корт на прошедшую дату
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
            return redirect('booking')

        # Если сегодня, проверяем время
        if booking_date == today and start_time < current_time:
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Нельзя бронировать корт на прошедшее время сегодня
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
            return redirect('booking')

        # 2. Проверка времени
        if end_time <= start_time:
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Время окончания должно быть позже времени начала
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
            return redirect('booking')

        # 3. Проверка продолжительности
        start_dt = datetime.combine(booking_date, start_time)
        end_dt = datetime.combine(booking_date, end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        if duration_hours < 1:
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Минимальная продолжительность бронирования - 1 час
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
            return redirect('booking')

        if duration_hours > 3:
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Максимальная продолжительность бронирования - 3 часа
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
            return redirect('booking')

        # 4. Проверка рабочих часов
        WORKING_HOURS_START = datetime.strptime('08:00', '%H:%M').time()
        WORKING_HOURS_END = datetime.strptime('22:00', '%H:%M').time()

        if start_time < WORKING_HOURS_START or end_time > WORKING_HOURS_END:
            error_html = '''
            <div style="display: flex; align-items: center; gap: 12px;">
                <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                <div>
                    <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                        ❌ Ошибка
                    </div>
                    <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                        Бронирование доступно только с 08:00 до 22:00
                    </div>
                </div>
            </div>
            '''
            messages.error(request, error_html)
            return redirect('booking')

        # 5. УБРАН ЛИМИТ НА КОЛИЧЕСТВО СЛОТОВ В ДЕНЬ!
        # Пользователь может бронировать сколько угодно

        # 6. Проверка пересечений с существующими бронированиями
        with transaction.atomic():
            existing_bookings = Booking.objects.select_for_update().filter(
                court=court,
                date=booking_date,
                status__in=['pending', 'confirmed']
            )

            # Проверяем пересечение по времени
            for booking in existing_bookings:
                if (booking.start_time <= start_time < booking.end_time or
                        booking.start_time < end_time <= booking.end_time or
                        (start_time <= booking.start_time and end_time >= booking.end_time)):
                    conflict_start = booking.start_time.strftime('%H:%M')
                    conflict_end = booking.end_time.strftime('%H:%M')

                    error_html = f'''
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
                        <div>
                            <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                                ❌ Время занято
                            </div>
                            <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                                Выбранное время уже занято с {conflict_start} до {conflict_end}
                            </div>
                        </div>
                    </div>
                    '''

                    messages.error(request, error_html)
                    return redirect('booking')

            # 7. Создаем бронирование
            booking = Booking.objects.create(
                user=request.user,
                court=court,
                date=booking_date,
                start_time=start_time,
                end_time=end_time,
                status='pending'
            )

        # 8. Очищаем кэш слотов
        clear_slots_cache(court_id=court_id, date_str=date_str)

        # 9. Логируем
        logger.info(
            f"Booking created: User {request.user.username} booked court {court.name} "
            f"on {booking_date} from {start_time_str} to {end_time.strftime('%H:%M')} "
            f"(Duration: {duration_hours}h, Price: {booking.total_price} руб.)"
        )

        # 10. КРАСИВОЕ HTML СООБЩЕНИЕ ДЛЯ УВЕДОМЛЕНИЯ
        duration_hours_int = int(duration_hours)

        # Правильное склонение
        if duration_hours_int == 1:
            duration_text = "1 час"
        elif 2 <= duration_hours_int <= 4:
            duration_text = f"{duration_hours_int} часа"
        else:
            duration_text = f"{duration_hours_int} часов"

        success_html = f'''
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <i class="fas fa-check-circle" style="font-size: 24px; color: white;"></i>
            <div style="flex: 1;">
                <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 8px;">
                    🎉 Бронирование успешно создано!
                </div>
                <div style="background: rgba(255,255,255,0.15); padding: 12px; border-radius: 8px;">
                    <div style="display: grid; grid-template-columns: auto 1fr; gap: 8px 15px; align-items: center;">
                        <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                            <i class="fas fa-court-sport"></i> Корт:
                        </div>
                        <div style="font-weight: bold; color: white; font-size: 14px;">{court.name}</div>

                        <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                            <i class="fas fa-calendar"></i> Дата:
                        </div>
                        <div style="font-weight: bold; color: white; font-size: 14px;">{booking_date.strftime("%d.%m.%Y")}</div>

                        <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                            <i class="fas fa-clock"></i> Время:
                        </div>
                        <div style="font-weight: bold; color: white; font-size: 14px;">{start_time_str} - {end_time.strftime("%H:%M")}</div>

                        <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                            <i class="fas fa-hourglass"></i> Продолжительность:
                        </div>
                        <div style="font-weight: bold; color: white; font-size: 14px;">{duration_text}</div>

                        <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                            <i class="fas fa-tag"></i> Стоимость:
                        </div>
                        <div style="font-weight: bold; color: white; font-size: 14px;">{int(booking.total_price)} руб.</div>
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: rgba(255,255,255,0.8);">
                    <i class="fas fa-info-circle"></i> Вы можете подтвердить бронирование за 24 часа до начала
                </div>
            </div>
        </div>
        '''

        messages.success(request, success_html)

        # 11. Редирект на профиль
        return redirect(f"{reverse('profile')}?tab=bookings")

    except Exception as e:
        # Логируем ошибку
        logger.error(
            f"Error creating booking for user {request.user.username}: {str(e)}",
            exc_info=True,
            extra={'request': request}
        )

        # КРАСИВОЕ СООБЩЕНИЕ ОБ ОШИБКЕ
        error_html = f'''
        <div style="display: flex; align-items: center; gap: 12px;">
            <i class="fas fa-exclamation-circle" style="font-size: 24px; color: white;"></i>
            <div>
                <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 5px;">
                    ❌ Ошибка при бронировании
                </div>
                <div style="font-size: 14px; color: rgba(255,255,255,0.9);">
                    Произошла ошибка при создании бронирования. 
                    Пожалуйста, попробуйте еще раз или обратитесь в поддержку.
                </div>
            </div>
        </div>
        '''

        messages.error(request, error_html)
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


# ========== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ==========

@login_required
def profile(request):
    """
    Объединенный профиль пользователя с вкладками
    """
    from django.contrib.auth.models import User

    try:
        user = User.objects.select_related('profile').get(id=request.user.id)
    except User.DoesNotExist:
        user = request.user

    # Получаем бронирования с оптимизацией запросов
    bookings = Booking.objects.filter(
        user=request.user
    ).select_related(
        'court'
    ).order_by(
        '-date', '-start_time'
    )

    today = timezone.now().date()
    current_time = timezone.now().time()

    # Обрабатываем каждое бронирование
    for booking in bookings:
        booking.today = today

        # Рассчитываем полную дату начала бронирования
        booking_datetime = timezone.make_aware(
            datetime.combine(booking.date, booking.start_time)
        )

        # Можно ли подтвердить? (за 24 часа до начала)
        time_diff = booking_datetime - timezone.now()
        booking.can_confirm_attr = timedelta(hours=0) < time_diff <= timedelta(hours=24)

        # Сколько часов осталось до возможности подтверждения
        if time_diff > timedelta(hours=24):
            hours_until = (time_diff - timedelta(hours=24)).total_seconds() / 3600
            booking.hours_until_confirmation_attr = max(0, int(hours_until))
        else:
            booking.hours_until_confirmation_attr = 0

        # Прошедшее ли бронирование?
        booking.is_past = booking.date < today or (
                booking.date == today and booking.start_time < current_time
        )

        # Можно ли отменить? (не прошедшее и не отмененное)
        booking.can_cancel = (
                not booking.is_past and
                booking.status in ['pending', 'confirmed']
        )

    # Статистика для пользователя
    booking_stats = {
        'total': bookings.count(),
        'confirmed': bookings.filter(status='confirmed').count(),
        'pending': bookings.filter(status='pending').count(),
        'cancelled': bookings.filter(status='cancelled').count(),
        'upcoming': bookings.filter(
            Q(date__gt=today) |
            Q(date=today, start_time__gt=current_time),
            status__in=['pending', 'confirmed']
        ).count(),
    }

    # Получаем активную вкладку из GET-параметра или session
    active_tab = request.GET.get('tab', 'bookings')

    context = {
        'user': user,
        'bookings': bookings,
        'today': today,
        'booking_stats': booking_stats,
        'active_tab': active_tab,
    }

    return render(request, 'users/profile.html', context)


# ========== ДОПОЛНИТЕЛЬНЫЕ VIEW ==========



def my_bookings(request):
    """Показать все бронирования пользователя (для совместимости)"""
    bookings = Booking.objects.filter(user=request.user).order_by('-date', '-start_time')
    today = timezone.now().date()

    for booking in bookings:
        booking.today = today
        booking.can_confirm_attr = booking.can_confirm
        booking.hours_until_confirmation_attr = booking.hours_until_confirmation

    return render(request, 'users/bookings.html', {'bookings': bookings, 'today': today})