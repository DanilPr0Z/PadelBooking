from django.db import models
from django.contrib.auth.models import User


class Court(models.Model):
    name = models.CharField(max_length=100)
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

    def __str__(self):
        return f"{self.user.username} - {self.court.name} - {self.date}"