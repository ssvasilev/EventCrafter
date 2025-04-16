import locale

from datetime import datetime
from zoneinfo import ZoneInfo  # Используем ZoneInfo для работы с часовыми поясами


# Устанавливаем локаль для корректного отображения дней недели
locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')  # Для Linux


def time_until_event(event_date: str, event_time: str, tz: ZoneInfo) -> str:
    """
    Вычисляет оставшееся время до мероприятия с учетом часового пояса.
    :param event_date: Дата мероприятия в формате "дд.мм.гггг".
    :param event_time: Время мероприятия в формате "чч:мм".
    :param tz: Часовой пояс (ZoneInfo).
    :return: Строка с оставшимся временем в формате "X дней, Y часов, Z минут".
    """
    # Преобразуем дату и время мероприятия в объект datetime
    event_datetime = datetime.strptime(f"{event_date} {event_time}", "%d.%m.%Y %H:%M")
    event_datetime = event_datetime.replace(tzinfo=tz)  # Устанавливаем часовой пояс

    # Получаем текущее время с учетом часового пояса
    now = datetime.now(tz)

    # Если мероприятие уже прошло, возвращаем соответствующее сообщение
    if event_datetime <= now:
        return "Мероприятие уже прошло."

    # Вычисляем разницу между текущим временем и временем мероприятия
    delta = event_datetime - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    # Формируем строку с оставшимся временем
    result = []
    if days > 0:
        result.append(f"{days} дней")
    if hours > 0:
        result.append(f"{hours} часов")
    if minutes > 0:
        result.append(f"{minutes} минут")

    return ", ".join(result) if result else "Менее минуты"


def format_users_list(users: list, empty_text: str) -> str:
    """Форматирует список пользователей без использования username из БД"""
    if not users:
        return empty_text

    return "\n".join(
        f"{i + 1}. {user['user_name']}"  # Используем уже отформатированное имя из БД
        for i, user in enumerate(users))