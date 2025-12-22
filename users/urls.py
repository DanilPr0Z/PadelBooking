from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from booking.views import my_bookings

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/bookings/', my_bookings, name='my_bookings'),

    # AJAX endpoints
    path('ajax/logout/', views.ajax_logout, name='ajax_logout'),
    path('ajax/register/', views.ajax_register, name='ajax_register'),
    path('ajax/login/', views.ajax_login, name='ajax_login'),
    path('ajax/update-email/', views.update_email, name='ajax_update_email'),
    path('ajax/verify-phone/', views.verify_phone, name='ajax_verify_phone'),
    path('ajax/resend-verification-code/', views.resend_verification_code, name='ajax_resend_verification_code'),

    # Аватарка
    path('ajax/upload-avatar/', views.upload_avatar, name='ajax_upload_avatar'),
    path('ajax/delete-avatar/', views.delete_avatar, name='ajax_delete_avatar'),
    path('ajax/update-profile/', views.update_profile, name='ajax_update_profile'),
]