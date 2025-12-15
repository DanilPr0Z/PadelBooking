from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

from .forms import RegistrationForm, LoginForm
from booking.models import Booking


@require_POST
@csrf_exempt
def ajax_register(request):
    """AJAX регистрация - исправленная версия"""
    form = RegistrationForm(request.POST)

    if form.is_valid():
        user = form.save()
        login(request, user)
        return JsonResponse({
            'success': True,
            'message': 'Регистрация успешна!',
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

@require_POST
@csrf_exempt
def ajax_login(request):
    """AJAX вход"""
    form = LoginForm(request.POST)

    if form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Вход выполнен успешно!',
                'username': user.username
            })

    return JsonResponse({
        'success': False,
        'message': 'Неверное имя пользователя или пароль'
    })


def user_login(request):
    """Стандартный вход (для обратной совместимости)"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
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
    return render(request, 'users/profile.html')


def user_logout(request):
    logout(request)
    return redirect('home')

from django.views.decorators.http import require_POST

@require_POST
@csrf_exempt
def ajax_logout(request):
    """AJAX выход"""
    logout(request)
    return JsonResponse({
        'success': True,
        'message': 'Вы успешно вышли из аккаунта'
    })