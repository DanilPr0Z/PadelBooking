from django.urls import path
from . import views

urlpatterns = [
    # Традиционные маршруты
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('rating/', views.rating_detail, name='rating_detail'),
    path('ajax/rating-info/', views.get_rating_info, name='ajax_rating_info'),
    path('ajax/update-rating/<int:user_id>/', views.update_player_rating, name='ajax_update_rating'),

    # AJAX endpoints
    path('ajax/logout/', views.ajax_logout, name='ajax_logout'),
    path('ajax/register/', views.ajax_register, name='ajax_register'),
    path('ajax/login/', views.ajax_login, name='ajax_login'),
    path('ajax/update-email/', views.update_email, name='ajax_update_email'),
    path('ajax/verify-phone/', views.verify_phone, name='ajax_verify_phone'),
    path('ajax/resend-verification-code/', views.resend_verification_code, name='ajax_resend_verification_code'),
    path('ajax/upload-avatar/', views.upload_avatar, name='ajax_upload_avatar'),
    path('ajax/delete-avatar/', views.delete_avatar, name='ajax_delete_avatar'),
    path('ajax/update-profile/', views.update_profile, name='ajax_update_profile'),
]