from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from .forms import RegistrationForm, LoginForm, EmailUpdateForm, PhoneVerificationForm, AvatarUploadForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.db.models import Prefetch, Count, Q
from datetime import datetime, timedelta
from booking.models import Booking, Court
import json


@require_POST
@csrf_exempt
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
        print(f"Ошибка при регистрации: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
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
        print(f"Ошибка при входе: {str(e)}")
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
@csrf_exempt
def ajax_logout(request):
    """AJAX выход"""
    logout(request)
    return JsonResponse({
        'success': True,
        'message': 'Вы успешно вышли из аккаунта'
    })


@require_POST
@csrf_exempt
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
        print(f"Ошибка при обновлении email: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
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
        print(f"Ошибка при подтверждении телефона: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
@login_required
def resend_verification_code(request):
    """AJAX повторная отправка кода подтверждения"""
    try:
        if hasattr(request.user, 'profile'):
            # Генерируем новый код
            code = request.user.profile.generate_verification_code()

            # В реальном приложении здесь был бы код отправки SMS
            # Для тестирования просто логируем
            print(f"Код подтверждения для {request.user.profile.phone}: {code}")

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
        print(f"Ошибка при отправке кода: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
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
        print(f"Ошибка при загрузке аватарки: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
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
        print(f"Ошибка при удалении аватарки: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)


@require_POST
@csrf_exempt
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
        print(f"Ошибка при обновлении профиля: {str(e)}")
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

    # Получаем пользователя с профилем
    try:
        user = User.objects.select_related('profile').get(id=request.user.id)
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
    print(f"DEBUG - Рейтинг: {rating.numeric_rating}, Уровень: {rating.level}, Прогресс: {progress_percentage}%")

    # Также получаем границы диапазона для текущего уровня
    range_min = rating.get_range_min()
    range_max = rating.get_range_max()

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