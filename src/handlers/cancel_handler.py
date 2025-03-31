from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.database.db_draft_operations import clear_user_state
from src.logger.logger import logger


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Очищаем состояние пользователя
    clear_user_state(context.bot_data["drafts_db_path"], update.message.from_user.id)

    # Восстанавливаем исходное сообщение
    original_message_id = context.user_data.get("bot_message_id")
    original_text = context.user_data.get("original_text")
    original_reply_markup = context.user_data.get("original_reply_markup")

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

    context.user_data.clear()  # Очищаем user_data
    return ConversationHandler.END


# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    # Очищаем состояние пользователя
    clear_user_state(context.bot_data["drafts_db_path"], update.message.from_user.id)
    await update.message.reply_text("Создание мероприятия отменено.")
    context.user_data.clear()
    return ConversationHandler.END