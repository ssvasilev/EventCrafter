from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from database.db_operations import update_event_field
from handlers.conversation_handler_states import EDIT_DESCRIPTION
from logger.logger import logger
from message.send_message import send_event_message

# Обработка редактирования описания
async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Сохраняем event_id в context.user_data
    event_id = query.data.split("|")[1]
    context.user_data["event_id"] = event_id

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение с запросом нового описания
    sent_message = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Введите новое описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Сохраняем ID нового сообщения в context.user_data
    context.user_data["bot_message_id"] = sent_message.message_id

    # Переходим к состоянию EDIT_DESCRIPTION
    return EDIT_DESCRIPTION

# Обработка ввода нового описания
async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text
    event_id = context.user_data["event_id"]
    db_path = context.bot_data["db_path"]

    try:
        # Обновляем описание в базе данных
        update_event_field(db_path, event_id, "description", new_description)

        # Редактируем сообщение с новым описанием
        await send_event_message(event_id, context, update.message.chat_id, context.user_data["bot_message_id"])

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END
    except BadRequest as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении описания.")
        return ConversationHandler.END