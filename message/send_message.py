import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    JobQueue,
)

from database.db_operations import get_event, get_participants, get_reserve, get_declined, update_message_id
from eventcrafterbot import DB_PATH
from handlers.utils import time_until_event

from logger.logger import logger


async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int = None):
    """
    Отправляет или редактирует сообщение с информацией о мероприятии.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    :param chat_id: ID чата, куда отправляется сообщение.
    :param message_id: ID сообщения для редактирования (если None, отправляется новое сообщение).
    :return: ID отправленного или отредактированного сообщения.
    """
    db_path = context.bot_data.get("db_path", DB_PATH)
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

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

    # Текст сообщения
    time_until = time_until_event(event['date'], event['time'])
    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {event['date']}\n"
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
        except telegram.error.BadRequest as e:
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
            # Сохраняем message_id в базе данных
            update_message_id(db_path, event_id, message.message_id)
            logger.info(f"Новое сообщение отправлено с ID: {message.message_id}")

            # Закрепляем сообщение в чате
            try:
                await context.bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=message.message_id,
                    disable_notification=True  # Отключаем уведомление о закреплении
                )
                logger.info(f"Сообщение {message.message_id} закреплено в чате {chat_id}.")
            except telegram.error.BadRequest as e:
                logger.error(f"Ошибка при закреплении сообщения: {e}")
            except telegram.error.Forbidden as e:
                logger.error(f"Бот не имеет прав на закрепление сообщений: {e}")

            return message.message_id
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            raise e