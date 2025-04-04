from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.database.db_draft_operations import delete_draft
from src.logger.logger import logger

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик отмены ввода данных при создании/редактировании мероприятия.
    Удаляет черновик и восстанавливает исходное сообщение.
    """
    query = update.callback_query
    await query.answer()

    try:
        # Удаляем черновик, если он есть
        if 'draft_id' in context.user_data:
            delete_draft(
                db_path=context.bot_data["drafts_db_path"],
                draft_id=context.user_data["draft_id"]
            )
            logger.info(f"Черновик {context.user_data['draft_id']} удален по отмене")

        # Восстанавливаем исходное сообщение
        if 'original_text' in context.user_data and 'original_reply_markup' in context.user_data:
            await query.edit_message_text(
                text=context.user_data["original_text"],
                reply_markup=context.user_data["original_reply_markup"]
            )
        else:
            await query.edit_message_text("Операция отменена.")

        # Очищаем user_data
        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при обработке отмены: {e}")
        await query.edit_message_text("Произошла ошибка при отмене.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /cancel для отмены текущей операции.
    """
    await update.message.reply_text("Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END