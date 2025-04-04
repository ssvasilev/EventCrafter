from datetime import datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from config import tz
from src.database.db_operations import get_event, get_participants, get_reserve, get_declined
from src.logger.logger import logger
from src.utils.pin_message import pin_message
from src.utils.utils import time_until_event


async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int = None):
    """Отправляет или редактирует сообщение с информацией о мероприятии."""
    db_path = context.bot_data.get("db_path")
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    participants = get_participants(db_path, event_id)
    reserve = get_reserve(db_path, event_id)
    declined = get_declined(db_path, event_id)

    # Форматируем списки
    participants_text = "\n".join([p["user_name"] for p in participants]) if participants else "Ещё никто не участвует."
    reserve_text = "\n".join([p["user_name"] for p in reserve]) if reserve else "Резерв пуст."
    declined_text = "\n".join([p["user_name"] for p in declined]) if declined else "Отказавшихся нет."

    # Лимит участников
    limit_text = "∞ (бесконечный)" if event["participant_limit"] is None else str(event["participant_limit"])

    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Форматируем дату с днём недели
    date = datetime.strptime(event["date"], "%d.%m.%Y").date()
    formatted_date = date.strftime("%d.%m.%Y (%A)")

    # Вычисляем оставшееся время до мероприятия
    time_until = time_until_event(event['date'], event['time'], tz)

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
            if "Message is not modified" not in str(e):
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                raise e
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

            # Закрепляем сообщение
            await pin_message(context, chat_id, message.message_id)
            return message.message_id
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            raise e