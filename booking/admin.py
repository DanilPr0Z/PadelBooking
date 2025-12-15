from django.contrib import admin
from .models import Court, Booking

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_per_hour', 'is_available']
    list_filter = ['is_available']
    search_fields = ['name']

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'court', 'date', 'start_time', 'end_time', 'status']
    list_filter = ['status', 'date']
    search_fields = ['user__username', 'court__name']