from django.contrib import admin
from django.urls import path, include
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('news/', views.news, name='news'),
    path('booking/', views.booking_page, name='booking'),
    path('tournaments/', views.tournaments, name='tournaments'),
    path('users/', include('users.urls')),  # Все user-related URLs здесь
    path('booking-api/', include('booking.urls')),  # Изменили префикс, чтобы избежать конфликтов
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)