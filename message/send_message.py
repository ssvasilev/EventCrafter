from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from database.db_operations import get_event, get_participants, get_reserve, get_declined
from utils.utils import time_until_event
from logger.logger import logger
from utils.pin_message import pin_message

async def send_event_message(event_id: int, chat_id: int, db_path: str, tz: str, message_id: int = None):
    """
    Отправляет или редактирует сообщение с информацией о мероприятии.
    :param event_id: ID мероприятия.
    :param chat_id: ID чата, куда отправляется сообщение.
    :param db_path: Путь к базе данных.
    :param tz: Часовой пояс (строка, например, "Europe/Moscow").
    :param message_id: ID сообщения для редактирования (если None, отправляется новое сообщение).
    :return: ID отправленного или отредактированного сообщения.
    """
    # Получаем данные о мероприятии из базы данных
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return None

    # Получаем участников, резерв и отказавшихся
    participants = get_participants(db_path, event_id)
    reserve = get_reserve(db_path, event_id)
    declined = get_declined(db_path, event_id)

    # Форматируем списки
    participants_text = (
        "\n".join([p["user_name"] for p in participants])
        if participants
        else "Ещё никто не участвует."
    )
    reserve_text = (
        "\n".join([p["user_name"] for p in reserve])
        if reserve
        else "Резерв пуст."
    )
    declined_text = (
        "\n".join([p["user_name"] for p in declined])
        if declined
        else "Отказавшихся нет."
    )

    # Лимит участников
    limit_text = "∞ (бесконечный)" if event["participant_limit"] is None else str(event["participant_limit"])

    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Вычисляем оставшееся время до мероприятия
    time_until = time_until_event(event['date'], event['time'], tz)

    # Форматируем дату с днём недели
    date = datetime.strptime(event["date"], "%d-%m-%Y").date()
    formatted_date = date.strftime("%d.%m.%Y (%A)")  # %A — полное название дня недели

    # Текст сообщения
    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {formatted_date}\n"
        f"🕒 <i>Время: </i> {event['time']}\n"
        f"⏳ <i>До мероприятия: </i> {time_until}\n"
        f"👥 <i>Лимит участников: </i> {limit_text}\n\n"
        f"✅ <i>Участники: </i>\n{participants_text}\n\n"
        f"⏳ <i>Резерв: </i>\n{reserve_text}\n\n"
        f"❌ <i>Отказавшиеся: </i>\n{declined_text}"
    )

    if message_id:
        try:
            # Редактируем существующее сообщение
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            logger.info(f"Сообщение {message_id} отредактировано.")
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Если сообщение не изменилось, просто игнорируем ошибку
                logger.info(f"Сообщение {message_id} не изменилось.")
            else:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                raise e  # Если ошибка другая, пробрасываем её дальше
        return message_id
    else:
        # Отправляем новое сообщение
        try:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            logger.info(f"Новое сообщение отправлено с ID: {message.message_id}")

            # Закрепляем сообщение в чате
            await pin_message(context, chat_id, message.message_id)

            return message.message_id
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            raise e