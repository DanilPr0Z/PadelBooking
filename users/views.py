from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.http import JsonResponse
# Удален импорт csrf_exempt для улучшения безопасности
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from .forms import RegistrationForm, LoginForm, EmailUpdateForm, PhoneVerificationForm, AvatarUploadForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Prefetch, Count, Q
from datetime import datetime, timedelta
from booking.models import Booking, Court
from users.analytics import get_player_stats
import json
import logging

logger = logging.getLogger(__name__)


@require_POST
def ajax_register(request):
    """AJAX регистрация - исправленная версия"""
    try:
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Регистрация успешна! Код подтверждения отправлен на ваш телефон.',
                'username': user.username
            })

        # ИСПРАВЛЕНО: правильный формат ошибок для JavaScript
        errors = {}
        for field, error_list in form.errors.items():
            # Преобразуем ошибки в простые строки
            errors[field] = [str(error) for error in error_list]

        # Получаем общее сообщение об ошибке (первая ошибка)
        first_error = ''
        if errors:
            first_field = list(errors.keys())[0]
            if errors[first_field]:
                first_error = errors[first_field][0]

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': first_error or 'Пожалуйста, исправьте ошибки в форме'
        })

    except Exception as e:
        # Логируем ошибку для отладки
        logger.error(f"Registration error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
def ajax_login(request):
    """AJAX вход по username или телефону"""
    try:
        form = LoginForm(request.POST)

        if form.is_valid():
            identifier_data = form.cleaned_data.get('identifier')
            password = form.cleaned_data.get('password')

            # Определяем username для аутентификации
            username = identifier_data['username']

            # Пытаемся аутентифицировать пользователя
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'message': 'Вход выполнен успешно!',
                    'username': user.username
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Неверный пароль'
                })

        # Возвращаем ошибки формы
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]

        first_error = ''
        if errors:
            first_field = list(errors.keys())[0]
            if errors[first_field]:
                first_error = errors[first_field][0]

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': first_error or 'Пожалуйста, исправьте ошибки в форме'
        })

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


def user_login(request):
    """Стандартный вход (для обратной совместимости)"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier_data = form.cleaned_data.get('identifier')
            password = form.cleaned_data.get('password')

            # Определяем username для аутентификации
            username = identifier_data['username']

            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
    else:
        form = LoginForm()

    return render(request, 'users/login.html', {'form': form})


def register(request):
    """Стандартная регистрация (для обратной совместимости)"""
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegistrationForm()

    return render(request, 'users/register.html', {'form': form})


def user_logout(request):
    """Стандартный выход (для обратной совместимости)"""
    logout(request)
    return redirect('home')


@require_POST
def ajax_logout(request):
    """AJAX выход"""
    logout(request)
    return JsonResponse({
        'success': True,
        'message': 'Вы успешно вышли из аккаунта'
    })


@require_POST
@login_required
def update_email(request):
    """AJAX обновление email пользователя"""
    try:
        form = EmailUpdateForm(request.POST, instance=request.user)

        if form.is_valid():
            user = form.save()

            # Возвращаем успешный ответ
            return JsonResponse({
                'success': True,
                'email': user.email,
                'message': 'Email успешно обновлен!'
            })

        # Возвращаем ошибки
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]

        first_error = ''
        if errors:
            first_field = list(errors.keys())[0]
            if errors[first_field]:
                first_error = errors[first_field][0]

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': first_error or 'Ошибка при обновлении email'
        })

    except Exception as e:
        logger.error(f"Email update error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def verify_phone(request):
    """AJAX подтверждение телефона"""
    try:
        form = PhoneVerificationForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data['verification_code']

            # Проверяем код через профиль пользователя
            if request.user.profile.verify_phone(code):
                return JsonResponse({
                    'success': True,
                    'message': 'Телефон успешно подтвержден!',
                    'phone_verified': True
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Неверный код подтверждения'
                })

        # Возвращаем ошибки
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]

        first_error = ''
        if errors:
            first_field = list(errors.keys())[0]
            if errors[first_field]:
                first_error = errors[first_field][0]

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': first_error or 'Ошибка при подтверждении телефона'
        })

    except Exception as e:
        logger.error(f"Phone verification error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def resend_verification_code(request):
    """AJAX повторная отправка кода подтверждения"""
    try:
        if hasattr(request.user, 'profile'):
            # Генерируем новый код
            code = request.user.profile.generate_verification_code()

            # В реальном приложении здесь был бы код отправки SMS
            # Для тестирования просто логируем
            logger.info(f"Verification code for {request.user.profile.phone}: {code}")

            return JsonResponse({
                'success': True,
                'message': 'Новый код подтверждения отправлен на ваш телефон'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Профиль пользователя не найден'
            })

    except Exception as e:
        logger.error(f"Code sending error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def verify_email(request):
    """AJAX подтверждение email"""
    try:
        code = request.POST.get('email_verification_code', '').strip()

        if not code:
            return JsonResponse({
                'success': False,
                'message': 'Введите код подтверждения'
            })

        if not hasattr(request.user, 'profile'):
            return JsonResponse({
                'success': False,
                'message': 'Профиль пользователя не найден'
            })

        # Используем метод модели для подтверждения
        if request.user.profile.verify_email(code):
            return JsonResponse({
                'success': True,
                'message': 'Email успешно подтвержден!',
                'email_verified': True
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Неверный код подтверждения'
            })

    except Exception as e:
        logger.error(f"Email confirmation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def resend_email_verification_code(request):
    """AJAX повторная отправка кода подтверждения email"""
    try:
        if not hasattr(request.user, 'profile'):
            return JsonResponse({
                'success': False,
                'message': 'Профиль пользователя не найден'
            })

        if not request.user.email:
            return JsonResponse({
                'success': False,
                'message': 'Email не указан'
            })

        # Генерируем новый код через метод модели
        code = request.user.profile.generate_email_verification_code()

        # В реальном приложении здесь был бы код отправки email
        # Для тестирования код уже залогирован в методе модели

        return JsonResponse({
            'success': True,
            'message': f'Код подтверждения отправлен на {request.user.email}'
        })

    except Exception as e:
        print(f"Ошибка при отправке кода email: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def upload_avatar(request):
    """AJAX загрузка аватарки"""
    try:
        if not hasattr(request.user, 'profile'):
            return JsonResponse({
                'success': False,
                'message': 'Профиль пользователя не найден'
            })

        form = AvatarUploadForm(request.POST, request.FILES)

        if form.is_valid():
            avatar = form.cleaned_data['avatar']

            # Сохраняем аватарку через метод модели
            request.user.profile.save_avatar(avatar)

            # Получаем URL новой аватарки
            avatar_url = request.user.profile.get_avatar_url()

            return JsonResponse({
                'success': True,
                'message': 'Аватар успешно загружен!',
                'avatar_url': avatar_url if avatar_url else ''
            })

        # Возвращаем ошибки
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]

        first_error = ''
        if errors:
            first_field = list(errors.keys())[0]
            if errors[first_field]:
                first_error = errors[first_field][0]

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': first_error or 'Ошибка при загрузке аватарки'
        })

    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
    except Exception as e:
        logger.error(f"Avatar upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def delete_avatar(request):
    """AJAX удаление аватарки"""
    try:
        if not hasattr(request.user, 'profile'):
            return JsonResponse({
                'success': False,
                'message': 'Профиль пользователя не найден'
            })

        # Удаляем аватарку
        if request.user.profile.delete_avatar():
            return JsonResponse({
                'success': True,
                'message': 'Аватар успешно удален!'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Аватар не найден'
            })

    except Exception as e:
        logger.error(f"Avatar deletion error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def update_profile(request):
    """AJAX обновление данных профиля"""
    try:
        from .forms import ProfileUpdateForm
        form = ProfileUpdateForm(request.POST, instance=request.user)

        if form.is_valid():
            user = form.save()

            # Обновляем телефон в профиле
            if hasattr(user, 'profile'):
                user.profile.phone = form.cleaned_data.get('phone')
                user.profile.save()

            return JsonResponse({
                'success': True,
                'message': 'Данные профиля успешно обновлены!',
                'username': user.username
            })

        # Возвращаем ошибки
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(error) for error in error_list]

        first_error = ''
        if errors:
            first_field = list(errors.keys())[0]
            if errors[first_field]:
                first_error = errors[first_field][0]

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': first_error or 'Ошибка при обновлении профиля'
        })

    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


from .models import PlayerRating


@login_required
def profile(request):
    """
    Объединенный профиль пользователя с вкладками:
    - Профиль (данные пользователя)
    - Мои бронирования
    - История
    - Настройки
    - Рейтинг
    """
    from django.contrib.auth.models import User

    # ОПТИМИЗАЦИЯ: Получаем пользователя с профилем и рейтингом за один запрос
    try:
        user = User.objects.select_related('profile', 'rating').get(id=request.user.id)
    except User.DoesNotExist:
        user = request.user

    # Получаем рейтинг пользователя
    try:
        rating = user.rating
    except PlayerRating.DoesNotExist:
        # Создаем рейтинг по умолчанию если его нет
        rating = PlayerRating.objects.create(
            user=user,
            numeric_rating=1.00,
            level='D'
        )

    # Получаем бронирования с оптимизацией запросов
    bookings = Booking.objects.filter(
        user=request.user
    ).select_related(
        'court'  # JOIN вместо отдельных запросов
    ).order_by(
        '-date', '-start_time'
    )

    today = timezone.now().date()
    current_time = timezone.now().time()

    # Создаем список бронирований с дополнительными данными
    bookings_with_extra = []

    for booking in bookings:
        # Рассчитываем полную дату начала бронирования
        booking_datetime = timezone.make_aware(
            datetime.combine(booking.date, booking.start_time)
        )

        # Можно ли подтвердить? (за 24 часа до начала)
        time_diff = booking_datetime - timezone.now()
        can_confirm = timedelta(hours=0) < time_diff <= timedelta(hours=24)

        # Сколько часов осталось до возможности подтверждения
        if time_diff > timedelta(hours=24):
            hours_until = (time_diff - timedelta(hours=24)).total_seconds() / 3600
            hours_until_confirmation = max(0, int(hours_until))
        else:
            hours_until_confirmation = 0

        # Прошедшее ли бронирование?
        is_past = booking.date < today or (
                booking.date == today and booking.start_time < current_time
        )

        # Можно ли отменить? (не прошедшее и не отмененное)
        can_cancel = (
                not is_past and
                booking.status in ['pending', 'confirmed']
        )

        # Сохраняем бронирование с дополнительными данными
        bookings_with_extra.append({
            'booking': booking,
            'can_confirm': can_confirm,
            'hours_until_confirmation': hours_until_confirmation,
            'is_past': is_past,
            'can_cancel': can_cancel,
            'today': today
        })

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
    active_tab = request.GET.get('tab', 'profile')

    # ВАЖНО: Рассчитываем процент прогресса для отображения
    progress_percentage = rating.get_progress_percentage()

    # Отладочный вывод
    logger.debug(f"Rating debug - numeric: {rating.numeric_rating}, level: {rating.level}, progress: {progress_percentage}%")

    # Также получаем границы диапазона для текущего уровня
    range_min = rating.get_range_min()
    range_max = rating.get_range_max()

    # Получаем статистику игрока для вкладки "Моя статистика"
    try:
        stats = get_player_stats(request.user)

        # Сериализуем данные для JavaScript
        monthly_activity_json = json.dumps([
            {
                'month': item['month'].strftime('%Y-%m') if item.get('month') else '',
                'games': item.get('games', 0)
            }
            for item in stats.get('monthly_activity', [])
        ])

        weekday_stats_json = json.dumps(stats.get('weekday_stats', []))
        rating_progress_json = json.dumps(stats.get('rating_progress', []))
    except Exception as e:
        logger.error(f"Error getting player stats: {str(e)}")
        stats = None
        monthly_activity_json = '[]'
        weekday_stats_json = '[]'
        rating_progress_json = '[]'

    context = {
        'user': user,
        'bookings_with_extra': bookings_with_extra,  # Передаем обновленный список
        'today': today,
        'booking_stats': booking_stats,
        'active_tab': active_tab,
        'rating': rating,
        'progress_percentage': progress_percentage,
        'range_min': range_min,
        'range_max': range_max,
        'stats': stats,
        'monthly_activity_json': monthly_activity_json,
        'weekday_stats_json': weekday_stats_json,
        'rating_progress_json': rating_progress_json,
    }

    return render(request, 'users/profile.html', context)


from django.contrib.auth.decorators import user_passes_test
from .forms import PlayerRatingForm


def is_coach(user):
    """Проверка, является ли пользователь тренером"""
    return user.groups.filter(name='Тренеры').exists() or user.is_staff


@login_required
def rating_detail(request):
    """Страница с подробной информацией о рейтинге пользователя"""
    rating = request.user.rating

    # История рейтинга
    history = rating.rating_history if hasattr(rating, 'rating_history') else []

    context = {
        'rating': rating,
        'history': reversed(history[-10:]),  # Последние 10 изменений
        'progress_percentage': rating.get_progress_percentage(),
    }

    return render(request, 'users/rating_detail.html', context)


# ==================== СИСТЕМА ТРЕНЕРОВ ====================

@login_required
def coaches_list(request):
    """Список всех тренеров"""
    from .models import CoachProfile

    coaches = CoachProfile.objects.filter(
        is_active=True
    ).select_related('user').order_by('-coach_rating')

    context = {
        'coaches': coaches
    }

    return render(request, 'users/coaches_list.html', context)


@login_required
def coach_detail(request, coach_id):
    """Детальная информация о тренере"""
    from .models import CoachProfile, TrainingSession
    from django.shortcuts import get_object_or_404

    coach_profile = get_object_or_404(CoachProfile, id=coach_id, is_active=True)

    # Получаем прошлые сессии тренера для статистики
    completed_sessions = TrainingSession.objects.filter(
        coach=coach_profile.user,
        status='completed'
    ).count()

    # Получаем будущие сессии (для отображения занятости)
    upcoming_sessions = TrainingSession.objects.filter(
        coach=coach_profile.user,
        status__in=['scheduled', 'in_progress'],
        date__gte=timezone.now().date()
    ).order_by('date', 'start_time')

    context = {
        'coach': coach_profile,
        'completed_sessions': completed_sessions,
        'upcoming_sessions': upcoming_sessions
    }

    return render(request, 'users/coach_detail.html', context)


@login_required
def my_training_sessions(request):
    """Список тренировок пользователя"""
    from .models import TrainingSession

    # Получаем все сессии пользователя
    sessions = TrainingSession.objects.filter(
        player=request.user
    ).select_related('coach', 'court').order_by('-date', '-start_time')

    context = {
        'sessions': sessions
    }

    return render(request, 'users/training_sessions.html', context)


# ==================== СИСТЕМА УВЕДОМЛЕНИЙ ====================

@login_required
def notifications_list(request):
    """Список уведомлений пользователя"""
    from .models import Notification

    # Получаем все уведомления пользователя
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')

    # Разделяем на непрочитанные и прочитанные
    unread_notifications = notifications.filter(is_read=False)
    read_notifications = notifications.filter(is_read=True)[:20]  # Последние 20 прочитанных

    context = {
        'unread_notifications': unread_notifications,
        'read_notifications': read_notifications,
        'unread_count': unread_notifications.count()
    }

    return render(request, 'users/notifications.html', context)


@require_POST
@login_required
def mark_notification_read(request):
    """AJAX пометить уведомление как прочитанное"""
    try:
        from .models import Notification

        notification_id = request.POST.get('notification_id')

        if not notification_id:
            return JsonResponse({
                'success': False,
                'message': 'ID уведомления не указан'
            })

        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=request.user
            )
            notification.mark_as_read()

            return JsonResponse({
                'success': True,
                'message': 'Уведомление отмечено как прочитанное'
            })

        except Notification.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Уведомление не найдено'
            })

    except Exception as e:
        logger.error(f"Notification mark error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@login_required
def mark_all_notifications_read(request):
    """AJAX пометить все уведомления как прочитанные"""
    try:
        from .models import Notification

        # Отмечаем все непрочитанные уведомления пользователя
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())

        return JsonResponse({
            'success': True,
            'message': f'Отмечено как прочитанные: {unread_count}',
            'marked_count': unread_count
        })

    except Exception as e:
        logger.error(f"Mark all notifications error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@login_required
def get_unread_notifications_count(request):
    """AJAX получить количество непрочитанных уведомлений"""
    try:
        from .models import Notification

        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        return JsonResponse({
            'success': True,
            'count': count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_coach)
def update_player_rating(request, user_id):
    """Обновление рейтинга игрока (доступно только тренерам)"""
    try:
        from django.contrib.auth.models import User
        player = User.objects.get(id=user_id)
        rating = player.rating
    except (User.DoesNotExist, PlayerRating.DoesNotExist):
        return JsonResponse({
            'success': False,
            'message': 'Игрок не найден'
        }, status=404)

    if request.method == 'POST':
        form = PlayerRatingForm(request.POST, instance=rating)

        if form.is_valid():
            old_rating = float(rating.numeric_rating)
            rating_obj = form.save(commit=False)
            rating_obj.updated_by = request.user
            rating_obj.save()

            # Добавляем в историю
            comment = form.cleaned_data.get('coach_comment', '')
            rating_obj.add_to_history(
                old_rating=old_rating,
                new_rating=float(rating_obj.numeric_rating),
                updated_by=request.user,
                comment=comment
            )

            return JsonResponse({
                'success': True,
                'message': 'Рейтинг успешно обновлен',
                'numeric_rating': float(rating_obj.numeric_rating),
                'level': rating_obj.level,
                'level_display': rating_obj.get_level_display(),
                'level_display_full': rating_obj.get_level_display_full(),
                'updated_at': rating_obj.updated_at.strftime('%d.%m.%Y %H:%M'),
                'updated_by': request.user.username
            })

        # Ошибки валидации
        errors = {field: [str(e) for e in error_list] for field, error_list in form.errors.items()}

        return JsonResponse({
            'success': False,
            'errors': errors,
            'message': 'Пожалуйста, исправьте ошибки в форме'
        })

    return JsonResponse({
        'success': False,
        'message': 'Метод не разрешен'
    }, status=405)


@login_required
def get_rating_info(request):
    """AJAX получение информации о рейтинге"""
    try:
        rating = request.user.rating

        return JsonResponse({
            'success': True,
            'numeric_rating': float(rating.numeric_rating),
            'level': rating.level,
            'level_display': rating.get_level_display(),
            'level_display_full': rating.get_level_display_full(),
            'progress_percentage': rating.get_progress_percentage(),
            'range_min': float(rating.get_range_min()),
            'range_max': float(rating.get_range_max()),
            'updated_at': rating.updated_at.strftime('%d.%m.%Y %H:%M') if rating.updated_at else '',
            'coach_comment': rating.coach_comment or ''
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }, status=500)