from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from datetime import datetime, timedelta
from django.urls import reverse
from django.db.models import Q
from .models import Court, Booking
from users.analytics import (
    get_player_stats,
    get_calendar_events,
    get_available_slots as get_available_slots_analytics
)
import traceback

# Импортируем profile из users.views для обратной совместимости
from users.views import profile


import logging
logger = logging.getLogger(__name__)


from django.utils.html import escape
from .utils import (
    create_error_message,
    create_success_message,
    validate_booking_times,
    validate_booking_duration,
    validate_working_hours,
    check_time_conflicts,
    pluralize_hours
)
from .decorators import (
    api_data_ratelimit,
    api_write_ratelimit,
    auth_ratelimit
)

def booking_page(request):
    """Страница бронирования кортов"""
    courts = Court.objects.filter(is_available=True).order_by('name')
    today_date = timezone.now().date()
    return render(request, 'booking.html', {
        'courts': courts,
        'today_date': today_date
    })


@require_GET
@api_data_ratelimit(rate='60/m')
def get_available_slots(request):
    court_id = request.GET.get('court')
    date_str = request.GET.get('date')

    logger.debug(f"get_available_slots called with court={court_id}, date={date_str}")
    logger.debug(f"Current time: {timezone.now().time()}")

    if not court_id or not date_str:
        return JsonResponse({
            'success': False,
            'message': 'Необходимо указать корт и дату'
        })

    try:
        court = Court.objects.filter(id=court_id, is_available=True).first()
        if not court:
            logger.warning(f"Court not found or not available: {court_id}")
            return JsonResponse({
                'success': False,
                'message': 'Корт не найден или недоступен'
            })

        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = timezone.now().date()
        current_time = timezone.now().time()

        logger.debug(f"booking_date={booking_date}, today={today}, current_time={current_time}")

        if booking_date < today:
            logger.warning(f"Booking date is in the past: {booking_date}")
            return JsonResponse({
                'success': False,
                'message': 'Нельзя бронировать корт на прошедшую дату'
            })

        # Получаем существующие бронирования
        existing_bookings = Booking.objects.filter(
            court=court,
            date=booking_date,
            status__in=['pending', 'confirmed']
        ).select_related('user', 'user__profile', 'user__rating').prefetch_related('partners')

        logger.debug(f"Found {existing_bookings.count()} existing bookings for court {court.name} on {booking_date}")

        # Словарь занятых часов
        booked_hours = {}
        for booking in existing_bookings:
            start_hour = booking.start_time.hour
            end_hour = booking.end_time.hour
            for hour in range(start_hour, end_hour):
                booked_hours[hour] = True
            logger.debug(f"Booking slot: {start_hour}:00-{end_hour}:00")

        # Рабочие часы: 8:00 - 22:00
        WORKING_HOURS_START = 8
        WORKING_HOURS_END = 22

        # ТОЛЬКО СВОБОДНЫЕ СЛОТЫ
        free_slots = []

        # Только если сегодняшняя дата
        if booking_date == today:
            current_hour = current_time.hour
            logger.debug(f"Booking for today - current hour: {current_hour}")
        else:
            current_hour = -1  # Будущая дата, все часы доступны
            logger.debug(f"Booking for future date - all hours available")

        for hour in range(WORKING_HOURS_START, WORKING_HOURS_END):
            is_available = hour not in booked_hours

            # Если сегодня, нельзя бронировать прошедшее время
            if booking_date == today and hour < current_hour:
                is_available = False

            # ДОБАВЛЯЕМ ТОЛЬКО СВОБОДНЫЕ СЛОТЫ
            if is_available:
                free_slots.append({
                    'type': 'free_slot',
                    'start_time': f"{hour:02d}:00",
                    'end_time': f"{(hour + 1):02d}:00",
                    'duration': 1,
                    'hour': hour
                })

        # Получаем рейтинг текущего пользователя (если залогинен)
        user_rating = None
        if request.user.is_authenticated:
            try:
                user_rating = request.user.rating.level
            except (AttributeError, ObjectDoesNotExist):
                user_rating = None

        # Ищем бронирования с "Найти партнёра"
        partner_bookings = []
        for booking in existing_bookings:
            # Пропускаем, если не ищет партнёра или уже полное
            if not booking.looking_for_partner or booking.is_full:
                continue

            # Пропускаем свои бронирования
            if request.user.is_authenticated and (booking.user == request.user or request.user in booking.partners.all()):
                continue

            # Проверяем рейтинг
            can_join = True
            join_message = ""

            if request.user.is_authenticated:
                can_join, join_message = booking.can_join(request.user)

            # Формируем информацию о бронировании
            user_full_name = f"{booking.user.first_name} {booking.user.last_name}".strip() or booking.user.username

            partner_bookings.append({
                'type': 'partner_booking',
                'booking_id': booking.id,
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'hour': booking.start_time.hour,
                'creator_name': user_full_name,
                'creator_rating': booking.user.rating.level if hasattr(booking.user, 'rating') else None,
                'required_rating': booking.required_rating_level,
                'current_players': 1 + booking.partners.count(),
                'max_players': booking.max_players,
                'available_slots': booking.available_slots,
                'price_per_person': float(booking.price_per_person),
                'can_join': can_join,
                'join_message': join_message
            })

        # Объединяем свободные слоты и бронирования с партнёрами
        all_items = free_slots + partner_bookings
        # Сортируем по времени начала
        all_items.sort(key=lambda x: x['hour'])

        logger.debug(f"Free slots: {len(free_slots)}, Partner bookings: {len(partner_bookings)}")

        result = {
            'success': True,
            'items': all_items,  # Смешанный список: свободные слоты + бронирования с партнёрами
            'court_price': float(court.price_per_hour),
            'court_name': court.name,
            'court_id': court.id,
            'date': date_str,
            'date_formatted': booking_date.strftime('%d.%m.%Y'),
            'free_slots_count': len(free_slots),
            'partner_bookings_count': len(partner_bookings),
            'user_rating': user_rating
        }

        logger.debug(f"Returning {len(all_items)} total items (free slots + partner bookings)")

        response = JsonResponse(result)
        response['Content-Type'] = 'application/json; charset=utf-8'
        return response

    except Exception as e:
        logger.error(f"Error in get_available_slots: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка загрузки слотов'
        }, status=500)

@login_required
@require_POST
@api_write_ratelimit(rate='10/m')
def create_booking(request):
    """
    Создание бронирования (рефакторенная версия)

    Улучшения:
    - Код сократился с 350 строк до ~220
    - Переиспользуемые функции валидации
    - Единая генерация HTML сообщений
    - Улучшенная читаемость
    """
    try:
        # Получаем данные из формы
        court_id = request.POST.get('court_id')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        duration = request.POST.get('duration', '1')

        # 1. Валидация обязательных полей
        if not all([court_id, date_str, start_time_str]):
            messages.error(request, create_error_message("Ошибка", "Все поля должны быть заполнены"))
            return redirect('booking')

        court = get_object_or_404(Court, id=court_id, is_available=True)

        # 2. Парсим дату и время
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

        # 3. Валидация времени
        is_valid, error_msg = validate_booking_times(
            booking_date, start_time, end_time, today, current_time
        )
        if not is_valid:
            messages.error(request, create_error_message("Ошибка", error_msg))
            return redirect('booking')

        # 4. Валидация продолжительности
        is_valid, duration_hours, error_msg = validate_booking_duration(
            start_time, end_time, booking_date
        )
        if not is_valid:
            messages.error(request, create_error_message("Ошибка", error_msg))
            return redirect('booking')

        # 5. Проверка рабочих часов
        is_valid, error_msg = validate_working_hours(start_time, end_time)
        if not is_valid:
            messages.error(request, create_error_message("Ошибка", error_msg))
            return redirect('booking')

        # 6. Создание бронирования в транзакции
        with transaction.atomic():
            # Проверка конфликтов
            has_conflict, conflicting_booking = check_time_conflicts(
                court, booking_date, start_time, end_time
            )

            if has_conflict:
                conflict_start = conflicting_booking.start_time.strftime('%H:%M')
                conflict_end = conflicting_booking.end_time.strftime('%H:%M')
                error_msg = f"Выбранное время уже занято с {conflict_start} до {conflict_end}"
                messages.error(request, create_error_message("Время занято", error_msg))
                return redirect('booking')

            # Получаем данные для поиска партнеров
            looking_for_partner = request.POST.get('looking_for_partner') == 'on'
            max_players = int(request.POST.get('max_players', 4))

            # Получаем выбранные уровни рейтинга (множественные чекбоксы)
            required_rating_levels = request.POST.getlist('required_rating_levels')
            logger.info(f"Selected rating levels: {required_rating_levels}")

            # Получаем приглашенных участников
            invited_participants_str = request.POST.get('invited_participants', '')
            invited_participant_ids = [int(pid) for pid in invited_participants_str.split(',') if pid.strip()]
            logger.info(f"Invited participants: {invited_participant_ids}")

            # Получаем тип бронирования и тренера
            booking_type = request.POST.get('booking_type', 'game')
            coach_id = request.POST.get('coach')
            coach = None

            if coach_id and booking_type == 'training':
                from django.contrib.auth.models import User
                try:
                    coach = User.objects.get(id=coach_id, groups__name='Тренеры')
                except User.DoesNotExist:
                    coach = None

            # Создаем бронирование
            booking = Booking.objects.create(
                user=request.user,
                court=court,
                date=booking_date,
                start_time=start_time,
                end_time=end_time,
                status='pending',
                booking_type=booking_type,
                coach=coach,
                looking_for_partner=looking_for_partner if booking_type == 'game' else False,
                max_players=max_players if booking_type == 'game' else 1,
                required_rating_levels=required_rating_levels if (required_rating_levels and booking_type == 'game') else []
            )

            # Повторная проверка (защита от race condition)
            has_conflict, _ = check_time_conflicts(
                court, booking_date, start_time, end_time, exclude_booking_id=booking.id
            )

            if has_conflict:
                booking.delete()
                error_msg = "Это время было забронировано другим пользователем. Пожалуйста, выберите другое время."
                messages.error(request, create_error_message("Время занято", error_msg))
                return redirect('booking')

            # Отправляем приглашения выбранным участникам
            if invited_participant_ids:
                from django.contrib.auth.models import User
                from booking.models import BookingInvitation

                invitations_sent = 0
                for user_id in invited_participant_ids:
                    try:
                        invited_user = User.objects.get(id=user_id)
                        # Создаем приглашение
                        BookingInvitation.objects.create(
                            booking=booking,
                            inviter=request.user,
                            invitee=invited_user,
                            invitee_phone=invited_user.profile.phone if hasattr(invited_user, 'profile') else '',
                            message=f"Приглашение присоединиться к игре {booking_date.strftime('%d.%m.%Y')} в {start_time_str}"
                        )
                        invitations_sent += 1
                        logger.info(f"Invitation sent to user {invited_user.username} for booking {booking.id}")
                    except User.DoesNotExist:
                        logger.warning(f"User with id {user_id} not found for invitation")
                    except Exception as e:
                        logger.error(f"Error sending invitation to user {user_id}: {str(e)}")

                if invitations_sent > 0:
                    logger.info(f"Sent {invitations_sent} invitations for booking {booking.id}")

        # 7. Очищаем кэш
        clear_slots_cache(court_id=court_id, date_str=date_str)

        # 8. Логируем успех
        logger.info(
            f"Booking created: User {request.user.username} booked court {court.name} "
            f"on {booking_date} from {start_time_str} to {end_time.strftime('%H:%M')} "
            f"(Duration: {duration_hours}h, Price: {booking.total_price} руб., Type: {booking_type})"
        )

        # 9. Формируем красивое сообщение об успехе
        duration_text = pluralize_hours(duration_hours)
        booking_type_text = "Тренировка" if booking_type == 'training' else "Игра"
        coach_info = f" с тренером {coach.get_full_name() or coach.username}" if coach else ""

        success_details = f"""
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <i class="fas fa-check-circle" style="font-size: 24px; color: white;"></i>
            <div style="flex: 1;">
                <div style="font-size: 16px; font-weight: bold; color: white; margin-bottom: 8px;">
                    🎉 Бронирование успешно создано!
                </div>
                <div style="background: rgba(255,255,255,0.15); padding: 12px; border-radius: 8px;">
                    <div style="display: grid; grid-template-columns: auto 1fr; gap: 8px 15px;">
                        <div style="color: rgba(255,255,255,0.9); font-size: 14px;">
                            <i class="fas fa-clipboard-list"></i> Тип:
                        </div>
                        <div style="font-weight: bold; color: white; font-size: 14px;">{booking_type_text}{coach_info}</div>

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
        """

        messages.success(request, success_details)
        return redirect(f"{reverse('profile')}#bookings")

    except Exception as e:
        logger.error(
            f"Error creating booking for user {request.user.username}: {str(e)}",
            exc_info=True
        )
        messages.error(request, create_error_message(
            "Ошибка при бронировании",
            "Произошла ошибка. Пожалуйста, попробуйте еще раз или обратитесь в поддержку."
        ))
        return redirect('booking')


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


# ========== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ==========
# УДАЛЕНО: Дублирующая функция profile() - используем версию из users.views (импорт в начале файла)


# ========== ДОПОЛНИТЕЛЬНЫЕ VIEW ==========
# УДАЛЕНО: my_bookings() - дублировало функционал profile()


# ========== ПОИСК ПАРТНЁРОВ И ПРИГЛАШЕНИЯ ==========

@login_required
def find_partners(request):
    """Страница поиска партнёров - бронирования, которые ищут игроков"""
    today = timezone.now().date()

    # ОПТИМИЗАЦИЯ: Загружаем рейтинг пользователя один раз
    try:
        user_rating = request.user.rating.level
    except (AttributeError, ObjectDoesNotExist):
        user_rating = None

    # ОПТИМИЗАЦИЯ: Используем Prefetch для оптимизации запросов
    from django.db.models import Prefetch
    from django.contrib.auth.models import User

    # Получаем бронирования, которые ищут партнёров
    available_bookings = Booking.objects.filter(
        looking_for_partner=True,
        status__in=['pending', 'confirmed'],
        date__gte=today
    ).select_related(
        'user', 'user__profile', 'user__rating', 'court'
    ).prefetch_related(
        Prefetch('partners', queryset=User.objects.all(), to_attr='partners_list')
    ).order_by('date', 'start_time')

    # Фильтруем бронирования, в которых есть свободные места
    bookings_with_slots = []

    for booking in available_bookings:
        # ИСПРАВЛЕНА N+1: Проверяем через предзагруженный список
        partner_ids = [p.id for p in booking.partners_list]

        # Пропускаем свои бронирования
        if booking.user == request.user or request.user.id in partner_ids:
            continue

        # Проверяем наличие мест
        if not booking.is_full:
            can_join, message = booking.can_join(request.user)
            booking.can_join_flag = can_join
            booking.join_message = message
            bookings_with_slots.append(booking)

    context = {
        'bookings': bookings_with_slots,
        'user_rating': user_rating,
        'today': today
    }

    return render(request, 'booking/find_partners.html', context)


@login_required
@require_POST
def join_booking(request, booking_id):
    """Присоединиться к бронированию"""
    try:
        booking = get_object_or_404(Booking, id=booking_id)

        # Проверяем, можно ли присоединиться
        can_join, message = booking.can_join(request.user)
        if not can_join:
            return JsonResponse({
                'success': False,
                'message': message
            })

        # Добавляем пользователя в партнёры
        success, msg = booking.add_partner(request.user)

        if success:
            # Отправляем уведомление создателю бронирования
            from users.services import NotificationService
            NotificationService.send_partner_joined_notification(booking, request.user)

            return JsonResponse({
                'success': True,
                'message': f'Вы успешно присоединились! Стоимость на человека: {booking.price_per_person} руб.',
                'price_per_person': booking.price_per_person,
                'available_slots': booking.available_slots
            })
        else:
            return JsonResponse({
                'success': False,
                'message': msg
            })

    except Exception as e:
        logger.error(f"Error joining booking {booking_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Произошла ошибка при присоединении'
        })


@login_required
def send_invitation(request, booking_id):
    """Отправить приглашение другу"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if request.method == 'POST':
        from .forms import InviteFriendForm
        form = InviteFriendForm(request.POST, booking=booking, inviter=request.user)

        if form.is_valid():
            invitation = form.save()

            # Отправляем уведомление приглашённому
            from users.services import NotificationService
            if invitation.invitee:
                NotificationService.send_booking_invitation_notification(invitation)

            messages.success(request, 'Приглашение успешно отправлено!')
            return redirect('booking_detail', booking_id=booking_id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            return redirect('booking_detail', booking_id=booking_id)

    else:
        from .forms import InviteFriendForm
        form = InviteFriendForm(booking=booking, inviter=request.user)

    context = {
        'form': form,
        'booking': booking
    }

    return render(request, 'booking/send_invitation.html', context)


@login_required
def my_invitations(request):
    """Список приглашений пользователя"""
    from .models import BookingInvitation

    # Полученные приглашения
    received_invitations = BookingInvitation.objects.filter(
        invitee=request.user,
        status='pending'
    ).select_related('booking', 'booking__court', 'inviter', 'inviter__profile').order_by('-created_at')

    # Отправленные приглашения
    sent_invitations = BookingInvitation.objects.filter(
        inviter=request.user
    ).select_related('booking', 'booking__court', 'invitee', 'invitee__profile').order_by('-created_at')[:10]

    context = {
        'received_invitations': received_invitations,
        'sent_invitations': sent_invitations
    }

    return render(request, 'booking/my_invitations.html', context)


@login_required
@require_POST
def accept_invitation(request, invitation_id):
    """Принять приглашение"""
    from .models import BookingInvitation

    try:
        invitation = get_object_or_404(BookingInvitation, id=invitation_id, invitee=request.user)

        success, message = invitation.accept()

        if success:
            # Уведомляем отправителя
            from users.services import NotificationService
            NotificationService.send_invitation_accepted_notification(invitation)

            return JsonResponse({
                'success': True,
                'message': message,
                'booking_id': invitation.booking.id
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            })

    except Exception as e:
        logger.error(f"Error accepting invitation {invitation_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Произошла ошибка при принятии приглашения'
        })


@login_required
@require_POST
def decline_invitation(request, invitation_id):
    """Отклонить приглашение"""
    from .models import BookingInvitation

    try:
        invitation = get_object_or_404(BookingInvitation, id=invitation_id, invitee=request.user)

        success, message = invitation.decline()

        if success:
            # Уведомляем отправителя
            from users.services import NotificationService
            NotificationService.send_invitation_declined_notification(invitation)

            return JsonResponse({
                'success': True,
                'message': message
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            })

    except Exception as e:
        logger.error(f"Error declining invitation {invitation_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Произошла ошибка при отклонении приглашения'
        })


@login_required
@require_POST
def cancel_invitation(request, invitation_id):
    """Отменить отправленное приглашение"""
    from .models import BookingInvitation

    try:
        invitation = get_object_or_404(BookingInvitation, id=invitation_id, inviter=request.user)

        success, message = invitation.cancel()

        if success:
            return JsonResponse({
                'success': True,
                'message': message
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            })

    except Exception as e:
        logger.error(f"Error cancelling invitation {invitation_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Произошла ошибка при отмене приглашения'
        })


@login_required
def booking_detail(request, booking_id):
    """Детальная страница бронирования с возможностью приглашения друзей"""
    from .models import BookingInvitation
    from .forms import InviteFriendForm

    # Получаем бронирование (создатель или партнёр)
    booking = get_object_or_404(
        Booking.objects.prefetch_related('partners', 'invitations'),
        Q(user=request.user) | Q(partners=request.user),
        id=booking_id
    )

    # Проверяем права доступа
    is_creator = booking.user == request.user
    is_partner = request.user in booking.partners.all()

    if not (is_creator or is_partner):
        messages.error(request, 'У вас нет доступа к этому бронированию')
        return redirect('profile')

    # Получаем все приглашения для этого бронирования
    invitations = booking.invitations.all().order_by('-created_at')

    # Форма для приглашения (только для создателя)
    invite_form = None
    if is_creator and not booking.is_full:
        invite_form = InviteFriendForm(booking=booking, inviter=request.user)

    context = {
        'booking': booking,
        'is_creator': is_creator,
        'is_partner': is_partner,
        'invitations': invitations,
        'invite_form': invite_form,
        'today': timezone.now().date()
    }

    return render(request, 'booking/booking_detail.html', context)

# ========== API ENDPOINTS ДЛЯ СТАТИСТИКИ И КАЛЕНДАРЯ ==========

@login_required
@require_GET
@api_data_ratelimit(rate='30/m')
def api_player_stats(request):
    """API: Получить статистику игрока"""
    try:
        stats = get_player_stats(request.user)
        
        # Преобразуем datetime объекты для JSON
        if stats['monthly_activity']:
            for item in stats['monthly_activity']:
                if 'month' in item and item['month']:
                    item['month'] = item['month'].strftime('%Y-%m')
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting player stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка получения статистики'
        }, status=500)


@login_required
@require_GET
def api_calendar_events(request):
    """API: Получить события для календаря"""
    try:
        start_str = request.GET.get('start')
        end_str = request.GET.get('end')

        if not start_str or not end_str:
            return JsonResponse({
                'success': False,
                'message': 'Требуются параметры start и end'
            }, status=400)

        # Парсим даты - FullCalendar может отправить разные форматы
        try:
            from dateutil import parser as date_parser
            # Используем dateutil для надежного парсинга любых форматов дат
            start_date = date_parser.parse(start_str).date()
            end_date = date_parser.parse(end_str).date()
        except ImportError:
            # Если dateutil не установлен, используем базовый парсинг
            try:
                # Извлекаем только дату из ISO строки
                start_date = datetime.fromisoformat(start_str.split('T')[0]).date()
                end_date = datetime.fromisoformat(end_str.split('T')[0]).date()
            except Exception as date_error:
                logger.error(f"Date parsing error: {date_error}, start={start_str}, end={end_str}")
                return JsonResponse({
                    'success': False,
                    'message': 'Неверный формат даты'
                }, status=400)
        except Exception as date_error:
            logger.error(f"Date parsing error: {date_error}, start={start_str}, end={end_str}")
            return JsonResponse({
                'success': False,
                'message': 'Неверный формат даты'
            }, status=400)

        events = get_calendar_events(request.user, start_date, end_date)

        return JsonResponse(events, safe=False)

    except Exception as e:
        logger.error(f"Error getting calendar events: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': 'Ошибка получения событий календаря'
        }, status=500)


@login_required
@require_GET
def api_available_slots(request):
    """API: Получить доступные слоты для бронирования"""
    try:
        court_id = request.GET.get('court_id')
        date_str = request.GET.get('date')
        
        if not court_id or not date_str:
            return JsonResponse({
                'success': False,
                'message': 'Требуются параметры court_id и date'
            }, status=400)
        
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        slots = get_available_slots_analytics(court_id, date)
        
        return JsonResponse({
            'success': True,
            'slots': slots
        })
    
    except Exception as e:
        logger.error(f"Error getting available slots: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Ошибка получения доступных слотов'
        }, status=500)



@login_required
def player_statistics(request):
    """Страница со статистикой игрока"""
    try:
        import json
        stats = get_player_stats(request.user)

        # Сериализуем данные для JavaScript
        # Преобразуем QuerySet и datetime объекты в JSON-совместимые форматы
        monthly_activity_json = json.dumps([
            {
                'month': item['month'].strftime('%Y-%m') if item.get('month') else '',
                'games': item.get('games', 0)
            }
            for item in stats.get('monthly_activity', [])
        ])

        weekday_stats_json = json.dumps(stats.get('weekday_stats', []))
        rating_progress_json = json.dumps(stats.get('rating_progress', []))

        context = {
            'stats': stats,
            'user': request.user,
            'monthly_activity_json': monthly_activity_json,
            'weekday_stats_json': weekday_stats_json,
            'rating_progress_json': rating_progress_json,
        }

        return render(request, 'booking/player_stats.html', context)

    except Exception as e:
        import traceback
        logger.error(f"Error rendering player statistics: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, 'Ошибка загрузки статистики')
        return redirect('profile')


@require_GET
def get_coaches_list(request):
    """API endpoint для получения списка тренеров"""
    try:
        from users.models import CoachProfile

        coaches = CoachProfile.objects.filter(
            is_active=True
        ).select_related('user').order_by('-coach_rating', 'user__first_name')

        coaches_data = []
        for coach in coaches:
            full_name = f"{coach.user.first_name} {coach.user.last_name}".strip()
            display_name = full_name if full_name else coach.user.username

            coaches_data.append({
                'id': coach.user.id,
                'name': display_name,
                'rating': float(coach.coach_rating),
                'hourly_rate': float(coach.hourly_rate),
                'specialization': coach.specialization,
                'experience_years': coach.experience_years,
            })

        return JsonResponse({
            'success': True,
            'coaches': coaches_data,
            'count': len(coaches_data)
        })

    except Exception as e:
        logger.error(f"Error fetching coaches list: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка загрузки списка тренеров'
        }, status=500)


@login_required
def api_search_users(request):
    """
    API: Умный поиск пользователей по имени, фамилии или телефону
    """
    try:
        query = request.GET.get('q', '').strip()

        logger.info(f"Search query from user {request.user.username}: '{query}'")

        if len(query) < 2:
            return JsonResponse({
                'success': False,
                'message': 'Запрос должен содержать минимум 2 символа',
                'users': []
            })

        # Ищем пользователей по имени, фамилии или телефону
        from django.db.models import Q
        from users.models import UserProfile

        # Два отдельных запроса для надежности
        # 1. Поиск по имени и фамилии
        users_by_name = User.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

        # 2. Поиск по телефону (только если есть профиль)
        users_by_phone = User.objects.filter(
            profile__phone__icontains=query
        )

        # Объединяем результаты и убираем дубликаты
        users = (users_by_name | users_by_phone).distinct().select_related('profile')[:10]

        logger.info(f"Found {users.count()} users matching query '{query}'")

        users_data = []
        for user in users:
            full_name = f"{user.first_name} {user.last_name}".strip()
            display_name = full_name if full_name else user.username

            # Безопасно получаем телефон
            try:
                phone = user.profile.phone
            except (AttributeError, UserProfile.DoesNotExist):
                phone = 'Не указан'

            # Помечаем если это текущий пользователь
            is_current_user = user.id == request.user.id

            users_data.append({
                'id': user.id,
                'full_name': display_name,
                'phone': phone,
                'is_current_user': is_current_user,
            })

            logger.debug(f"User found: {display_name} ({phone}) {'[current user]' if is_current_user else ''}")

        return JsonResponse({
            'success': True,
            'users': users_data,
            'count': len(users_data)
        })

    except Exception as e:
        logger.error(f"Error searching users: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка поиска пользователей',
            'users': []
        }, status=500)


@login_required
def api_get_notifications(request):
    """
    API: Получить уведомления пользователя (приглашения в игры)
    """
    try:
        from booking.models import BookingInvitation

        # Получаем все непрочитанные приглашения
        invitations = BookingInvitation.objects.filter(
            invitee=request.user,
            status='pending'
        ).select_related('booking', 'booking__court', 'inviter').order_by('-created_at')[:10]

        notifications_data = []
        for invitation in invitations:
            booking = invitation.booking
            inviter_name = f"{invitation.inviter.first_name} {invitation.inviter.last_name}".strip() or invitation.inviter.username

            # Форматируем дату и время
            booking_date = booking.date.strftime('%d.%m.%Y')
            booking_time = booking.start_time.strftime('%H:%M')

            notifications_data.append({
                'id': invitation.id,
                'type': 'invitation',
                'title': f'Приглашение в игру',
                'message': f'{inviter_name} приглашает вас на игру {booking_date} в {booking_time}',
                'inviter_name': inviter_name,
                'court_name': booking.court.name,
                'date': booking_date,
                'time': booking_time,
                'booking_id': booking.id,
                'created_at': invitation.created_at.isoformat(),
            })

        return JsonResponse({
            'success': True,
            'notifications': notifications_data,
            'count': len(notifications_data)
        })

    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка загрузки уведомлений',
            'notifications': []
        }, status=500)


@login_required
@login_required
@require_POST
def api_accept_invitation(request, invitation_id):
    """
    API: Принять приглашение в игру
    """
    try:
        from booking.models import BookingInvitation

        logger.info(f"User {request.user.username} trying to accept invitation {invitation_id}")

        invitation = get_object_or_404(BookingInvitation, id=invitation_id, invitee=request.user)

        logger.info(f"Invitation found: booking={invitation.booking.id}, status={invitation.status}")

        if invitation.status != 'pending':
            logger.warning(f"Invitation {invitation_id} status is {invitation.status}, not pending")
            return JsonResponse({
                'success': False,
                'message': 'Приглашение уже обработано'
            }, status=400)

        # Принимаем приглашение
        success, message = invitation.accept()

        logger.info(f"Invitation.accept() result: success={success}, message={message}")

        if success:
            logger.info(f"User {request.user.username} accepted invitation {invitation_id}")
            return JsonResponse({
                'success': True,
                'message': 'Вы успешно присоединились к игре!'
            })
        else:
            logger.warning(f"Failed to accept invitation {invitation_id}: {message}")
            return JsonResponse({
                'success': False,
                'message': message
            }, status=400)

    except Exception as e:
        logger.error(f"Error accepting invitation: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при принятии приглашения'
        }, status=500)


@login_required
@require_POST
def api_decline_invitation(request, invitation_id):
    """
    API: Отклонить приглашение в игру
    """
    try:
        from booking.models import BookingInvitation

        invitation = get_object_or_404(BookingInvitation, id=invitation_id, invitee=request.user)

        if invitation.status != 'pending':
            return JsonResponse({
                'success': False,
                'message': 'Приглашение уже обработано'
            }, status=400)

        # Отклоняем приглашение
        success, message = invitation.decline()

        if success:
            logger.info(f"User {request.user.username} declined invitation {invitation_id}")
            return JsonResponse({
                'success': True,
                'message': 'Приглашение отклонено'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            }, status=400)

    except Exception as e:
        logger.error(f"Error declining invitation: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Ошибка при отклонении приглашения'
        }, status=500)
