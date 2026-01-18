from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    UserProfile, PlayerRating, CoachProfile,
    TrainingSession, Notification, PlayerCoachRelationship
)


# === USER PROFILE INLINE ===

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль пользователя'
    fields = ('phone', 'phone_verified', 'birth_date', 'avatar')


# === CUSTOM USER ADMIN ===

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'phone_number', 'date_joined', 'is_staff')

    def phone_number(self, obj):
        return obj.profile.phone if hasattr(obj, 'profile') else '-'

    phone_number.short_description = 'Телефон'


# Перерегистрируем User с кастомным админом
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# === USER PROFILE ADMIN ===

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'phone_verified', 'created_at')
    list_filter = ('phone_verified', 'created_at')
    search_fields = ('user__username', 'phone')


# === PLAYER RATING ADMIN ===

@admin.register(PlayerRating)
class PlayerRatingAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'level_badge', 'numeric_rating',
        'progress_bar', 'updated_by', 'updated_at'
    ]
    list_filter = ['level', 'updated_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    readonly_fields = ['level', 'updated_at']

    fieldsets = (
        ('Рейтинг', {
            'fields': ('user', 'numeric_rating', 'level')
        }),
        ('История', {
            'fields': ('updated_by', 'updated_at', 'coach_comment')
        }),
    )

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        name = obj.user.get_full_name() or obj.user.username
        return format_html('<a href="{}">{}</a>', url, name)
    user_link.short_description = 'Игрок'

    def level_badge(self, obj):
        return format_html(
            '<span style="background: linear-gradient(135deg, #9ef01a, #bff167); '
            'color: #1e3a5f; padding: 5px 15px; border-radius: 20px; '
            'font-weight: 700; font-size: 14px;">{}</span>',
            obj.level
        )
    level_badge.short_description = 'Уровень'

    def progress_bar(self, obj):
        progress = obj.get_progress_percentage()
        return format_html(
            '<div style="width: 100px; height: 10px; background: #e5e7eb; '
            'border-radius: 5px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background: #9ef01a;"></div>'
            '</div>',
            progress
        )
    progress_bar.short_description = 'Прогресс'

    def save_model(self, request, obj, form, change):
        """При сохранении обновляем updated_by"""
        if change:
            old_obj = PlayerRating.objects.get(pk=obj.pk)
            if old_obj.numeric_rating != obj.numeric_rating:
                # Добавляем в историю если меняется рейтинг
                obj.add_to_history(
                    old_rating=old_obj.numeric_rating,
                    new_rating=obj.numeric_rating,
                    updated_by=request.user,
                    comment='Изменено через админку'
                )

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# === COACH PROFILE ADMIN ===

@admin.register(CoachProfile)
class CoachProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'specialization', 'experience_years',
        'hourly_rate_display', 'coach_rating', 'is_active'
    ]
    list_filter = ['is_active', 'specialization', 'experience_years']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'bio']
    list_editable = ['is_active']

    fieldsets = (
        ('Тренер', {
            'fields': ('user', 'is_active')
        }),
        ('Квалификация', {
            'fields': ('qualifications', 'specialization', 'experience_years', 'bio')
        }),
        ('Финансы', {
            'fields': ('hourly_rate', 'coach_rating')
        }),
        ('Контакты', {
            'fields': ('contact_info',)
        }),
    )

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        name = obj.user.get_full_name() or obj.user.username
        return format_html('<a href="{}">{}</a>', url, name)
    user_link.short_description = 'Тренер'

    def hourly_rate_display(self, obj):
        return f"{obj.hourly_rate} ₽/час"
    hourly_rate_display.short_description = 'Ставка'


# === TRAINING SESSION ADMIN ===

@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'coach_link', 'player_link', 'court',
        'date', 'time_slot', 'status_badge', 'rating_given'
    ]
    list_filter = ['status', 'date', 'rating_given']
    search_fields = [
        'coach__username', 'player__username',
        'court__name', 'notes'
    ]
    date_hierarchy = 'date'

    fieldsets = (
        ('Участники', {
            'fields': ('coach', 'player', 'court')
        }),
        ('Время', {
            'fields': ('date', 'start_time', 'end_time', 'status')
        }),
        ('Заметки', {
            'fields': ('notes', 'player_feedback', 'rating_given')
        }),
    )

    def coach_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.coach.id])
        name = obj.coach.get_full_name() or obj.coach.username
        return format_html('<a href="{}">{}</a>', url, name)
    coach_link.short_description = 'Тренер'

    def player_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.player.id])
        name = obj.player.get_full_name() or obj.player.username
        return format_html('<a href="{}">{}</a>', url, name)
    player_link.short_description = 'Игрок'

    def time_slot(self, obj):
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_slot.short_description = 'Время'

    def status_badge(self, obj):
        colors = {
            'scheduled': '#3b82f6',
            'in_progress': '#fbbf24',
            'completed': '#10b981',
            'cancelled': '#ef4444'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'


# === NOTIFICATION ADMIN ===

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_link', 'type_badge', 'title',
        'channels_sent', 'is_read', 'created_at'
    ]
    list_filter = [
        'type', 'is_read', 'email_sent', 'sms_sent',
        'push_sent', 'created_at'
    ]
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'

    actions = ['mark_as_read']

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        name = obj.user.get_full_name() or obj.user.username
        return format_html('<a href="{}">{}</a>', url, name)
    user_link.short_description = 'Пользователь'

    def type_badge(self, obj):
        return format_html(
            '<span style="background: #3b82f6; color: white; padding: 3px 8px; '
            'border-radius: 10px; font-size: 10px;">{}</span>',
            obj.get_type_display()
        )
    type_badge.short_description = 'Тип'

    def channels_sent(self, obj):
        """Показать какими каналами отправлено"""
        channels = []
        if obj.email_sent:
            channels.append('📧')
        if obj.sms_sent:
            channels.append('💬')
        if obj.push_sent:
            channels.append('🔔')
        return ' '.join(channels) if channels else '-'
    channels_sent.short_description = 'Отправлено'

    def mark_as_read(self, request, queryset):
        """Отметить уведомления как прочитанные"""
        for notification in queryset:
            notification.mark_as_read()
        self.message_user(request, f'Отмечено прочитанными: {queryset.count()}')
    mark_as_read.short_description = 'Отметить прочитанными'


# === PLAYER COACH RELATIONSHIP ADMIN ===

@admin.register(PlayerCoachRelationship)
class PlayerCoachRelationshipAdmin(admin.ModelAdmin):
    list_display = ['player_link', 'coach_link', 'is_active', 'assigned_at']
    list_filter = ['is_active', 'assigned_at']
    search_fields = [
        'player__username', 'player__first_name', 'player__last_name',
        'coach__username', 'coach__first_name', 'coach__last_name'
    ]

    def player_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.player.id])
        name = obj.player.get_full_name() or obj.player.username
        return format_html('<a href="{}">{}</a>', url, name)
    player_link.short_description = 'Игрок'

    def coach_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.coach.id])
        name = obj.coach.get_full_name() or obj.coach.username
        return format_html('<a href="{}">{}</a>', url, name)
    coach_link.short_description = 'Тренер'