from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from . import views

urlpatterns = [
                  path('admin/', admin.site.urls),

                  # Главная страница
                  path('', views.home, name='home'),

                  # Новости
                  path('news/', TemplateView.as_view(template_name='news.html'), name='news'),

                  # Турниры
                  path('tournaments/', TemplateView.as_view(template_name='tournaments.html'), name='tournaments'),

                  # Бронирование - основное приложение
                  path('booking/', include('booking.urls')),

                  # Пользователи - отдельное приложение
                  path('users/', include('users.urls')),
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)