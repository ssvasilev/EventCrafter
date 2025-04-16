from datetime import datetime

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import DB_PATH
from src.database.db_operations import get_event, get_participants, get_reserve, get_declined, update_message_id
from src.logger.logger import logger
from src.utils.pin_message import pin_message_safe
from src.utils.utils import time_until_event, format_users_list

# Константы для текстов пустых списков
EMPTY_PARTICIPANTS_TEXT = "Ещё никто не участвует."
EMPTY_RESERVE_TEXT = "Резерв пуст."
EMPTY_DECLINED_TEXT = "Отказавшихся нет."


async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id):
    logger.warning(f"Готовимся к отправке сообщения о мероприятие с ID {event_id} и номером сообщения {message_id}.")
    """
    Отправляет или редактирует сообщение с информацией о мероприятии и закрепляет его.
    Возвращает ID сообщения.
    """
    try:
        db_path = context.bot_data.get("db_path", DB_PATH)
        event = get_event(db_path, event_id)
        if not event:
            logger.error(f"Мероприятие с ID {event_id} не найдено.")
            return None

        # Получаем данные для сообщения
        participants = get_participants(db_path, event_id)
        reserve = get_reserve(db_path, event_id)
        declined = get_declined(db_path, event_id)

        # Форматируем текст и клавиатуру
        message_text = (
            f"📢 <b>{event['description']}</b>\n"
            f"📅 <i>Дата:</i> {datetime.strptime(event['date'], '%d.%m.%Y').strftime('%d.%m.%Y (%A)')}\n"
            f"🕒 <i>Время:</i> {event['time']}\n"
            f"⏳ <i>До мероприятия:</i> {time_until_event(event['date'], event['time'], context.bot_data.get('tz'))}\n"
            f"👥 <i>Лимит:</i> {'∞' if event['participant_limit'] is None else event['participant_limit']}\n\n"
            f"✅ <i>Участники:</i>\n{format_users_list(participants, EMPTY_PARTICIPANTS_TEXT)}\n\n"
            f"⏳ <i>Резерв:</i>\n{format_users_list(reserve, EMPTY_RESERVE_TEXT)}\n\n"
            f"❌ <i>Отказавшиеся:</i>\n{format_users_list(declined, EMPTY_DECLINED_TEXT)}"
        )

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
            [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
            [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")]
        ])

        # Редактирование существующего сообщения
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                await pin_message_safe(context, chat_id, message_id)
                return message_id
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение {message_id}: {e}")
                message_id = None  # Переключимся на создание нового

        # Создание нового сообщения
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        new_message_id = message.message_id
        logger.info(f"Начинаем закреплять сообщение  {message_id} в чате {chat_id}")
        await pin_message_safe(context, chat_id, new_message_id)
        # Обновляем ID сообщения в БД и закрепляем
        update_message_id(db_path, event_id, new_message_id)

        return new_message_id

    except Exception as e:
        logger.error(f"Ошибка в send_event_message: {e}")
        raise