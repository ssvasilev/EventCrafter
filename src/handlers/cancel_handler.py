from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.logger.logger import logger
from src.database.db_draft_operations import clear_user_state

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        chat_id = query.message.chat_id
        message_id = query.message.message_id

        logger.info(f"Обработка отмены для user_id={user_id}")

        # Очищаем состояние
        clear_user_state(context.bot_data["drafts_db_path"], user_id)
        context.user_data.clear()

        # Пытаемся отредактировать сообщение вместо удаления
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Операция отменена. Вы можете начать заново.",
                reply_markup=None  # Убираем клавиатуру
            )
            logger.info("Сообщение успешно отредактировано")
        except BadRequest as e:
            if "Message to edit not found" in str(e):
                logger.warning("Сообщение для редактирования не найдено, отправляем новое")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Операция отменена. Вы можете начать заново."
                )
            else:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                raise

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Критическая ошибка в cancel_input: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Произошла ошибка при отмене операции"
            )
        except:
            logger.error("Не удалось отправить сообщение об ошибке")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        logger.info(f"Обработка команды отмены для user_id={user_id}")

        clear_user_state(context.bot_data["drafts_db_path"], user_id)
        context.user_data.clear()

        await update.message.reply_text("Создание мероприятия отменено.")
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка в cancel: {e}")
        await update.message.reply_text("⚠️ Ошибка при отмене")
        return ConversationHandler.END