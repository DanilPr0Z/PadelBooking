from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Court, Booking, BookingInvitation, Payment, BookingHistory


# === COURT ADMIN ===

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_per_hour', 'is_available', 'today_bookings_count']
    list_filter = ['is_available']
    search_fields = ['name', 'description']
    list_editable = ['is_available', 'price_per_hour']

    def today_bookings_count(self, obj):
        """Количество бронирований на сегодня"""
        today = timezone.now().date()
        count = Booking.objects.filter(
            court=obj,
            date=today,
            status__in=['pending', 'confirmed']
        ).count()
        return count
    today_bookings_count.short_description = 'Броней сегодня'


# === BOOKING ADMIN ===

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_link', 'court', 'date', 'time_slot',
        'status_badge', 'booking_type', 'partners_count',
        'total_price_display', 'payment_status'
    ]
    list_filter = [
        'status', 'booking_type', 'date', 'looking_for_partner',
        ('coach', admin.RelatedOnlyFieldListFilter),
        ('court', admin.RelatedOnlyFieldListFilter),
    ]
    search_fields = [
        'user__username', 'user__first_name', 'user__last_name',
        'court__name', 'partners__username'
    ]
    filter_horizontal = ['partners']
    date_hierarchy = 'date'

    readonly_fields = ['created_at', 'confirmed_at', 'total_price_display']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'court', 'date', 'start_time', 'end_time',
                      'booking_type', 'status', 'confirmed_at', 'created_at')
        }),
        ('Участники', {
            'fields': ('partners', 'coach', 'looking_for_partner',
                      'max_players', 'required_rating_levels')
        }),
        ('Финансы', {
            'fields': ('total_price_display',)
        }),
    )

    actions = ['confirm_bookings', 'cancel_bookings']

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'Пользователь'

    def time_slot(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_slot.short_description = 'Время'

    def status_badge(self, obj):
        colors = {
            'pending': '#fbbf24',
            'confirmed': '#10b981',
            'cancelled': '#ef4444'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def partners_count(self, obj):
        return obj.partners.count()
    partners_count.short_description = 'Партнёров'

    def total_price_display(self, obj):
        return f"{obj.total_price} ₽"
    total_price_display.short_description = 'Стоимость'

    def payment_status(self, obj):
        """Статус платежа"""
        try:
            payment = obj.payment
            colors = {
                'pending': '#fbbf24',
                'paid': '#10b981',
                'refunded': '#6b7280',
                'failed': '#ef4444',
                'cancelled': '#6b7280'
            }
            return format_html(
                '<span style="background: {}; color: white; padding: 3px 8px; '
                'border-radius: 10px; font-size: 10px;">{}</span>',
                colors.get(payment.status, '#6b7280'),
                payment.get_status_display()
            )
        except Payment.DoesNotExist:
            return format_html('<span style="color: #6b7280;">Нет</span>')
    payment_status.short_description = 'Платёж'

    def confirm_bookings(self, request, queryset):
        """Массовое подтверждение бронирований"""
        updated = 0
        for booking in queryset.filter(status='pending'):
            success, message = booking.confirm()
            if success:
                updated += 1
                # Создаем запись в истории
                BookingHistory.objects.create(
                    booking=booking,
                    action='confirmed',
                    user=request.user,
                    comment='Подтверждено через админку'
                )
        self.message_user(request, f'Подтверждено бронирований: {updated}')
    confirm_bookings.short_description = 'Подтвердить выбранные'

    def cancel_bookings(self, request, queryset):
        """Массовая отмена"""
        updated = 0
        for booking in queryset:
            booking.status = 'cancelled'
            booking.save()
            # Создаем запись в истории
            BookingHistory.objects.create(
                booking=booking,
                action='cancelled',
                user=request.user,
                comment='Отменено через админку'
            )
            updated += 1
        self.message_user(request, f'Отменено бронирований: {updated}')
    cancel_bookings.short_description = 'Отменить выбранные'


# === PAYMENT ADMIN ===

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'booking_link', 'amount_display', 'status_badge',
        'payment_method', 'created_at', 'paid_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = [
        'booking__user__username', 'transaction_id',
        'payment_intent_id'
    ]
    readonly_fields = [
        'created_at', 'paid_at', 'refunded_at',
        'transaction_id', 'payment_intent_id'
    ]
    date_hierarchy = 'created_at'

    actions = ['mark_as_paid', 'refund_payments']

    def booking_link(self, obj):
        url = reverse('admin:booking_booking_change', args=[obj.booking.id])
        return format_html('<a href="{}">Бронь #{}</a>', url, obj.booking.id)
    booking_link.short_description = 'Бронирование'

    def amount_display(self, obj):
        return f"{obj.amount} ₽"
    amount_display.short_description = 'Сумма'

    def status_badge(self, obj):
        colors = {
            'pending': '#fbbf24',
            'paid': '#10b981',
            'refunded': '#6b7280',
            'failed': '#ef4444',
            'cancelled': '#6b7280'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 600;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def mark_as_paid(self, request, queryset):
        """Отметить платежи как оплаченные"""
        for payment in queryset.filter(status='pending'):
            payment.mark_as_paid()
            # Создаем запись в истории бронирования
            BookingHistory.objects.create(
                booking=payment.booking,
                action='payment_paid',
                user=request.user,
                comment='Платеж отмечен оплаченным через админку'
            )
        self.message_user(request, f'Платежей отмечено оплаченными: {queryset.count()}')
    mark_as_paid.short_description = 'Отметить как оплаченные'

    def refund_payments(self, request, queryset):
        """Вернуть деньги"""
        refunded = 0
        for payment in queryset.filter(status='paid'):
            if payment.refund():
                # Создаем запись в истории
                BookingHistory.objects.create(
                    booking=payment.booking,
                    action='payment_refunded',
                    user=request.user,
                    comment='Платеж возвращен через админку'
                )
                refunded += 1
        self.message_user(request, f'Возвращено платежей: {refunded}')
    refund_payments.short_description = 'Вернуть деньги'


# === BOOKING HISTORY ADMIN ===

@admin.register(BookingHistory)
class BookingHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking_link', 'action_badge', 'user', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['booking__id', 'user__username', 'comment']
    readonly_fields = ['booking', 'action', 'user', 'changes', 'timestamp', 'comment']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False  # История создается автоматически

    def has_delete_permission(self, request, obj=None):
        return False  # История не удаляется

    def booking_link(self, obj):
        url = reverse('admin:booking_booking_change', args=[obj.booking.id])
        return format_html('<a href="{}">Бронь #{}</a>', url, obj.booking.id)
    booking_link.short_description = 'Бронирование'

    def action_badge(self, obj):
        colors = {
            'created': '#3b82f6',
            'confirmed': '#10b981',
            'cancelled': '#ef4444',
            'modified': '#fbbf24',
            'payment_pending': '#fbbf24',
            'payment_paid': '#10b981',
            'payment_refunded': '#6b7280',
            'payment_failed': '#ef4444'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 10px;">{}</span>',
            colors.get(obj.action, '#6b7280'),
            obj.get_action_display()
        )
    action_badge.short_description = 'Действие'


# === BOOKING INVITATION ADMIN ===

@admin.register(BookingInvitation)
class BookingInvitationAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking', 'inviter', 'invitee_phone', 'invitee', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['inviter__username', 'inviter__first_name', 'inviter__last_name', 'invitee__username', 'invitee__first_name', 'invitee__last_name', 'invitee_phone']

    readonly_fields = ['created_at', 'responded_at']

