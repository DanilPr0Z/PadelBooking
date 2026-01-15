"""
Сервисы для работы с бронированиями, платежами и историей
"""
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Booking, Payment, BookingHistory
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    """Сервис для работы с платежами"""
    
    @staticmethod
    def create_payment(booking, payment_method='online'):
        """
        Создать платеж для бронирования
        Возвращает объект Payment
        """
        amount = booking.total_price
        
        payment = Payment.objects.create(
            booking=booking,
            amount=amount,
            payment_method=payment_method,
            status='pending'
        )
        
        # Создаем запись в истории
        BookingHistoryService.create_history_entry(
            booking=booking,
            action='payment_pending',
            user=booking.user,
            changes={'amount': str(amount), 'payment_method': payment_method}
        )
        
        logger.info(f"Payment created for booking {booking.id}: {amount} руб.")
        return payment
    
    @staticmethod
    def process_payment(payment, transaction_id=None, payment_intent_id=None):
        """
        Обработать платеж (заглушка для будущей интеграции)
        В реальной интеграции здесь будет вызов API платежной системы
        """
        # TODO: Интеграция с платежной системой
        # Пример:
        # if payment.payment_method == 'online':
        #     result = stripe_api.create_payment_intent(amount, ...)
        #     payment.payment_intent_id = result.id
        #     payment.save()
        
        # Пока просто возвращаем объект платежа
        return payment
    
    @staticmethod
    def confirm_payment(payment, transaction_id=None):
        """
        Подтвердить платеж
        В реальной интеграции здесь будет проверка статуса в платежной системе
        """
        payment.mark_as_paid(transaction_id=transaction_id)
        
        # Создаем запись в истории
        BookingHistoryService.create_history_entry(
            booking=payment.booking,
            action='payment_paid',
            user=payment.booking.user,
            changes={'amount': str(payment.amount), 'transaction_id': transaction_id or ''}
        )
        
        logger.info(f"Payment {payment.id} confirmed for booking {payment.booking.id}")
        return payment
    
    @staticmethod
    def refund_payment(payment):
        """
        Вернуть платеж (заглушка для будущей интеграции)
        """
        payment.mark_as_refunded()
        
        # Создаем запись в истории
        BookingHistoryService.create_history_entry(
            booking=payment.booking,
            action='payment_refunded',
            user=payment.booking.user,
            changes={'amount': str(payment.amount)}
        )
        
        logger.info(f"Payment {payment.id} refunded for booking {payment.booking.id}")
        return payment


class BookingHistoryService:
    """Сервис для работы с историей бронирований"""
    
    @staticmethod
    def create_history_entry(booking, action, user=None, changes=None, comment=''):
        """
        Создать запись в истории бронирования
        """
        history_entry = BookingHistory.objects.create(
            booking=booking,
            action=action,
            user=user,
            changes=changes or {},
            comment=comment
        )
        
        logger.debug(f"History entry created: {booking.id} - {action}")
        return history_entry
    
    @staticmethod
    def log_booking_created(booking, user):
        """Логировать создание бронирования"""
        return BookingHistoryService.create_history_entry(
            booking=booking,
            action='created',
            user=user,
            changes={
                'court': booking.court.name,
                'date': booking.date.isoformat(),
                'start_time': booking.start_time.isoformat(),
                'end_time': booking.end_time.isoformat(),
                'price': str(booking.total_price)
            }
        )
    
    @staticmethod
    def log_booking_confirmed(booking, user):
        """Логировать подтверждение бронирования"""
        return BookingHistoryService.create_history_entry(
            booking=booking,
            action='confirmed',
            user=user,
            changes={'confirmed_at': timezone.now().isoformat()}
        )
    
    @staticmethod
    def log_booking_cancelled(booking, user, reason=''):
        """Логировать отмену бронирования"""
        return BookingHistoryService.create_history_entry(
            booking=booking,
            action='cancelled',
            user=user,
            comment=reason
        )




