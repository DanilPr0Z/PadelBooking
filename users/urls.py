from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from booking.views import my_bookings

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/bookings/', my_bookings, name='my_bookings'),  # ✅ Добавлено
    path('ajax/logout/', views.ajax_logout, name='ajax_logout'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('ajax/register/', views.ajax_register, name='ajax_register'),
    path('ajax/login/', views.ajax_login, name='ajax_login'),
]