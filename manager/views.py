"""
Manager App Views
Современная админ-панель для управления бронированиями
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q, Sum
from django.views.decorators.http import require_POST
import csv

from booking.models import Booking, Court
from booking.analytics import get_financial_stats, get_occupancy_stats, get_clients_stats


@staff_member_required
def dashboard(request):
    """Главная страница менеджера с метриками"""
    context = {'current_page': 'dashboard'}
    return render(request, 'manager/dashboard.html', context)


@staff_member_required
def bookings_list(request):
    """Список бронирований с фильтрами и поиском"""
    context = {'current_page': 'bookings'}
    return render(request, 'manager/bookings.html', context)


@staff_member_required
def schedule(request):
    """Расписание кортов и тренеров"""
    courts = Court.objects.filter(is_available=True).order_by('name')
    context = {'current_page': 'schedule', 'courts': courts}
    return render(request, 'manager/schedule.html', context)


@staff_member_required
def analytics(request):
    """Детальная аналитика"""
    context = {'current_page': 'analytics'}
    return render(request, 'manager/analytics.html', context)


@staff_member_required
def users_list(request):
    """Управление пользователями"""
    context = {'current_page': 'users'}
    return render(request, 'manager/users.html', context)


@staff_member_required
def courts_list(request):
    """Управление кортами"""
    context = {'current_page': 'courts'}
    return render(request, 'manager/courts.html', context)


@staff_member_required
def api_metrics(request):
    """API: Получить основные метрики для dashboard"""
    try:
        today = timezone.now().date()
        start_date = today - timedelta(days=30)

        financial = get_financial_stats(start_date, today)
        occupancy = get_occupancy_stats(start_date, today)
        clients = get_clients_stats(start_date, today)

        # Подготовка данных для графиков
        # График дохода за последние 7 дней
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        revenue_trend = []

        daily_revenue_dict = {item['day']: item for item in financial['daily_revenue']}

        for day in last_7_days:
            revenue_trend.append({
                'day': day.isoformat(),
                'revenue': daily_revenue_dict.get(day, {'revenue': 0})['revenue']
            })

        # График загруженности по часам
        occupancy_trend = occupancy['hourly_occupancy']

        return JsonResponse({
            'success': True,
            'metrics': {
                'total_revenue': financial['total_revenue'],
                'paid_amount': financial['paid_amount'],
                'total_bookings': occupancy['total_bookings'],
                'occupancy_rate': occupancy['overall_occupancy_rate'],
                'new_users': clients['new_users'],
                'active_users': clients['active_users'],
            },
            'charts': {
                'revenue_trend': revenue_trend,
                'occupancy_trend': occupancy_trend
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# API ENDPOINTS FOR BOOKINGS
# =============================================================================

@staff_member_required
def api_bookings_list(request):
    """API: Список всех бронирований"""
    try:
        # Ограничиваем выборку последними 100 бронированиями для производительности
        bookings = Booking.objects.select_related('court', 'user', 'coach').order_by('-date', '-start_time')[:100]

        # Формируем данные для отображения
        bookings_data = []
        for booking in bookings:
            bookings_data.append({
                'id': booking.id,
                'date': booking.date.isoformat(),
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'court_id': booking.court.id,
                'court_name': booking.court.name,
                'user_id': booking.user.id,
                'user_name': booking.user.get_full_name() or booking.user.username,
                'coach_name': f"{booking.coach.first_name} {booking.coach.last_name}" if booking.coach else None,
                'status': booking.status,
                'total_price': float(booking.total_price),
            })

        # Статистика за сегодня
        today = timezone.now().date()
        today_bookings = Booking.objects.filter(date=today)

        stats = {
            'total_today': today_bookings.count(),
            'confirmed_today': today_bookings.filter(status='confirmed').count(),
            'pending_today': today_bookings.filter(status='pending').count(),
            'revenue_today': sum(float(b.total_price) for b in today_bookings.filter(status='confirmed'))
        }

        return JsonResponse({
            'success': True,
            'bookings': bookings_data,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_booking_detail(request, booking_id):
    """API: Детали конкретного бронирования"""
    try:
        booking = get_object_or_404(Booking.objects.select_related('court', 'user', 'coach'), id=booking_id)

        booking_data = {
            'id': booking.id,
            'date': booking.date.isoformat(),
            'start_time': booking.start_time.strftime('%H:%M'),
            'end_time': booking.end_time.strftime('%H:%M'),
            'court_id': booking.court.id,
            'court_name': booking.court.name,
            'user_id': booking.user.id,
            'user_name': booking.user.get_full_name() or booking.user.username,
            'user_email': booking.user.email,
            'coach_name': f"{booking.coach.first_name} {booking.coach.last_name}" if booking.coach else None,
            'status': booking.status,
            'total_price': float(booking.total_price),
            'created_at': booking.created_at.isoformat() if hasattr(booking, 'created_at') else None,
        }

        return JsonResponse({
            'success': True,
            'booking': booking_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_booking_confirm(request, booking_id):
    """API: Подтвердить бронирование"""
    try:
        booking = get_object_or_404(Booking, id=booking_id)

        if booking.status == 'confirmed':
            return JsonResponse({'success': False, 'error': 'Бронирование уже подтверждено'})

        booking.status = 'confirmed'
        booking.save()

        return JsonResponse({
            'success': True,
            'message': 'Бронирование подтверждено'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_booking_cancel(request, booking_id):
    """API: Отменить бронирование"""
    try:
        booking = get_object_or_404(Booking, id=booking_id)

        if booking.status == 'cancelled':
            return JsonResponse({'success': False, 'error': 'Бронирование уже отменено'})

        booking.status = 'cancelled'
        booking.save()

        return JsonResponse({
            'success': True,
            'message': 'Бронирование отменено'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_courts_list(request):
    """API: Список всех кортов"""
    try:
        courts = Court.objects.all().order_by('name')

        courts_data = [
            {
                'id': court.id,
                'name': court.name,
                'price_per_hour': float(court.price_per_hour),
                'is_available': court.is_available,
            }
            for court in courts
        ]

        # Статистика
        stats = {
            'total_courts': courts.count(),
            'available_courts': courts.filter(is_available=True).count(),
            'unavailable_courts': courts.filter(is_available=False).count(),
        }

        return JsonResponse({
            'success': True,
            'courts': courts_data,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_court_detail(request, court_id):
    """API: Детали конкретного корта"""
    try:
        court = get_object_or_404(Court, id=court_id)

        court_data = {
            'id': court.id,
            'name': court.name,
            'price_per_hour': float(court.price_per_hour),
            'is_available': court.is_available,
        }

        # Статистика по корту
        today = timezone.now().date()
        bookings_today = Booking.objects.filter(court=court, date=today).count()
        total_bookings = Booking.objects.filter(court=court).count()

        court_data['bookings_today'] = bookings_today
        court_data['total_bookings'] = total_bookings

        return JsonResponse({
            'success': True,
            'court': court_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_court_create(request):
    """API: Создать новый корт"""
    try:
        import json

        data = json.loads(request.body)

        # Валидация
        name = data.get('name', '').strip()
        price_per_hour = data.get('price_per_hour')
        is_available = data.get('is_available', True)

        if not name:
            return JsonResponse({'success': False, 'error': 'Название обязательно'}, status=400)
        if not price_per_hour:
            return JsonResponse({'success': False, 'error': 'Цена за час обязательна'}, status=400)

        try:
            price_per_hour = float(price_per_hour)
            if price_per_hour <= 0:
                return JsonResponse({'success': False, 'error': 'Цена должна быть больше 0'}, status=400)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Неверный формат цены'}, status=400)

        # Проверка на существование
        if Court.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'error': 'Корт с таким названием уже существует'}, status=400)

        # Создание корта
        court = Court.objects.create(
            name=name,
            price_per_hour=price_per_hour,
            is_available=is_available
        )

        return JsonResponse({
            'success': True,
            'message': 'Корт успешно создан',
            'court': {
                'id': court.id,
                'name': court.name,
                'price_per_hour': float(court.price_per_hour),
                'is_available': court.is_available,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_court_update(request, court_id):
    """API: Обновить корт"""
    try:
        import json

        court = get_object_or_404(Court, id=court_id)
        data = json.loads(request.body)

        # Обновление полей
        if 'name' in data:
            name = data['name'].strip()
            if name != court.name and Court.objects.filter(name=name).exists():
                return JsonResponse({'success': False, 'error': 'Корт с таким названием уже существует'}, status=400)
            court.name = name

        if 'price_per_hour' in data:
            try:
                price = float(data['price_per_hour'])
                if price <= 0:
                    return JsonResponse({'success': False, 'error': 'Цена должна быть больше 0'}, status=400)
                court.price_per_hour = price
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Неверный формат цены'}, status=400)

        if 'is_available' in data:
            court.is_available = data['is_available']

        court.save()

        return JsonResponse({
            'success': True,
            'message': 'Корт успешно обновлен',
            'court': {
                'id': court.id,
                'name': court.name,
                'price_per_hour': float(court.price_per_hour),
                'is_available': court.is_available,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_court_delete(request, court_id):
    """API: Удалить корт"""
    try:
        court = get_object_or_404(Court, id=court_id)

        # Проверка на наличие бронирований
        future_bookings = Booking.objects.filter(
            court=court,
            date__gte=timezone.now().date(),
            status__in=['pending', 'confirmed']
        ).count()

        if future_bookings > 0:
            return JsonResponse({
                'success': False,
                'error': f'Нельзя удалить корт. Есть {future_bookings} активных бронирований'
            }, status=400)

        court_name = court.name
        court.delete()

        return JsonResponse({
            'success': True,
            'message': f'Корт "{court_name}" успешно удален'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_bookings_export(request):
    """API: Экспорт бронирований в CSV"""
    try:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="bookings_{timezone.now().date()}.csv"'

        # Добавляем BOM для корректного отображения в Excel
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['ID', 'Дата', 'Время начала', 'Время окончания', 'Корт', 'Клиент', 'Email', 'Тренер',
                         'Статус', 'Сумма'])

        bookings = Booking.objects.select_related('court', 'user', 'coach').order_by('-date')

        for booking in bookings:
            writer.writerow([
                booking.id,
                booking.date.strftime('%Y-%m-%d'),
                booking.start_time.strftime('%H:%M'),
                booking.end_time.strftime('%H:%M'),
                booking.court.name,
                booking.user.get_full_name() or booking.user.username,
                booking.user.email,
                f"{booking.coach.first_name} {booking.coach.last_name}" if booking.coach else '',
                booking.status,
                float(booking.total_price)
            ])

        return response
    except Exception as e:
        return HttpResponse(f'Ошибка: {str(e)}', status=500)


# =============================================================================
# API ENDPOINTS FOR ANALYTICS
# =============================================================================

@staff_member_required
def api_analytics(request):
    """API: Полная аналитика"""
    try:
        days = int(request.GET.get('days', 30))
        today = timezone.now().date()
        start_date = today - timedelta(days=days)

        financial = get_financial_stats(start_date, today)
        occupancy = get_occupancy_stats(start_date, today)
        clients = get_clients_stats(start_date, today)

        return JsonResponse({
            'success': True,
            'financial': financial,
            'occupancy': occupancy,
            'clients': clients
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_analytics_export(request):
    """API: Экспорт аналитики в CSV"""
    try:
        days = int(request.GET.get('days', 30))
        today = timezone.now().date()
        start_date = today - timedelta(days=days)

        financial = get_financial_stats(start_date, today)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="analytics_{today}.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['Аналитика за период', start_date, '-', today])
        writer.writerow([])

        # Financial data
        writer.writerow(['Финансовая аналитика'])
        writer.writerow(['Показатель', 'Значение'])
        writer.writerow(['Общий доход', financial['total_revenue']])
        writer.writerow(['Оплачено', financial['paid_amount']])
        writer.writerow(['Неоплачено', financial['unpaid_amount']])
        writer.writerow(['Средний доход в день', financial['avg_daily_revenue']])
        writer.writerow(['Прогноз на месяц', financial['forecast_next_month']])
        writer.writerow([])

        # Daily revenue
        writer.writerow(['Доход по дням'])
        writer.writerow(['Дата', 'Доход', 'Бронирований'])
        for day in financial['daily_revenue']:
            writer.writerow([day['day'], day['revenue'], day['bookings_count']])

        return response
    except Exception as e:
        return HttpResponse(f'Ошибка: {str(e)}', status=500)


# =============================================================================
# API ENDPOINTS FOR USERS
# =============================================================================

@staff_member_required
def api_users_list(request):
    """API: Список всех пользователей"""
    try:
        from django.contrib.auth.models import User

        # Ограничиваем выборку для производительности
        users = User.objects.all().order_by('-date_joined')[:100]

        # Формируем данные для отображения
        users_data = []
        for user in users:
            # Подсчитываем бронирования и потраченную сумму
            user_bookings = Booking.objects.filter(user=user, status='confirmed')
            total_spent = sum(float(b.total_price) for b in user_bookings)

            # Получаем данные профиля и рейтинга
            phone = None
            email_verified = False
            if hasattr(user, 'profile'):
                phone = user.profile.phone
                email_verified = user.profile.email_verified

            rating_level = None
            rating_progress = 0
            if hasattr(user, 'rating'):
                rating_level = user.rating.level
                rating_progress = user.rating.get_progress_percentage()

            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone': phone,
                'email_verified': email_verified,
                'rating_level': rating_level,
                'rating_progress': rating_progress,
                'full_name': user.get_full_name(),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'bookings_count': user_bookings.count(),
                'total_spent': total_spent,
            })

        # Статистика
        today = timezone.now().date()
        last_month = today - timedelta(days=30)

        # Исправление: правильные пути к полям
        from django.contrib.auth.models import User as AuthUser
        all_users = AuthUser.objects.all()

        stats = {
            'total_users': all_users.count(),
            'active_users': all_users.filter(
                Q(bookings_created__date__gte=last_month) |
                Q(bookings_as_partner__date__gte=last_month) |
                Q(bookings_as_coach__date__gte=last_month)
            ).distinct().count(),
            'new_users': all_users.filter(date_joined__date__gte=last_month).count(),
            'staff_users': all_users.filter(is_staff=True).count(),
        }

        return JsonResponse({
            'success': True,
            'users': users_data,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_user_detail(request, user_id):
    """API: Детали конкретного пользователя"""
    try:
        from django.contrib.auth.models import User

        user = get_object_or_404(User, id=user_id)

        # Подсчитываем бронирования и потраченную сумму
        user_bookings = Booking.objects.filter(user=user, status='confirmed')
        total_spent = sum(float(b.total_price) for b in user_bookings)

        # Получаем данные профиля и рейтинга
        phone = None
        email_verified = False
        if hasattr(user, 'profile'):
            phone = user.profile.phone
            email_verified = user.profile.email_verified

        rating_level = None
        rating_progress = 0
        if hasattr(user, 'rating'):
            rating_level = user.rating.level
            rating_progress = user.rating.get_progress_percentage()

        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': phone,
            'email_verified': email_verified,
            'rating_level': rating_level,
            'rating_progress': rating_progress,
            'full_name': user.get_full_name(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'is_superuser': user.is_superuser,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'bookings_count': user_bookings.count(),
            'total_spent': total_spent,
        }

        return JsonResponse({
            'success': True,
            'user': user_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_users_export(request):
    """API: Экспорт пользователей в CSV"""
    try:
        from django.contrib.auth.models import User

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="users_{timezone.now().date()}.csv"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['ID', 'Username', 'Email', 'Имя', 'Фамилия', 'Роль', 'Статус',
                         'Зарегистрирован', 'Бронирований', 'Потрачено'])

        users = User.objects.all().order_by('-date_joined')

        for user in users:
            user_bookings = Booking.objects.filter(user=user, status='confirmed')
            total_spent = sum(float(b.total_price) for b in user_bookings)

            writer.writerow([
                user.id,
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                'Персонал' if user.is_staff else 'Клиент',
                'Активен' if user.is_active else 'Неактивен',
                user.date_joined.strftime('%Y-%m-%d'),
                user_bookings.count(),
                total_spent
            ])

        return response
    except Exception as e:
        return HttpResponse(f'Ошибка: {str(e)}', status=500)


@staff_member_required
@require_POST
def api_user_create(request):
    """API: Создать нового пользователя"""
    try:
        import json
        from django.contrib.auth.models import User

        data = json.loads(request.body)

        # Валидация
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        phone_number = data.get('phone_number', '').strip()
        email_verified = data.get('email_verified', False)
        rating_level = data.get('rating_level')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        is_staff = data.get('is_staff', False)
        is_active = data.get('is_active', True)

        if not username:
            return JsonResponse({'success': False, 'error': 'Username обязателен'}, status=400)
        if not email:
            return JsonResponse({'success': False, 'error': 'Email обязателен'}, status=400)
        if not password:
            return JsonResponse({'success': False, 'error': 'Пароль обязателен'}, status=400)
        if not phone_number:
            return JsonResponse({'success': False, 'error': 'Номер телефона обязателен'}, status=400)

        # Проверка на существование
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Пользователь с таким username уже существует'}, status=400)
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'Пользователь с таким email уже существует'}, status=400)

        # Проверка на существование телефона
        from users.models import UserProfile
        if UserProfile.objects.filter(phone=phone_number).exists():
            return JsonResponse({'success': False, 'error': 'Номер телефона уже используется'}, status=400)

        # Получение is_superuser
        is_superuser = data.get('is_superuser', False)

        # Создание пользователя
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=is_staff,
            is_active=is_active,
            is_superuser=is_superuser
        )

        # Создание/обновление профиля
        from users.models import UserProfile, PlayerRating
        if hasattr(user, 'profile'):
            # Обновляем существующий профиль
            user.profile.phone = phone_number
            user.profile.email_verified = email_verified
            user.profile.save()
        else:
            # Создаем новый профиль
            UserProfile.objects.create(
                user=user,
                phone=phone_number,
                email_verified=email_verified
            )

        # Обновление рейтинга если указан уровень (рейтинг создается автоматически через сигнал)
        if rating_level:
            # Находим соответствующий numeric_rating для уровня
            level_to_rating = {
                'D': 1.25, 'D+': 2.00, 'C-': 2.80, 'C': 3.30, 'C+': 3.80,
                'B-': 4.30, 'B': 4.80, 'B+': 5.30, 'A': 6.00, 'PRO': 6.80
            }
            numeric_rating = level_to_rating.get(rating_level, 1.00)

            # Рейтинг уже создан сигналом, просто обновляем его
            rating = PlayerRating.objects.get(user=user)
            rating.numeric_rating = numeric_rating
            rating.updated_by = request.user
            rating.save()

        return JsonResponse({
            'success': True,
            'message': 'Пользователь успешно создан',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name(),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_user_update(request, user_id):
    """API: Обновить пользователя"""
    try:
        import json
        from django.contrib.auth.models import User

        user = get_object_or_404(User, id=user_id)
        data = json.loads(request.body)

        # Обновление полей
        if 'email' in data:
            email = data['email'].strip()
            if email != user.email and User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'error': 'Email уже используется'}, status=400)
            user.email = email

        if 'first_name' in data:
            user.first_name = data['first_name'].strip()
        if 'last_name' in data:
            user.last_name = data['last_name'].strip()
        if 'is_staff' in data:
            user.is_staff = data['is_staff']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'is_superuser' in data:
            user.is_superuser = data['is_superuser']

        # Обновление пароля (если указан)
        if 'password' in data and data['password']:
            user.set_password(data['password'])

        user.save()

        # Обновление профиля
        from users.models import UserProfile, PlayerRating
        if 'phone_number' in data or 'email_verified' in data:
            if hasattr(user, 'profile'):
                if 'phone_number' in data:
                    phone_number = data['phone_number'].strip()
                    # Проверка уникальности телефона
                    if phone_number != user.profile.phone and UserProfile.objects.filter(phone=phone_number).exists():
                        return JsonResponse({'success': False, 'error': 'Номер телефона уже используется'}, status=400)
                    user.profile.phone = phone_number
                if 'email_verified' in data:
                    user.profile.email_verified = data['email_verified']
                user.profile.save()
            else:
                # Создаем профиль если его нет
                phone_number = data.get('phone_number', '+79800000000').strip()
                UserProfile.objects.create(
                    user=user,
                    phone=phone_number,
                    email_verified=data.get('email_verified', False)
                )

        # Обновление рейтинга
        if 'rating_level' in data:
            rating_level = data['rating_level']
            if rating_level:
                # Находим соответствующий numeric_rating для уровня
                level_to_rating = {
                    'D': 1.25, 'D+': 2.00, 'C-': 2.80, 'C': 3.30, 'C+': 3.80,
                    'B-': 4.30, 'B': 4.80, 'B+': 5.30, 'A': 6.00, 'PRO': 6.80
                }
                numeric_rating = level_to_rating.get(rating_level, 1.00)

                if hasattr(user, 'rating'):
                    old_rating = user.rating.numeric_rating
                    user.rating.numeric_rating = numeric_rating
                    user.rating.updated_by = request.user
                    user.rating.save()
                    # Добавляем в историю
                    user.rating.add_to_history(
                        old_rating=old_rating,
                        new_rating=numeric_rating,
                        updated_by=request.user,
                        comment='Обновлено через админ-панель'
                    )
                else:
                    PlayerRating.objects.create(
                        user=user,
                        numeric_rating=numeric_rating,
                        updated_by=request.user
                    )

        return JsonResponse({
            'success': True,
            'message': 'Пользователь успешно обновлен',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.get_full_name(),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'is_superuser': user.is_superuser,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_user_delete(request, user_id):
    """API: Удалить пользователя"""
    try:
        from django.contrib.auth.models import User

        user = get_object_or_404(User, id=user_id)

        # Защита от удаления самого себя
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'Вы не можете удалить себя'}, status=400)

        # Защита от удаления суперпользователя
        if user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Нельзя удалить суперпользователя'}, status=400)

        username = user.username
        user.delete()

        return JsonResponse({
            'success': True,
            'message': f'Пользователь {username} успешно удален'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =============================================================================
# API ENDPOINTS FOR SCHEDULE
# =============================================================================

@staff_member_required
def api_schedule(request):
    """API: Расписание на конкретную дату"""
    try:
        from datetime import datetime as dt

        date_str = request.GET.get('date')
        court_id = request.GET.get('court_id')

        if not date_str:
            date = timezone.now().date()
        else:
            date = dt.strptime(date_str, '%Y-%m-%d').date()

        # Фильтруем бронирования по дате
        bookings = Booking.objects.filter(date=date).select_related('court', 'user', 'coach').order_by('start_time')

        # Дополнительный фильтр по корту если указан
        if court_id:
            bookings = bookings.filter(court_id=court_id)

        # Формируем данные
        schedule_data = []
        for booking in bookings:
            schedule_data.append({
                'id': booking.id,
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'court_id': booking.court.id,
                'court_name': booking.court.name,
                'user_id': booking.user.id,
                'user_name': booking.user.get_full_name() or booking.user.username,
                'coach_name': f"{booking.coach.first_name} {booking.coach.last_name}" if booking.coach else None,
                'status': booking.status,
            })

        return JsonResponse({
            'success': True,
            'schedule': schedule_data,
            'date': date.isoformat()
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def api_schedule_events(request):
    """API: События для FullCalendar (неделя)"""
    try:
        from datetime import datetime as dt
        import re

        start_str = request.GET.get('start')
        end_str = request.GET.get('end')
        court_id = request.GET.get('court_id')

        # Проверка обязательных параметров
        if not start_str or not end_str:
            return JsonResponse({
                'success': False,
                'error': 'Требуются параметры start и end'
            }, status=400)

        # Функция для парсинга даты с разными форматами
        def parse_date_string(date_str):
            # Убираем 'Z' в конце и заменяем на +00:00
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'

            # Исправляем случай, когда между временем и часовым поясом пробел вместо знака
            # Например: '2026-01-19T00:00:00 04:00' -> '2026-01-19T00:00:00+04:00'
            date_str = re.sub(r'(\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2})$', r'\1+\2', date_str)

            # Если уже есть часовой пояс, оставляем как есть
            # Формат: 2026-01-19T00:00:00+04:00
            try:
                return dt.fromisoformat(date_str)
            except ValueError:
                # Если не получилось, пробуем убрать часовой пояс
                date_str_no_tz = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)
                return dt.fromisoformat(date_str_no_tz)

        start = parse_date_string(start_str)
        end = parse_date_string(end_str)

        # Фильтруем бронирования по диапазону дат
        bookings = Booking.objects.filter(
            date__gte=start.date(),
            date__lte=end.date()
        ).select_related('court', 'user', 'coach')

        # Дополнительный фильтр по корту
        if court_id:
            bookings = bookings.filter(court_id=court_id)

        # Формируем события для FullCalendar
        events = []
        for booking in bookings:
            # Создаем datetime объекты для start и end
            booking_start = dt.combine(booking.date, booking.start_time)
            booking_end = dt.combine(booking.date, booking.end_time)

            events.append({
                'id': booking.id,
                'title': booking.user.get_full_name() or booking.user.username,
                'start': booking_start.isoformat(),
                'end': booking_end.isoformat(),
                'user_name': booking.user.get_full_name() or booking.user.username,
                'court_name': booking.court.name,
                'status': booking.status,
            })

        return JsonResponse({
            'success': True,
            'events': events
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in api_schedule_events: {error_details}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@require_POST
def api_booking_update_time(request, booking_id):
    """API: Обновить время бронирования (drag-and-drop)"""
    try:
        import json
        from datetime import datetime as dt
        from django.utils import timezone as tz

        booking = get_object_or_404(Booking, id=booking_id)
        data = json.loads(request.body)

        # Парсим новые даты
        new_start = dt.fromisoformat(data['start'].replace('Z', '+00:00'))
        new_end = dt.fromisoformat(data['end'].replace('Z', '+00:00'))

        # Проверка на прошедшую дату
        if new_start.date() < tz.now().date():
            return JsonResponse({
                'success': False,
                'error': 'Нельзя переносить бронирование на прошедшую дату'
            }, status=400)

        # Проверка на конфликты бронирований (исключая текущее бронирование)
        conflicts = Booking.objects.filter(
            court=booking.court,
            date=new_start.date(),
            status__in=['pending', 'confirmed']
        ).exclude(
            id=booking.id
        ).exclude(
            Q(end_time__lte=new_start.time()) | Q(start_time__gte=new_end.time())
        )

        if conflicts.exists():
            conflict = conflicts.first()
            return JsonResponse({
                'success': False,
                'error': f'Конфликт с другим бронированием ({conflict.start_time.strftime("%H:%M")} - {conflict.end_time.strftime("%H:%M")})'
            }, status=400)

        # Обновляем дату и время
        booking.date = new_start.date()
        booking.start_time = new_start.time()
        booking.end_time = new_end.time()
        booking.save()

        return JsonResponse({
            'success': True,
            'message': 'Время бронирования обновлено'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_booking_create(request):
    """API: Создать новое бронирование"""
    try:
        import json
        from datetime import datetime as dt, time
        from django.contrib.auth.models import User

        data = json.loads(request.body)

        # Валидация обязательных полей
        date_str = data.get('date')
        start_time_str = data.get('start_time')
        end_time_str = data.get('end_time')
        court_id = data.get('court_id')
        user_id = data.get('user_id')

        if not all([date_str, start_time_str, end_time_str, court_id, user_id]):
            return JsonResponse({'success': False, 'error': 'Заполните все обязательные поля'}, status=400)

        # Парсинг даты и времени
        booking_date = dt.strptime(date_str, '%Y-%m-%d').date()
        start_time = dt.strptime(start_time_str, '%H:%M').time()
        end_time = dt.strptime(end_time_str, '%H:%M').time()

        # Получение связанных объектов
        court = get_object_or_404(Court, id=court_id)
        user = get_object_or_404(User, id=user_id)

        # Проверка на прошедшую дату
        from django.utils import timezone as tz
        if booking_date < tz.now().date():
            return JsonResponse({
                'success': False,
                'error': 'Нельзя создавать бронирования на прошедшие даты'
            }, status=400)

        # Получение тренера (опционально)
        coach_id = data.get('coach_id')
        coach = None
        if coach_id:
            coach = get_object_or_404(User, id=coach_id, is_staff=True)

        # Проверка на конфликты бронирований
        conflicts = Booking.objects.filter(
            court=court,
            date=booking_date,
            status__in=['pending', 'confirmed']
        ).exclude(
            Q(end_time__lte=start_time) | Q(start_time__gte=end_time)
        )

        if conflicts.exists():
            return JsonResponse({
                'success': False,
                'error': 'На это время уже есть бронирование'
            }, status=400)

        # Получение дополнительных полей
        booking_type = data.get('booking_type', 'game')
        looking_for_partner = data.get('looking_for_partner', False)
        max_players = data.get('max_players', 4)
        partners = data.get('partners', [])
        required_rating_levels = data.get('required_rating_levels', [])

        # Создание бронирования (total_price - это property, рассчитывается автоматически)
        booking = Booking.objects.create(
            court=court,
            user=user,
            coach=coach,
            date=booking_date,
            start_time=start_time,
            end_time=end_time,
            status=data.get('status', 'pending'),
            booking_type=booking_type,
            looking_for_partner=looking_for_partner,
            max_players=max_players,
            required_rating_levels=required_rating_levels
        )

        # Добавляем партнеров (ManyToMany - нужно добавлять после создания объекта)
        if partners:
            for partner_id in partners:
                try:
                    partner = User.objects.get(id=partner_id)
                    booking.partners.add(partner)
                except User.DoesNotExist:
                    pass

        return JsonResponse({
            'success': True,
            'message': 'Бронирование успешно создано',
            'booking': {
                'id': booking.id,
                'date': booking.date.isoformat(),
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'court_name': booking.court.name,
                'user_name': booking.user.get_full_name() or booking.user.username,
                'status': booking.status,
                'total_price': float(booking.total_price),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_booking_update(request, booking_id):
    """API: Обновить бронирование"""
    try:
        import json
        from datetime import datetime as dt
        from django.contrib.auth.models import User

        booking = get_object_or_404(Booking, id=booking_id)
        data = json.loads(request.body)

        # Обновление полей
        if 'date' in data:
            new_date = dt.strptime(data['date'], '%Y-%m-%d').date()
            # Проверка на прошедшую дату
            from django.utils import timezone as tz
            if new_date < tz.now().date():
                return JsonResponse({
                    'success': False,
                    'error': 'Нельзя переносить бронирование на прошедшую дату'
                }, status=400)
            booking.date = new_date

        if 'start_time' in data:
            booking.start_time = dt.strptime(data['start_time'], '%H:%M').time()

        if 'end_time' in data:
            booking.end_time = dt.strptime(data['end_time'], '%H:%M').time()

        if 'court_id' in data:
            booking.court = get_object_or_404(Court, id=data['court_id'])

        if 'user_id' in data:
            booking.user = get_object_or_404(User, id=data['user_id'])

        if 'coach_id' in data:
            if data['coach_id']:
                booking.coach = get_object_or_404(User, id=data['coach_id'], is_staff=True)
            else:
                booking.coach = None

        if 'status' in data:
            booking.status = data['status']

        if 'booking_type' in data:
            booking.booking_type = data['booking_type']

        if 'looking_for_partner' in data:
            booking.looking_for_partner = data['looking_for_partner']

        if 'max_players' in data:
            booking.max_players = data['max_players']

        if 'required_rating_levels' in data:
            booking.required_rating_levels = data['required_rating_levels']

        # Обновление партнеров
        if 'partners' in data:
            booking.partners.clear()
            for partner_id in data['partners']:
                try:
                    partner = User.objects.get(id=partner_id)
                    booking.partners.add(partner)
                except User.DoesNotExist:
                    pass

        # total_price пересчитывается автоматически как property
        booking.save()

        return JsonResponse({
            'success': True,
            'message': 'Бронирование успешно обновлено',
            'booking': {
                'id': booking.id,
                'date': booking.date.isoformat(),
                'start_time': booking.start_time.strftime('%H:%M'),
                'end_time': booking.end_time.strftime('%H:%M'),
                'court_name': booking.court.name,
                'user_name': booking.user.get_full_name() or booking.user.username,
                'status': booking.status,
                'total_price': float(booking.total_price),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_POST
def api_booking_delete(request, booking_id):
    """API: Удалить бронирование"""
    try:
        booking = get_object_or_404(Booking, id=booking_id)

        booking_info = f"#{booking.id} - {booking.date} {booking.start_time}"
        booking.delete()

        return JsonResponse({
            'success': True,
            'message': f'Бронирование {booking_info} успешно удалено'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
