"""
URL routing для админских страниц бронирований
Расписания кортов и тренеров
"""

from django.urls import path
from . import admin_views

urlpatterns = [
    # Расписание кортов
    path('courts/', admin_views.courts_schedule_view, name='admin_courts_schedule'),

    # Расписание тренера
    path('coach/<int:coach_id>/', admin_views.coach_schedule_view, name='admin_coach_schedule'),

    # API endpoints
    path('api/bookings/', admin_views.bookings_list_api, name='admin_bookings_list_api'),
    path('api/booking/create/', admin_views.booking_quick_create_api, name='admin_booking_create_api'),
    path('api/booking/<int:booking_id>/update/', admin_views.booking_update_api, name='admin_booking_update_api'),
    path('api/booking/<int:booking_id>/delete/', admin_views.booking_delete_api, name='admin_booking_delete_api'),
]
