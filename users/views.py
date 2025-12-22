from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.core.exceptions import ValidationError
import os
from django.conf import settings

from .forms import RegistrationForm, LoginForm, EmailUpdateForm, PhoneVerificationForm, AvatarUploadForm
from .models import UserProfile
from booking.models import Booking


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


@login_required
def profile(request):
    """Страница профиля с обработкой подтверждения телефона"""
    verification_success = None
    verification_error = None

    if request.method == 'POST':
        # Обработка подтверждения телефона (традиционная форма)
        if 'verification_code' in request.POST:
            form = PhoneVerificationForm(request.POST)
            if form.is_valid():
                code = form.cleaned_data['verification_code']

                # Проверяем код
                if request.user.profile.verify_phone(code):
                    verification_success = 'Телефон успешно подтвержден!'
                else:
                    verification_error = 'Неверный код подтверждения'
            else:
                verification_error = 'Неверный формат кода'

    return render(request, 'users/profile.html', {
        'verification_success': verification_success,
        'verification_error': verification_error
    })


def user_logout(request):
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