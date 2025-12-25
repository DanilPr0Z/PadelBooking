from django.shortcuts import render
from booking.models import Court
from django.utils import timezone


def home(request):
    return render(request, 'home.html')


def news(request):
    return render(request, 'news.html')


def booking_page(request):
    """Страница бронирования кортов"""
    # Получаем все доступные корты
    courts = Court.objects.filter(is_available=True).order_by('name')
    today_date = timezone.now().date()

    # Отладка (можно убрать после проверки)
    print(f"DEBUG: Передано {courts.count()} кортов в шаблон")
    for court in courts:
        print(f"  - {court.name}: {court.price_per_hour} руб/час, доступен: {court.is_available}")

    return render(request, 'booking.html', {
        'courts': courts,
        'today_date': today_date
    })


def tournaments(request):
    return render(request, 'tournaments.html')