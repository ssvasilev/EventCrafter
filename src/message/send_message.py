from datetime import datetime

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.database.db_operations import get_event, get_participants, get_reserve, get_declined, update_message_id
from src.logger.logger import logger
from src.utils.pin_message import pin_message
from src.utils.utils import time_until_event, format_users_list

# Константы для текстов пустых списков
EMPTY_PARTICIPANTS_TEXT = "Ещё никто не участвует."
EMPTY_RESERVE_TEXT = "Резерв пуст."
EMPTY_DECLINED_TEXT = "Отказавшихся нет."

async def send_event_message(event_id, context, chat_id, message_id=None):
    """Отправляет или обновляет сообщение о мероприятии с обработкой ошибок"""
    try:
        db_path = context.bot_data["db_path"]

        # Получаем данные мероприятия
        event = get_event(db_path, event_id)
        if not event:
            logger.error(f"Мероприятие {event_id} не найдено")
            return None

        # Преобразуем в словарь если нужно
        if hasattr(event, '_fields'):  # Для sqlite3.Row
            event = dict(zip(event._fields, event))

        # Формируем текст сообщения
        participants_text = format_users_list(event["participants"], "Ещё никто не участвует")
        reserve_text = format_users_list(event["reserve"], "Резерв пуст")
        declined_text = format_users_list(event["declined"], "Отказавшихся нет")
        limit_text = "∞ (без лимита)" if not event["participant_limit"] else str(event["participant_limit"])

        # Форматируем дату
        event_date = datetime.strptime(event["date"], "%d.%m.%Y").strftime("%d.%m.%Y (%A)")
        time_until = time_until_event(event["date"], event["time"], context.bot_data.get("tz"))

        # Текст сообщения
        message_text = (
            f"📢 <b>{event['description']}</b>\n"
            f"📅 <i>Дата:</i> {event_date}\n"
            f"🕒 <i>Время:</i> {event['time']}\n"
            f"⏳ <i>До мероприятия:</i> {time_until}\n"
            f"👥 <i>Лимит:</i> {limit_text}\n\n"
            f"✅ <i>Участники ({event['participants_count']}):</i>\n{participants_text}\n\n"
            f"⏳ <i>Резерв:</i>\n{reserve_text}\n\n"
            f"❌ <i>Отказавшиеся:</i>\n{declined_text}"
        )

        # Клавиатура
        keyboard = [
            [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
            [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")]
        ]
        if event["creator_id"] == context._user_id:
            keyboard.append([InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit|{event_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

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
                return message_id
            except Exception as edit_error:
                logger.warning(f"Не удалось отредактировать сообщение {message_id}: {str(edit_error)}")
                # Продолжаем создавать новое сообщение

        # Создание нового сообщения
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        new_message_id = message.message_id

        # Обновляем message_id в БД
        update_message_id(db_path, event_id, new_message_id)

        # Закрепляем сообщение
        try:
            await context.bot.pin_chat_message(chat_id, new_message_id)
        except Exception as pin_error:
            logger.warning(f"Не удалось закрепить сообщение: {str(pin_error)}")

        return new_message_id

    except Exception as e:
        logger.error(f"Критическая ошибка в send_event_message: {str(e)}")
        raise