"""
Константы для приложения booking
"""
from datetime import time as dt_time

# Рабочие часы кортов
WORKING_HOURS_START = 8  # 08:00
WORKING_HOURS_END = 22  # 22:00

# Время для работы с кортами (time объекты)
WORKING_HOURS_START_TIME = dt_time(8, 0)  # 08:00
WORKING_HOURS_END_TIME = dt_time(22, 0)  # 22:00

# Ограничения на бронирование
MIN_BOOKING_DURATION_HOURS = 1  # Минимальная продолжительность бронирования (в часах)
MAX_BOOKING_DURATION_HOURS = 3  # Максимальная продолжительность бронирования (в часах)

# Подтверждение бронирования
MIN_CONFIRMATION_HOURS = 24  # За сколько часов до начала можно подтвердить бронирование
MIN_CANCEL_HOURS = 1  # Минимальное количество часов до начала, когда можно отменить бронирование

# Конвертация времени
SECONDS_PER_HOUR = 3600  # Секунд в часе






