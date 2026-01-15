from django.urls import path
from . import views

urlpatterns = [
    path('', views.booking_page, name='booking'),
    path('available-slots/', views.get_available_slots, name='available_slots'),
    path('create/', views.create_booking, name='create_booking'),
    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('confirm/<int:booking_id>/', views.confirm_booking, name='confirm_booking'),
    path('booking-info/<int:booking_id>/', views.get_booking_info, name='booking_info'),

    # Система поиска партнёров
    path('find-partners/', views.find_partners, name='find_partners'),
    path('join/<int:booking_id>/', views.join_booking, name='join_booking'),
    path('invite/<int:booking_id>/', views.send_invitation, name='send_invitation'),
    path('my-invitations/', views.my_invitations, name='my_invitations'),
]