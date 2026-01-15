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

    # Система тренеров
    path('coaches/', views.coaches_list, name='coaches_list'),
    path('coaches/<int:coach_id>/', views.coach_detail, name='coach_detail'),
    path('training-sessions/', views.my_training_sessions, name='training_sessions'),

    # Система уведомлений
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('ajax/notifications/count/', views.get_unread_notifications_count, name='ajax_notifications_count'),
    path('ajax/notifications/mark-read/', views.mark_notification_read, name='ajax_mark_notification_read'),
    path('ajax/notifications/mark-all-read/', views.mark_all_notifications_read, name='ajax_mark_all_notifications_read'),

    # AJAX endpoints
    path('ajax/logout/', views.ajax_logout, name='ajax_logout'),
    path('ajax/register/', views.ajax_register, name='ajax_register'),
    path('ajax/login/', views.ajax_login, name='ajax_login'),
    path('ajax/update-email/', views.update_email, name='ajax_update_email'),
    path('ajax/verify-phone/', views.verify_phone, name='ajax_verify_phone'),
    path('ajax/resend-verification-code/', views.resend_verification_code, name='ajax_resend_verification_code'),
    path('ajax/verify-email/', views.verify_email, name='ajax_verify_email'),
    path('ajax/resend-email-verification-code/', views.resend_email_verification_code, name='ajax_resend_email_verification_code'),
    path('ajax/upload-avatar/', views.upload_avatar, name='ajax_upload_avatar'),
    path('ajax/delete-avatar/', views.delete_avatar, name='ajax_delete_avatar'),
    path('ajax/update-profile/', views.update_profile, name='ajax_update_profile'),
]