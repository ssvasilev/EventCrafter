from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.logger.logger import logger
from src.database.db_draft_operations import clear_user_state

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    logger.info(f"Обработка отмены для user_id={user_id}")

    # Очищаем состояние
    clear_user_state(context.bot_data["drafts_db_path"], user_id)
    context.user_data.clear()

    try:
        # Пытаемся отредактировать сообщение
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Операция отменена. Вы можете начать заново.",
                reply_markup=None
            )
            logger.info("Сообщение успешно отредактировано")
            return ConversationHandler.END

        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Сообщение уже содержит нужный текст - ничего не делаем
                logger.info("Сообщение уже содержит текст отмены")
                return ConversationHandler.END

            elif "Message to edit not found" in str(e):
                logger.warning("Сообщение не найдено, отправляем новое")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Операция отменена. Вы можете начать заново."
                )
                return ConversationHandler.END

            else:
                logger.error(f"Неизвестная ошибка при редактировании: {e}")
                raise

    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        # Не отправляем дополнительное сообщение об ошибке, чтобы избежать дублирования
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    logger.info(f"Обработка команды отмены для user_id={user_id}")

    clear_user_state(context.bot_data["drafts_db_path"], user_id)
    context.user_data.clear()

    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END