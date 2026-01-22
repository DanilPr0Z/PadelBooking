"""
Manager App URLs
"""

from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    # Pages
    path('', views.dashboard, name='dashboard'),
    path('bookings/', views.bookings_list, name='bookings'),
    path('schedule/', views.schedule, name='schedule'),
    path('analytics/', views.analytics, name='analytics'),
    path('users/', views.users_list, name='users'),
    path('courts/', views.courts_list, name='courts'),

    # API - Dashboard
    path('api/metrics/', views.api_metrics, name='api_metrics'),

    # API - Bookings
    path('api/bookings/', views.api_bookings_list, name='api_bookings_list'),
    path('api/bookings/create/', views.api_booking_create, name='api_booking_create'),
    path('api/bookings/<int:booking_id>/', views.api_booking_detail, name='api_booking_detail'),
    path('api/bookings/<int:booking_id>/update/', views.api_booking_update, name='api_booking_update'),
    path('api/bookings/<int:booking_id>/confirm/', views.api_booking_confirm, name='api_booking_confirm'),
    path('api/bookings/<int:booking_id>/cancel/', views.api_booking_cancel, name='api_booking_cancel'),
    path('api/bookings/<int:booking_id>/delete/', views.api_booking_delete, name='api_booking_delete'),
    path('api/bookings/export/', views.api_bookings_export, name='api_bookings_export'),

    # API - Courts
    path('api/courts/', views.api_courts_list, name='api_courts_list'),
    path('api/courts/create/', views.api_court_create, name='api_court_create'),
    path('api/courts/<int:court_id>/', views.api_court_detail, name='api_court_detail'),
    path('api/courts/<int:court_id>/update/', views.api_court_update, name='api_court_update'),
    path('api/courts/<int:court_id>/delete/', views.api_court_delete, name='api_court_delete'),

    # API - Analytics
    path('api/analytics/', views.api_analytics, name='api_analytics'),
    path('api/analytics/export/', views.api_analytics_export, name='api_analytics_export'),

    # API - Users
    path('api/users/', views.api_users_list, name='api_users_list'),
    path('api/users/create/', views.api_user_create, name='api_user_create'),
    path('api/users/<int:user_id>/', views.api_user_detail, name='api_user_detail'),
    path('api/users/<int:user_id>/update/', views.api_user_update, name='api_user_update'),
    path('api/users/<int:user_id>/delete/', views.api_user_delete, name='api_user_delete'),
    path('api/users/export/', views.api_users_export, name='api_users_export'),

    # API - Schedule
    path('api/schedule/', views.api_schedule, name='api_schedule'),
    path('api/schedule/events/', views.api_schedule_events, name='api_schedule_events'),
    path('api/bookings/<int:booking_id>/update-time/', views.api_booking_update_time, name='api_booking_update_time'),
]
