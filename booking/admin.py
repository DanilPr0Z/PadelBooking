from django.contrib import admin
from .models import Court, Booking, BookingInvitation

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_per_hour', 'is_available']
    list_filter = ['is_available']
    search_fields = ['name']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'court', 'date', 'start_time', 'end_time', 'status', 'looking_for_partner']
    list_filter = ['status', 'date', 'looking_for_partner']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'court__name']
    filter_horizontal = ['partners']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'court', 'date', 'start_time', 'end_time', 'status', 'confirmed_at')
        }),
        ('Партнёры и тренер', {
            'fields': ('partners', 'coach', 'looking_for_partner', 'max_players', 'required_rating_level')
        }),
    )

@admin.register(BookingInvitation)
class BookingInvitationAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking', 'inviter', 'invitee_phone', 'invitee', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['inviter__username', 'inviter__first_name', 'inviter__last_name', 'invitee__username', 'invitee__first_name', 'invitee__last_name', 'invitee_phone']

    readonly_fields = ['created_at', 'responded_at']

