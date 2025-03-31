from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.database.db_draft_operations import delete_draft
from src.logger.logger import logger

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Полная очистка
    keys = list(context.user_data.keys())
    for key in keys:
        del context.user_data[key]

    try:
        if "draft_id" in context.user_data:
            delete_draft(context.bot_data["drafts_db_path"], context.user_data["draft_id"])

        await query.edit_message_text(
            text="❌ Создание мероприятия отменено",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Cancel error: {e}")
        await query.answer("⚠️ Ошибка при отмене")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        draft_id = context.user_data.get("draft_id")
        if draft_id:
            delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Полностью очищаем user_data
        keys = list(context.user_data.keys())
        for key in keys:
            del context.user_data[key]

        await update.message.reply_text("❌ Создание мероприятия отменено.")
    except Exception as e:
        logger.error(f"Error in cancel command: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при отмене.")
    finally:
        context.user_data.clear()
        return ConversationHandler.END