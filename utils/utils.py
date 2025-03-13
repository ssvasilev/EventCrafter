from datetime import datetime, timedelta, date, time
import pytz
import locale

from config import tz

# Устанавливаем локаль для корректного отображения дней недели
locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')  # Для Linux

# Получаем часовой пояс из переменной окружения (например, 'Europe/Moscow')
TIMEZONE = pytz.timezone('Europe/Moscow')

def time_until_event(event_date: str, event_time: str) -> str:
    """
    Вычисляет оставшееся время до мероприятия с учетом часового пояса.
    :param event_date: Дата мероприятия в формате "дд-мм-гггг".
    :param event_time: Время мероприятия в формате "чч:мм".
    :return: Строка с оставшимся временем в формате "X дней, Y часов, Z минут".
    """
    # Преобразуем дату и время мероприятия в объект datetime
    event_datetime = datetime.strptime(f"{date.strftime('%d-%m-%Y')} {time.strftime('%H:%M')}", "%d-%m-%Y %H:%M")
    event_datetime = event_datetime.replace(tzinfo=tz)  # Устанавливаем часовой пояс

    # Получаем текущее время с учетом часового пояса
    now = datetime.now(TIMEZONE)

    # Если мероприятие уже прошло, возвращаем соответствующее сообщение
    if event_datetime <= now:
        return "Мероприятие уже прошло."

    # Вычисляем разницу между текущим временем и временем мероприятия
    delta = event_datetime - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return f"{days} дней, {hours} часов, {minutes} минут"


def format_date_with_weekday(date_str: str) -> str:
    """
    Форматирует дату в формате "дд-мм-гггг" в строку с днем недели.
    :param date_str: Дата в формате "дд-мм-гггг".
    :return: Строка в формате "дд.мм.гггг (ДеньНедели)".
    """
    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
    return date_obj.strftime("%d.%m.%Y (%A)")  # %A — полное название дня недели


def format_event_message(event: dict) -> str:
    """
    Форматирует информацию о мероприятии в строку для отправки в чат.
    :param event: Словарь с данными о мероприятии.
    :return: Отформатированная строка.
    """
    time_until = time_until_event(event['date'], event['time'])
    limit_text = "∞ (бесконечный)" if event["participant_limit"] is None else str(event["participant_limit"])

    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {event['date']}\n"
        f"🕒 <i>Время: </i> {event['time']}\n"
        f"⏳ <i>До мероприятия: </i> {time_until}\n"
        f"👥 <i>Лимит участников: </i> {limit_text}\n\n"
        f"✅ <i>Участники: </i>\n{event.get('participants', 'Ещё никто не участвует.')}\n\n"
        f"⏳ <i>Резерв: </i>\n{event.get('reserve', 'Резерв пуст.')}\n\n"
        f"❌ <i>Отказавшиеся: </i>\n{event.get('declined', 'Отказавшихся нет.')}"
    )

    return message_text


def validate_date(date_str: str) -> bool:
    """
    Проверяет, является ли строка корректной датой в формате "дд.мм.гггг".
    :param date_str: Строка с датой.
    :return: True, если дата корректна, иначе False.
    """
    try:
        datetime.strptime(date_str, "%d.%m.%Y")
        return True
    except ValueError:
        return False


def validate_time(time_str: str) -> bool:
    """
    Проверяет, является ли строка корректным временем в формате "чч:мм".
    :param time_str: Строка с временем.
    :return: True, если время корректно, иначе False.
    """
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False