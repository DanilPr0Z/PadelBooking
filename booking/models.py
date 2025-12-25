from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta


class Court(models.Model):
    name = models.CharField(max_length=100)
    today_bookings_count = models.IntegerField(default=0, verbose_name='Бронирований сегодня')
    description = models.TextField()
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    court = models.ForeignKey(Court, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'В ожидании'),
        ('confirmed', 'Подтверждено'),
        ('cancelled', 'Отменено'),
    ], default='pending')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.court.name} - {self.date}"

    @property
    def total_price(self):
        """Рассчитывает общую стоимость бронирования"""
        start_dt = datetime.combine(self.date, self.start_time)
        end_dt = datetime.combine(self.date, self.end_time)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # на случай если бронирование через полночь

        duration_hours = (end_dt - start_dt).total_seconds() / 3600
        return round(float(self.court.price_per_hour) * duration_hours, 2)

    @property
    def can_confirm(self):
        """Можно ли подтвердить бронирование (за 24 часа до начала)"""
        from django.utils import timezone

        # Создаем aware datetime для booking_datetime
        booking_datetime = timezone.make_aware(
            datetime.combine(self.date, self.start_time)
        )
        current_time = timezone.now()
        time_diff = booking_datetime - current_time

        # Можно подтвердить если осталось от 0 до 24 часов
        return timedelta(hours=0) < time_diff <= timedelta(hours=24)

    @property
    def hours_until_confirmation(self):
        """Сколько часов осталось до возможности подтверждения"""
        from django.utils import timezone

        booking_datetime = timezone.make_aware(
            datetime.combine(self.date, self.start_time)
        )
        current_time = timezone.now()
        time_diff = booking_datetime - current_time

        # Если уже можно подтверждать
        if time_diff <= timedelta(hours=24):
            return 0

        # Сколько осталось до возможности подтверждения
        hours_until = (time_diff - timedelta(hours=24)).total_seconds() / 3600
        return max(0, int(hours_until))

    @property
    def booking_datetime(self):
        """Полная дата и время начала бронирования"""
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    def confirm(self):
        """Подтвердить бронирование"""
        if self.status == 'pending' and self.can_confirm:
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save()
            return True
        return False