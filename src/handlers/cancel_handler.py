from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.database.db_draft_operations import delete_draft
from src.logger.logger import logger

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Полная очистка user_data
        context.user_data.clear()
    except Exception as e:
        logger.error(f"Error in cancel handler: {e}")
        await update.callback_query.answer("⚠️ Ошибка при отмене")
    query = update.callback_query
    await query.answer()

    try:
        # Получаем данные из user_data
        draft_id = context.user_data.get("draft_id")
        chat_id = query.message.chat_id

        # Удаляем черновик из базы данных
        if draft_id:
            try:
                delete_draft(context.bot_data["drafts_db_path"], draft_id)
                logger.info(f"Deleted draft {draft_id} for user {update.effective_user.id}")
            except Exception as e:
                logger.error(f"Error deleting draft: {e}")

        # Полностью очищаем user_data
        keys = list(context.user_data.keys())
        for key in keys:
            del context.user_data[key]

        # Редактируем сообщение вместо удаления
        await query.edit_message_text(
            text="❌ Создание мероприятия отменено.",
            reply_markup=None
        )

    except Exception as e:
        logger.error(f"Error in cancel handler: {e}")
        try:
            await query.edit_message_text("❌ Отмена не удалась. Попробуйте снова.")
        except:
            pass

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

    return ConversationHandler.END