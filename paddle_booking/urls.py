from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('news/', views.news, name='news'),
    path('booking/', views.booking_page, name='booking'),
    path('tournaments/', views.tournaments, name='tournaments'),
    path('users/', include('users.urls')),  # Все user-related URLs здесь
    path('booking-api/', include('booking.urls')),  # Изменили префикс, чтобы избежать конфликтов
]