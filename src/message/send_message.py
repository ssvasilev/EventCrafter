from datetime import datetime

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import DB_PATH
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
    """
    try:
        db_path = context.bot_data.get("db_path", DB_PATH)
        event = get_event(db_path, event_id)
        if not event:
            logger.error(f"Мероприятие с ID {event_id} не найдено.")
            return None

        # Получаем все необходимые данные
        participants = get_participants(db_path, event_id)
        reserve = get_reserve(db_path, event_id)
        declined = get_declined(db_path, event_id)

        # Форматируем сообщение со всеми необходимыми аргументами
        message_text, reply_markup = await format_event_message(
            event=event,
            participants=participants,
            reserve=reserve,
            declined=declined,
            context=context
        )

        # Пытаемся редактировать существующее сообщение
        if message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode="HTML",
                    read_timeout=20,
                    write_timeout=20,
                    connect_timeout=20,
                    pool_timeout=20
                )
                logger.info(f"Сообщение {message_id} отредактировано.")
                return message_id
            except Exception as edit_error:
                logger.warning(f"Не удалось отредактировать сообщение {message_id}: {edit_error}")
                # Продолжаем с отправкой нового сообщения

        # Отправляем новое сообщение
        try:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                read_timeout=20,
                write_timeout=20,
                connect_timeout=20,
                pool_timeout=20
            )
            new_message_id = message.message_id
            logger.info(f"Новое сообщение отправлено с ID: {new_message_id}")

            # Закрепляем сообщение в чате
            await pin_message(context, chat_id, message.message_id)

            # Обновляем message_id в базе данных
            update_message_id(db_path, event_id, new_message_id)
            return new_message_id

        except Exception as send_error:
            logger.error(f"Ошибка при отправке сообщения: {send_error}")
            raise

    except Exception as e:
        logger.error(f"Ошибка в send_event_message: {e}")
        raise

async def format_event_message(event, participants, reserve, declined, context):
    """Форматирует текст и клавиатуру для сообщения о мероприятии"""
    try:
        # Форматируем списки участников
        participants_text = format_users_list(participants, EMPTY_PARTICIPANTS_TEXT)
        reserve_text = format_users_list(reserve, EMPTY_RESERVE_TEXT)
        declined_text = format_users_list(declined, EMPTY_DECLINED_TEXT)

        # Лимит участников
        limit_text = "∞ (бесконечный)" if event["participant_limit"] is None else str(event["participant_limit"])

        # Клавиатура
        keyboard = [
            [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event['id']}")],
            [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event['id']}")],
            [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Получаем часовой пояс
        tz = context.bot_data.get("tz")

        # Вычисляем оставшееся время до мероприятия
        time_until = time_until_event(event['date'], event['time'], tz)

        # Форматируем дату с днём недели
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

        return message_text, reply_markup

    except Exception as e:
        logger.error(f"Ошибка в format_event_message: {e}")
        raise