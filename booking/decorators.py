"""
Декораторы для rate limiting и защиты API endpoints
"""
from functools import wraps
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def api_ratelimit(key='ip', rate='30/m', method='ALL', block=True):
    """
    Декоратор для rate limiting API endpoints

    Args:
        key: Ключ для группировки (ip, user, header:x-real-ip)
        rate: Лимит (формат: <count>/<period>, например '10/m', '100/h', '1000/d')
        method: HTTP методы для ограничения (ALL, GET, POST)
        block: Блокировать при превышении (True) или только логировать (False)

    Периоды:
        s - секунда
        m - минута
        h - час
        d - день
    """
    def decorator(func):
        @wraps(func)
        @ratelimit(key=key, rate=rate, method=method, block=block)
        def wrapper(request, *args, **kwargs):
            # Проверяем, был ли запрос заблокирован
            was_limited = getattr(request, 'limited', False)

            if was_limited:
                logger.warning(
                    f"Rate limit exceeded for {func.__name__}: "
                    f"key={key}, rate={rate}, "
                    f"ip={request.META.get('REMOTE_ADDR')}, "
                    f"user={request.user if request.user.is_authenticated else 'anonymous'}"
                )

                return JsonResponse({
                    'success': False,
                    'error': 'rate_limit_exceeded',
                    'message': 'Слишком много запросов. Пожалуйста, подождите немного.'
                }, status=429)

            return func(request, *args, **kwargs)

        return wrapper
    return decorator


def auth_ratelimit(rate='5/5m'):
    """
    Строгий rate limiting для endpoints авторизации
    Защита от brute force атак

    Default: 5 попыток за 5 минут
    """
    return api_ratelimit(key='ip', rate=rate, method='POST', block=True)


def api_data_ratelimit(rate='60/m'):
    """
    Умеренный rate limiting для endpoints получения данных

    Default: 60 запросов в минуту
    """
    return api_ratelimit(key='user_or_ip', rate=rate, method='GET', block=True)


def api_write_ratelimit(rate='10/m'):
    """
    Средний rate limiting для endpoints записи данных

    Default: 10 запросов в минуту
    """
    return api_ratelimit(key='user', rate=rate, method='POST', block=True)


def user_specific_ratelimit(rate='20/h'):
    """
    Rate limiting для действий конкретного пользователя

    Default: 20 действий в час
    """
    return api_ratelimit(key='user', rate=rate, method='ALL', block=True)
