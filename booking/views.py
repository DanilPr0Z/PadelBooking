# python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from datetime import datetime
from .models import Booking, Court


@login_required
def my_bookings(request):
    """Показать все бронирования пользователя"""
    bookings = Booking.objects.filter(user=request.user).order_by('-date', '-start_time')
    today = timezone.now().date()
    return render(request, 'users/bookings.html', {'bookings': bookings, 'today': today})


def booking_page(request):
    """Страница бронирования кортов (отдаёт список доступных кортов)"""
    courts = Court.objects.filter(is_available=True).order_by('name')
    today_date = timezone.now().date()
    return render(request, 'booking.html', {'courts': courts, 'today_date': today_date})


def get_available_slots(request):
    """API: возвращает слоты доступности для корта и даты"""
    court_id = request.GET.get('court')
    date_str = request.GET.get('date')

    if not court_id or not date_str:
        return JsonResponse({'success': False, 'message': 'Необходимо указать корт и дату'})

    try:
        court = Court.objects.get(id=court_id, is_available=True)
    except Court.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Корт не найден или недоступен'})

    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Неверный формат даты'})

    if booking_date < timezone.now().date():
        return JsonResponse({'success': False, 'message': 'Нельзя бронировать корт на прошедшую дату'})

    existing_bookings = Booking.objects.filter(
        court=court,
        date=booking_date,
        status__in=['pending', 'confirmed']
    )

    all_slots = []
    for hour in range(8, 22):
        start_time = f"{hour:02d}:00"
        is_available = True

        for booking in existing_bookings:
            booking_start = booking.start_time.strftime('%H:%M')
            booking_end = booking.end_time.strftime('%H:%M')
            if booking_start <= start_time < booking_end:
                is_available = False
                break

        all_slots.append({'start_time': start_time, 'is_available': is_available})

    return JsonResponse({
        'success': True,
        'slots': all_slots,
        'court_price': float(court.price_per_hour)
    })


@login_required
@require_POST
def create_booking(request):
    """Создание нового бронирования"""
    try:
        court_id = request.POST.get('court_id')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')

        if not all([court_id, date_str, start_time_str, end_time_str]):
            messages.error(request, 'Все поля должны быть заполнены')
            return redirect('booking')

        court = get_object_or_404(Court, id=court_id, is_available=True)
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        if booking_date < timezone.now().date():
            messages.error(request, 'Нельзя бронировать корт на прошедшую дату')
            return redirect('booking')

        existing_bookings = Booking.objects.filter(
            court=court,
            date=booking_date,
            status__in=['pending', 'confirmed']
        )

        for booking in existing_bookings:
            if (booking.start_time <= start_time < booking.end_time or
                booking.start_time < end_time <= booking.end_time or
                (start_time <= booking.start_time and end_time >= booking.end_time)):
                messages.error(request, 'Выбранное время уже занято')
                return redirect('booking')

        Booking.objects.create(
            user=request.user,
            court=court,
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            status='pending'
        )

        messages.success(request, 'Бронирование успешно создано!')
        return redirect('my_bookings')

    except Exception as e:
        messages.error(request, f'Ошибка при создании бронирования: {str(e)}')
        return redirect('booking')


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Отмена бронирования"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.status == 'cancelled':
        messages.error(request, 'Это бронирование уже отменено')
    elif booking.date < timezone.now().date():
        messages.error(request, 'Нельзя отменить прошедшее бронирование')
    else:
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, 'Бронирование успешно отменено')

    return redirect('my_bookings')
