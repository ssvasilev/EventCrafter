import os

import pytz
from logger.logger import logger

# Получаем часовой пояс из переменной окружения
TIMEZONE = os.getenv('TIMEZONE', 'UTC')  # По умолчанию используется UTC

# Устанавливаем часовой пояс
try:
    tz = pytz.timezone(TIMEZONE)
except pytz.UnknownTimeZoneError:
    logger.error(f"Неизвестный часовой пояс: {TIMEZONE}. Используется UTC.")
    tz = pytz.UTC

# Путь к базе данных
DB_PATH = "../data/events.db"