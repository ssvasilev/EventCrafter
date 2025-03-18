import os
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError

from logger.logger import logger

# Получаем часовой пояс из переменной окружения
TIMEZONE = os.getenv('TIMEZONE', 'UTC')  # По умолчанию используется UTC

# Устанавливаем часовой пояс
try:
    tz = ZoneInfo(TIMEZONE)
except ZoneInfoNotFoundError:
    logger.error(f"Неизвестный часовой пояс: {TIMEZONE}. Используется UTC.")
    tz = ZoneInfo("UTC")

# Путь к базе основных данных
DB_PATH = "../data/events.db"

# Путь к базе данных черновиков
DB_DRAFT_PATH = "../data/draft.db"