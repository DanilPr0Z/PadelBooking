from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль пользователя'
    fields = ('phone', 'phone_verified', 'birth_date', 'avatar')


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'phone_number', 'date_joined', 'is_staff')

    def phone_number(self, obj):
        return obj.profile.phone if hasattr(obj, 'profile') else '-'

    phone_number.short_description = 'Телефон'


# Перерегистрируем User с кастомным админом
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'phone_verified', 'created_at')
    list_filter = ('phone_verified', 'created_at')
    search_fields = ('user__username', 'phone')