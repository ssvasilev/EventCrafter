from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.logger.logger import logger
from src.database.db_draft_operations import clear_user_state, update_draft


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        db_path = context.bot_data["drafts_db_path"]

        # Очищаем состояние
        clear_user_state(db_path, user_id)

        # Помечаем черновик как отмененный
        if 'draft_id' in context.user_data:
            update_draft(
                db_path=db_path,
                draft_id=context.user_data["draft_id"],
                status="CANCELED"
            )

        # Пытаемся удалить или отредактировать сообщение
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except BadRequest:
            try:
                await query.edit_message_text(
                    text="Операция отменена",
                    reply_markup=None
                )
            except BadRequest:
                pass

        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка отмены: {e}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    logger.info(f"Обработка команды отмены для user_id={user_id}")

    clear_user_state(context.bot_data["drafts_db_path"], user_id)
    context.user_data.clear()

    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END