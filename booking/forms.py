from django import forms
from .models import Booking, BookingInvitation
from django.contrib.auth.models import User
from users.models import PlayerRating


class BookingForm(forms.ModelForm):
    # Поле для выбора тренера
    coach = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Тренеры'),
        required=False,
        empty_label="Без тренера",
        label='Тренер',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    # Опция "Найти партнёра"
    looking_for_partner = forms.BooleanField(
        required=False,
        label='Найти партнёра',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'lookingForPartner'
        }),
        help_text='Другие игроки с подходящим рейтингом смогут присоединиться к вашему бронированию'
    )

    # Максимальное количество игроков
    max_players = forms.IntegerField(
        initial=4,
        min_value=2,
        max_value=4,
        label='Максимальное количество игроков',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '2',
            'max': '4'
        }),
        help_text='Включая вас (от 2 до 4 игроков)'
    )

    # Требуемый рейтинг для партнёров
    required_rating_level = forms.ChoiceField(
        choices=[('', 'Любой уровень')] + PlayerRating.RATING_LEVELS,
        required=False,
        label='Требуемый уровень партнёров',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='Только игроки с таким же рейтингом смогут присоединиться'
    )

    class Meta:
        model = Booking
        fields = ['court', 'date', 'start_time', 'end_time', 'coach', 'looking_for_partner', 'max_players', 'required_rating_level']
        widgets = {
            'court': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }
        labels = {
            'court': 'Корт',
            'date': 'Дата',
            'start_time': 'Время начала',
            'end_time': 'Время окончания',
        }

    def clean(self):
        cleaned_data = super().clean()
        looking_for_partner = cleaned_data.get('looking_for_partner')
        max_players = cleaned_data.get('max_players')

        # Если ищем партнёра, нужно указать макс. игроков
        if looking_for_partner and max_players < 2:
            self.add_error('max_players', 'При поиске партнёра должно быть минимум 2 игрока')

        return cleaned_data


class InviteFriendForm(forms.ModelForm):
    """Форма для приглашения друга в бронирование"""

    phone = forms.CharField(
        max_length=20,
        label='Номер телефона друга',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67'
        }),
        help_text='Введите номер телефона друга, зарегистрированного в системе'
    )

    class Meta:
        model = BookingInvitation
        fields = ['phone', 'message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительное сообщение (необязательно)'
            })
        }
        labels = {
            'message': 'Сообщение'
        }

    def __init__(self, *args, **kwargs):
        self.booking = kwargs.pop('booking', None)
        self.inviter = kwargs.pop('inviter', None)
        super().__init__(*args, **kwargs)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')

        from users.models import UserProfile

        # Нормализуем номер
        normalized_phone = UserProfile.objects.normalize_phone(phone)
        if not normalized_phone:
            raise forms.ValidationError('Неверный формат номера телефона')

        # Проверяем, что пользователь существует
        user = UserProfile.objects.get_user_by_phone(normalized_phone)
        if not user:
            raise forms.ValidationError('Пользователь с таким номером не найден')

        # Нельзя приглашать самого себя
        if self.inviter and user == self.inviter:
            raise forms.ValidationError('Вы не можете пригласить самого себя')

        # Проверяем, не является ли пользователь уже участником
        if self.booking:
            if user == self.booking.user or user in self.booking.partners.all():
                raise forms.ValidationError('Этот пользователь уже участвует в бронировании')

            # Проверяем, не было ли уже приглашения
            existing_invitation = BookingInvitation.objects.filter(
                booking=self.booking,
                invitee_phone=normalized_phone,
                status='pending'
            ).first()
            if existing_invitation:
                raise forms.ValidationError('Приглашение этому пользователю уже отправлено')

        return normalized_phone

    def save(self, commit=True):
        invitation = super().save(commit=False)
        invitation.booking = self.booking
        invitation.inviter = self.inviter
        invitation.invitee_phone = self.cleaned_data['phone']

        if commit:
            invitation.save()
        return invitation


class JoinBookingForm(forms.Form):
    """Форма для присоединения к бронированию"""
    booking_id = forms.IntegerField(widget=forms.HiddenInput())