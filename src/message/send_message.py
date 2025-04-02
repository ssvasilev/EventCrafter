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

async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int = None):
    """
    Отправляет или редактирует сообщение с информацией о мероприятии.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    :param chat_id: ID чата, куда отправляется сообщение.
    :param message_id: ID сообщения для редактирования (если None, отправляется новое сообщение).
    :return: ID отправленного или отредактированного сообщения.
    """
    db_path = context.bot_data.get("db_path")
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return None

    try:
        # Получаем участников, резерв и отказавшихся
        participants = get_participants(db_path, event_id)
        reserve = get_reserve(db_path, event_id)
        declined = get_declined(db_path, event_id)

        # Форматируем списки
        participants_text = format_users_list(participants, EMPTY_PARTICIPANTS_TEXT)
        reserve_text = format_users_list(reserve, EMPTY_RESERVE_TEXT)
        declined_text = format_users_list(declined, EMPTY_DECLINED_TEXT)

        # Лимит участников
        limit_text = "∞ (без лимита)" if event["participant_limit"] is None else str(event["participant_limit"])

        # Клавиатура
        keyboard = [
            [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
            [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
            [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Получаем часовой пояс
        tz = context.bot_data.get("tz")

        # Форматируем дату и время
        time_until = time_until_event(event['date'], event['time'], tz)
        date = datetime.strptime(event["date"], "%d.%m.%Y").date()
        formatted_date = date.strftime("%d.%m.%Y (%A)")

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

        # Редактирование или создание сообщения
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                logger.info(f"Сообщение {message_id} отредактировано")
                return message_id
            except telegram.error.BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning(f"Не удалось отредактировать {message_id}: {e}")
                    # Продолжаем создавать новое сообщение

        # Создание нового сообщения
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        new_message_id = message.message_id
        logger.info(f"Создано новое сообщение {new_message_id}")

        # Обновляем ID в базе
        if not update_message_id(db_path, event_id, new_message_id):
            logger.error(f"Не удалось обновить message_id в БД для {event_id}")

        # Закрепляем сообщение
        try:
            await pin_message(context, chat_id, new_message_id)
        except Exception as e:
            logger.error(f"Ошибка при закреплении сообщения: {e}")

        return new_message_id

    except Exception as e:
        logger.error(f"Критическая ошибка в send_event_message: {e}")
        raise