from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from datetime import datetime
import logging

from src.handlers.conversation_handler_states import SET_DATE
from src.database.db_draft_operations import update_draft, add_draft

# Настройка логгера
logger = logging.getLogger(__name__)

async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем данные пользователя
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    description = update.message.text

    try:
        # Создаем новый черновик
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id,
            description=description
        )

        # Сохраняем данные в контекст
        context.user_data.update({
            "draft_id": draft_id,
            "current_state": "SET_DATE"
        })

        # Отправляем сообщение с запросом даты
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup
        )

        # Сохраняем ID сообщения бота
        context.user_data["bot_message_id"] = message.message_id

        # Обновляем черновик в базе
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_DATE",
            current_state="SET_DATE",  # Новый параметр
            bot_message_id=message.message_id
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        return SET_DATE

    except Exception as e:
        logger.error(f"Ошибка в set_description: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при создании мероприятия. Попробуйте еще раз.")
        return ConversationHandler.END