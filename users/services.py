"""
Сервисы для работы с уведомлениями
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from .models import Notification, User
from booking.models import Booking
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    # Шаблоны email
    EMAIL_TEMPLATES = {
        'registration': {
            'subject': 'Добро пожаловать в Paddle Booking!',
            'template': 'emails/registration.html',
        },
        'phone_verification': {
            'subject': 'Код подтверждения телефона',
            'template': 'emails/phone_verification.html',
        },
        'booking_created': {
            'subject': 'Бронирование создано',
            'template': 'emails/booking_created.html',
        },
        'booking_confirmed': {
            'subject': 'Бронирование подтверждено',
            'template': 'emails/booking_confirmed.html',
        },
        'booking_cancelled': {
            'subject': 'Бронирование отменено',
            'template': 'emails/booking_cancelled.html',
        },
        'booking_reminder_24h': {
            'subject': 'Напоминание: бронирование через 24 часа',
            'template': 'emails/booking_reminder_24h.html',
        },
        'booking_reminder_1h': {
            'subject': 'Напоминание: бронирование через 1 час',
            'template': 'emails/booking_reminder_1h.html',
        },
        'payment_success': {
            'subject': 'Оплата прошла успешно',
            'template': 'emails/payment_success.html',
        },
        'payment_failed': {
            'subject': 'Ошибка оплаты',
            'template': 'emails/payment_failed.html',
        },
        'payment_pending': {
            'subject': 'Ожидает оплаты',
            'template': 'emails/payment_pending.html',
        },
        'rating_updated': {
            'subject': 'Ваш рейтинг обновлен',
            'template': 'emails/rating_updated.html',
        },
        'email_verification': {
            'subject': 'Подтверждение вашего Email на Paddle Booking',
            'template': 'emails/email_verification.html',
        },
        'booking_invitation': {
            'subject': 'Приглашение в бронирование',
            'template': 'emails/booking_invitation.html',
        },
        'invitation_accepted': {
            'subject': 'Приглашение принято',
            'template': 'emails/invitation_accepted.html',
        },
        'invitation_declined': {
            'subject': 'Приглашение отклонено',
            'template': 'emails/invitation_declined.html',
        },
        'partner_joined': {
            'subject': 'Новый партнёр присоединился',
            'template': 'emails/partner_joined.html',
        },
    }
    
    @staticmethod
    def create_notification(user, notification_type, title, message, metadata=None):
        """
        Создать уведомление в базе данных
        """
        notification = Notification.objects.create(
            user=user,
            type=notification_type,
            title=title,
            message=message,
            metadata=metadata or {}
        )
        return notification
    
    @staticmethod
    def send_email_notification(user, notification_type, context=None):
        """
        Отправить email уведомление
        """
        if not user.email:
            logger.warning(f"User {user.username} has no email, cannot send notification")
            return False
        
        template_info = NotificationService.EMAIL_TEMPLATES.get(notification_type)
        if not template_info:
            logger.error(f"Email template not found for type: {notification_type}")
            return False
        
        try:
            # Подготавливаем контекст
            context = context or {}
            context.update({
                'user': user,
                'site_name': getattr(settings, 'SITE_NAME', 'Paddle Booking'),
                'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
            })
            
            # Рендерим HTML шаблон
            html_message = render_to_string(template_info['template'], context)
            
            # Отправляем email
            send_mail(
                subject=template_info['subject'],
                message='',  # Текстовая версия (опционально)
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@paddlebooking.com'),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email sent to {user.email} for notification type: {notification_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {user.email}: {e}", exc_info=True)
            return False
    
    @staticmethod
    def send_sms_notification(user, message):
        """
        Отправить SMS уведомление (каркас для будущей реализации)
        TODO: Интеграция с SMS сервисом (SMS.ru, Twilio и т.д.)
        """
        # TODO: Реализация отправки SMS
        # Пример:
        # if hasattr(user, 'profile') and user.profile.phone_verified:
        #     sms_client.send(user.profile.phone, message)
        #     return True
        return False
    
    @staticmethod
    def notify_booking_created(booking):
        """Уведомить о создании бронирования"""
        notification = NotificationService.create_notification(
            user=booking.user,
            notification_type='booking_created',
            title='Бронирование создано',
            message=f'Ваше бронирование корта {booking.court.name} на {booking.date} создано.',
            metadata={'booking_id': booking.id}
        )
        
        # Отправляем email
        NotificationService.send_email_notification(
            booking.user,
            'booking_created',
            {'booking': booking}
        )
        
        # Отмечаем, что email отправлен
        notification.mark_email_sent()
        
        return notification
    
    @staticmethod
    def notify_booking_confirmed(booking):
        """Уведомить о подтверждении бронирования"""
        notification = NotificationService.create_notification(
            user=booking.user,
            notification_type='booking_confirmed',
            title='Бронирование подтверждено',
            message=f'Ваше бронирование корта {booking.court.name} на {booking.date} подтверждено.',
            metadata={'booking_id': booking.id}
        )
        
        NotificationService.send_email_notification(
            booking.user,
            'booking_confirmed',
            {'booking': booking}
        )
        
        notification.mark_email_sent()
        return notification
    
    @staticmethod
    def notify_booking_cancelled(booking):
        """Уведомить об отмене бронирования"""
        notification = NotificationService.create_notification(
            user=booking.user,
            notification_type='booking_cancelled',
            title='Бронирование отменено',
            message=f'Ваше бронирование корта {booking.court.name} на {booking.date} отменено.',
            metadata={'booking_id': booking.id}
        )
        
        NotificationService.send_email_notification(
            booking.user,
            'booking_cancelled',
            {'booking': booking}
        )
        
        notification.mark_email_sent()
        return notification
    
    @staticmethod
    def notify_payment_success(payment):
        """Уведомить об успешной оплате"""
        notification = NotificationService.create_notification(
            user=payment.booking.user,
            notification_type='payment_success',
            title='Оплата прошла успешно',
            message=f'Ваш платеж на сумму {payment.amount} руб. успешно обработан.',
            metadata={'payment_id': payment.id, 'booking_id': payment.booking.id}
        )
        
        NotificationService.send_email_notification(
            payment.booking.user,
            'payment_success',
            {'payment': payment, 'booking': payment.booking}
        )
        
        notification.mark_email_sent()
        return notification
    
    @staticmethod
    def notify_payment_failed(payment):
        """Уведомить об ошибке оплаты"""
        notification = NotificationService.create_notification(
            user=payment.booking.user,
            notification_type='payment_failed',
            title='Ошибка оплаты',
            message=f'Произошла ошибка при обработке платежа на сумму {payment.amount} руб.',
            metadata={'payment_id': payment.id, 'booking_id': payment.booking.id}
        )
        
        NotificationService.send_email_notification(
            payment.booking.user,
            'payment_failed',
            {'payment': payment, 'booking': payment.booking}
        )
        
        notification.mark_email_sent()
        return notification
    
    @staticmethod
    def notify_payment_pending(payment):
        """Уведомить об ожидании оплаты"""
        notification = NotificationService.create_notification(
            user=payment.booking.user,
            notification_type='payment_pending',
            title='Ожидает оплаты',
            message=f'Ваше бронирование ожидает оплаты на сумму {payment.amount} руб.',
            metadata={'payment_id': payment.id, 'booking_id': payment.booking.id}
        )
        
        NotificationService.send_email_notification(
            payment.booking.user,
            'payment_pending',
            {'payment': payment, 'booking': payment.booking}
        )
        
        notification.mark_email_sent()
        return notification
    
    @staticmethod
    def notify_email_verification(user, verification_code):
        """Уведомить о необходимости подтверждения email"""
        # Определяем email для отправки (pending или текущий)
        email_to_send = None
        if hasattr(user, 'profile') and user.profile.email_pending:
            email_to_send = user.profile.email_pending
        elif user.email:
            email_to_send = user.email
        
        if not email_to_send:
            logger.warning(f"User {user.username} has no email to send verification code")
            return False
        
        try:
            # Рендерим HTML шаблон
            context = {
                'user': user,
                'code': verification_code,
                'site_name': getattr(settings, 'SITE_NAME', 'Paddle Booking'),
                'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
            }
            
            html_message = render_to_string('emails/email_verification.html', context)
            
            # Отправляем email
            send_mail(
                subject='Подтверждение вашего Email на Paddle Booking',
                message='',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@paddlebooking.com'),
                recipient_list=[email_to_send],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email verification code sent to {email_to_send} for user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email verification code to {email_to_send}: {e}", exc_info=True)
            return False

    # ========== УВЕДОМЛЕНИЯ О ПРИГЛАШЕНИЯХ И ПАРТНЁРАХ ==========

    @staticmethod
    def send_booking_invitation_notification(invitation):
        """Уведомить пользователя о приглашении в бронирование"""
        if not invitation.invitee:
            return False

        # Создаём уведомление в БД
        notification = NotificationService.create_notification(
            user=invitation.invitee,
            notification_type='booking_invitation',
            title='Приглашение в бронирование',
            message=f'{invitation.inviter.first_name} {invitation.inviter.last_name} приглашает вас присоединиться к бронированию корта {invitation.booking.court.name} на {invitation.booking.date.strftime("%d.%m.%Y")} в {invitation.booking.start_time.strftime("%H:%M")}',
            metadata={
                'invitation_id': invitation.id,
                'booking_id': invitation.booking.id,
                'inviter_id': invitation.inviter.id
            }
        )

        # Отправляем email
        context = {
            'invitation': invitation,
            'booking': invitation.booking,
            'inviter': invitation.inviter,
        }

        NotificationService.send_email_notification(
            user=invitation.invitee,
            notification_type='booking_invitation',
            context=context
        )

        # TODO: Отправить SMS
        return True

    @staticmethod
    def send_invitation_accepted_notification(invitation):
        """Уведомить отправителя о принятии приглашения"""
        # Создаём уведомление в БД
        notification = NotificationService.create_notification(
            user=invitation.inviter,
            notification_type='invitation_accepted',
            title='Приглашение принято',
            message=f'{invitation.invitee.first_name} {invitation.invitee.last_name} принял(а) ваше приглашение на {invitation.booking.date.strftime("%d.%m.%Y")} в {invitation.booking.start_time.strftime("%H:%M")}',
            metadata={
                'invitation_id': invitation.id,
                'booking_id': invitation.booking.id,
                'invitee_id': invitation.invitee.id
            }
        )

        return True

    @staticmethod
    def send_invitation_declined_notification(invitation):
        """Уведомить отправителя об отклонении приглашения"""
        # Создаём уведомление в БД
        notification = NotificationService.create_notification(
            user=invitation.inviter,
            notification_type='invitation_declined',
            title='Приглашение отклонено',
            message=f'{invitation.invitee.first_name} {invitation.invitee.last_name} отклонил(а) ваше приглашение на {invitation.booking.date.strftime("%d.%m.%Y")} в {invitation.booking.start_time.strftime("%H:%M")}',
            metadata={
                'invitation_id': invitation.id,
                'booking_id': invitation.booking.id,
                'invitee_id': invitation.invitee.id
            }
        )

        return True

    @staticmethod
    def send_partner_joined_notification(booking, partner):
        """Уведомить создателя о присоединении партнёра"""
        # Создаём уведомление в БД
        notification = NotificationService.create_notification(
            user=booking.user,
            notification_type='partner_joined',
            title='Новый партнёр присоединился',
            message=f'{partner.first_name} {partner.last_name} присоединился к вашему бронированию на {booking.date.strftime("%d.%m.%Y")} в {booking.start_time.strftime("%H:%M")}. Стоимость на человека: {booking.price_per_person} руб.',
            metadata={
                'booking_id': booking.id,
                'partner_id': partner.id,
                'price_per_person': float(booking.price_per_person)
            }
        )

        return True

