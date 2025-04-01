from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_draft_operations import delete_draft, get_user_chat_draft
from src.logger.logger import logger

async def cancel_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены черновика"""
    query = update.callback_query
    await query.answer()

    # Получаем ID черновика из callback_data (формат: cancel_draft|123)
    draft_id = int(query.data.split('|')[1])

    try:
        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Удаляем сообщение бота с формой
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение бота: {e}")

        await query.edit_message_text("Создание мероприятия отменено.")

    except Exception as e:
        logger.error(f"Ошибка при отмене черновика: {e}")
        await query.edit_message_text("Произошла ошибка при отмене мероприятия.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Ищем активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)

    if draft:
        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

        # Пытаемся удалить сообщение бота с формой
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=draft["bot_message_id"]
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение бота: {e}")

    await update.message.reply_text("Создание мероприятия отменено.")