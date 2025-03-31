from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from src.database.db_draft_operations import delete_draft
from src.logger.logger import logger


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        # Получаем данные из user_data
        draft_id = context.user_data.get("draft_id")
        chat_id = query.message.chat_id
        message_id = query.message.message_id

        # Удаляем черновик из базы данных, если он есть
        if draft_id:
            try:
                delete_draft(context.bot_data["drafts_db_path"], draft_id)
                logger.info(f"Черновик {draft_id} отменен пользователем {update.effective_user.id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении черновика: {e}")

        # Удаляем сообщение с кнопками создания мероприятия
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")

        # Отправляем сообщение об отмене
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Создание мероприятия отменено."
        )

    except Exception as e:
        logger.error(f"Ошибка в обработчике отмены: {e}")
        try:
            await query.edit_message_text("❌ Произошла ошибка при отмене.")
        except:
            pass

    finally:
        context.user_data.clear()
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        draft_id = context.user_data.get("draft_id")
        if draft_id:
            delete_draft(context.bot_data["drafts_db_path"], draft_id)

        await update.message.reply_text("❌ Создание мероприятия отменено.")
    except Exception as e:
        logger.error(f"Ошибка в обработчике cancel: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при отмене.")

    context.user_data.clear()
    return ConversationHandler.END