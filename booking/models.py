from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models.signals import pre_save
from django.dispatch import receiver


class Court(models.Model):
    name = models.CharField(max_length=100)
    today_bookings_count = models.IntegerField(default=0, verbose_name='Бронирований сегодня')
    description = models.TextField()
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_available']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_created', verbose_name='Создатель')
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

    # Новые поля для партнёров и тренера
    partners = models.ManyToManyField(
        User,
        related_name='bookings_as_partner',
        blank=True,
        verbose_name='Партнёры'
    )
    coach = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings_as_coach',
        verbose_name='Тренер',
        limit_choices_to={'groups__name': 'Тренеры'}
    )

    # Функция "Найти партнёра"
    looking_for_partner = models.BooleanField(
        default=False,
        verbose_name='Ищет партнёра'
    )
    max_players = models.IntegerField(
        default=4,
        verbose_name='Макс. игроков',
        help_text='Максимальное количество игроков (включая создателя)'
    )
    required_rating_level = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='Требуемый уровень игры',
        help_text='Буквенный рейтинг для поиска партнёров (например: C+, B-)'
    )

    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['court', 'date', 'status']),
            models.Index(fields=['user']),
            models.Index(fields=['date', 'start_time']),
            models.Index(fields=['status']),
            models.Index(fields=['looking_for_partner', 'date']),
        ]

    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        display_name = full_name if full_name else self.user.username
        return f"{display_name} - {self.court.name} - {self.date}"

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
    def price_per_person(self):
        """Рассчитывает стоимость на одного человека"""
        total = self.total_price
        # Количество участников = создатель + партнёры (без тренера)
        participants_count = 1 + self.partners.count()
        if participants_count > 1:
            return round(total / participants_count, 2)
        return total

    @property
    def available_slots(self):
        """Количество свободных мест для партнёров"""
        current_players = 1 + self.partners.count()  # создатель + партнёры
        return max(0, self.max_players - current_players)

    @property
    def is_full(self):
        """Проверка, заполнено ли бронирование"""
        return self.available_slots == 0

    def get_all_participants(self):
        """Возвращает список всех участников (создатель + партнёры)"""
        participants = [self.user]
        participants.extend(list(self.partners.all()))
        return participants

    def can_join(self, user):
        """Проверка, может ли пользователь присоединиться к бронированию"""
        # Нельзя присоединиться если:
        # 1. Бронирование не ищет партнёров
        if not self.looking_for_partner:
            return False, "Бронирование не ищет партнёров"

        # 2. Бронирование уже заполнено
        if self.is_full:
            return False, "Нет свободных мест"

        # 3. Пользователь уже является участником
        if user == self.user or user in self.partners.all():
            return False, "Вы уже являетесь участником"

        # 4. Бронирование отменено
        if self.status == 'cancelled':
            return False, "Бронирование отменено"

        # 5. Проверка рейтинга (если указан требуемый уровень)
        if self.required_rating_level:
            try:
                user_rating = user.rating.level
                if user_rating != self.required_rating_level:
                    return False, f"Требуемый уровень: {self.required_rating_level}, ваш: {user_rating}"
            except:
                return False, "У вас нет рейтинга"

        return True, "OK"

    def add_partner(self, user):
        """Добавить партнёра в бронирование"""
        can_join, message = self.can_join(user)
        if not can_join:
            return False, message

        self.partners.add(user)
        return True, "Вы успешно присоединились к бронированию"

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


class Payment(models.Model):
    """Модель платежа за бронирование"""

    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('paid', 'Оплачено'),
        ('refunded', 'Возвращено'),
        ('failed', 'Ошибка оплаты'),
        ('cancelled', 'Отменено'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('card', 'Банковская карта'),
        ('bank_transfer', 'Банковский перевод'),
        ('cash', 'Наличные'),
        ('online', 'Онлайн оплата'),
    ]

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='payment',
        verbose_name='Бронирование'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Статус'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='online',
        verbose_name='Способ оплаты'
    )
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        verbose_name='ID транзакции'
    )
    payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='ID платежного намерения',
        help_text='Используется для интеграции с платежными системами'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    paid_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата оплаты'
    )
    refunded_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дата возврата'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные данные',
        help_text='Для хранения данных платежной системы'
    )

    class Meta:
        verbose_name = 'Платеж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Платеж #{self.id} - {self.booking} - {self.amount}₽ ({self.get_status_display()})"

    def mark_as_paid(self):
        """Отметить платеж как оплаченный"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()

    def mark_as_failed(self):
        """Отметить платеж как ошибочный"""
        self.status = 'failed'
        self.save()

    def refund(self):
        """Вернуть платеж"""
        if self.status == 'paid':
            self.status = 'refunded'
            self.refunded_at = timezone.now()
            self.save()
            return True
        return False


class BookingHistory(models.Model):
    """История изменений бронирования"""

    ACTION_CHOICES = [
        ('created', 'Создано'),
        ('confirmed', 'Подтверждено'),
        ('cancelled', 'Отменено'),
        ('payment_pending', 'Ожидает оплаты'),
        ('payment_paid', 'Оплачено'),
        ('payment_refunded', 'Оплата возвращена'),
        ('payment_failed', 'Ошибка оплаты'),
        ('modified', 'Изменено'),
    ]

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Бронирование'
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name='Действие'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Пользователь',
        help_text='Кто выполнил действие'
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Изменения',
        help_text='Данные о том, что изменилось'
    )
    comment = models.TextField(
        blank=True,
        verbose_name='Комментарий'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Время'
    )

    class Meta:
        verbose_name = 'История бронирования'
        verbose_name_plural = 'История бронирований'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['booking', 'timestamp']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.booking} - {self.get_action_display()} - {self.timestamp}"


class BookingInvitation(models.Model):
    """Приглашение в бронирование"""

    STATUS_CHOICES = [
        ('pending', 'Ожидает ответа'),
        ('accepted', 'Принято'),
        ('declined', 'Отклонено'),
        ('cancelled', 'Отменено'),
    ]

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='invitations',
        verbose_name='Бронирование'
    )
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        verbose_name='Отправитель'
    )
    invitee_phone = models.CharField(
        max_length=20,
        verbose_name='Телефон приглашённого',
        help_text='Номер телефона пользователя, которого приглашают'
    )
    invitee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_invitations',
        null=True,
        blank=True,
        verbose_name='Приглашённый пользователь'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name='Статус'
    )
    message = models.TextField(
        blank=True,
        verbose_name='Сообщение',
        help_text='Дополнительное сообщение для приглашённого'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата отправки'
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата ответа'
    )

    class Meta:
        verbose_name = 'Приглашение в бронирование'
        verbose_name_plural = 'Приглашения в бронирования'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invitee', 'status']),
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['invitee_phone']),
        ]
        # Нельзя приглашать одного и того же человека дважды в одно бронирование
        unique_together = [('booking', 'invitee_phone')]

    def __str__(self):
        inviter_name = f"{self.inviter.first_name} {self.inviter.last_name}".strip() or self.inviter.username
        return f"{inviter_name} → {self.invitee_phone} ({self.get_status_display()})"

    def accept(self):
        """Принять приглашение"""
        if self.status != 'pending':
            return False, "Приглашение уже обработано"

        if not self.invitee:
            return False, "Пользователь не найден"

        # Проверяем, можно ли присоединиться
        can_join, message = self.booking.can_join(self.invitee)
        if not can_join:
            return False, message

        # Добавляем пользователя в партнёры
        success, msg = self.booking.add_partner(self.invitee)
        if success:
            self.status = 'accepted'
            self.responded_at = timezone.now()
            self.save()
            return True, "Приглашение принято"
        else:
            return False, msg

    def decline(self):
        """Отклонить приглашение"""
        if self.status != 'pending':
            return False, "Приглашение уже обработано"

        self.status = 'declined'
        self.responded_at = timezone.now()
        self.save()
        return True, "Приглашение отклонено"

    def cancel(self):
        """Отменить приглашение (со стороны отправителя)"""
        if self.status != 'pending':
            return False, "Приглашение уже обработано"

        self.status = 'cancelled'
        self.save()
        return True, "Приглашение отменено"


@receiver(pre_save, sender=BookingInvitation)
def set_invitee_by_phone(sender, instance, **kwargs):
    """Автоматически определяет приглашённого пользователя по номеру телефона"""
    if instance.invitee_phone and not instance.invitee:
        from users.models import UserProfile
        # Нормализуем номер и ищем пользователя
        normalized_phone = UserProfile.objects.normalize_phone(instance.invitee_phone)
        if normalized_phone:
            user = UserProfile.objects.get_user_by_phone(normalized_phone)
            if user:
                instance.invitee = user
                instance.invitee_phone = normalized_phone