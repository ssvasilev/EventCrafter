from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.db_operations import clear_user_state, get_user_state
from logger.logger import logger


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    db_path = context.bot_data["db_path"]

    # Получаем состояние пользователя из базы данных
    user_state = get_user_state(db_path, user_id)

    if user_state:
        # Извлекаем данные из состояния
        original_message_id = user_state.get("bot_message_id")
        original_text = user_state.get("original_text")
        original_reply_markup = user_state.get("original_reply_markup")

        # Восстанавливаем исходное сообщение
        if original_message_id and original_text:
            try:
                await context.bot.edit_message_text(
                    chat_id=query.message.chat_id,
                    message_id=original_message_id,
                    text=original_text,
                    reply_markup=original_reply_markup,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при восстановлении сообщения: {e}")
                await query.edit_message_text("Операция отменена.")
        else:
            await query.edit_message_text("Операция отменена.")

        # Очищаем состояние пользователя из базы данных
        clear_user_state(db_path, user_id)
    else:
        await query.edit_message_text("Операция отменена.")

    return ConversationHandler.END


# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END