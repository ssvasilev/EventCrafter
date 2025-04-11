from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters
from src.handlers.draft_utils import process_draft_step
from src.database.db_draft_operations import get_user_chat_draft
from src.logger import logger


async def handle_draft_message(update, context):
    """Обработчик сообщений для черновиков с защитой от устаревших запросов"""
    if not update.message:
        return

    try:
        draft = get_user_chat_draft(
            context.bot_data["drafts_db_path"],
            update.message.from_user.id,
            update.message.chat_id
        )

        if draft:
            await process_draft_step(update, context, draft)

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")

        # Пытаемся отправить сообщение об ошибке разными способами
        try:
            # Сначала пробуем через всплывающее окно
            await context.bot.answer_callback_query(
                callback_query_id=update.message.message_id,
                text="⚠️ Произошла ошибка при обработке вашего ввода",
                show_alert=True
            )
        except Exception as callback_error:
            logger.warning(f"Не удалось отправить callback: {callback_error}")
            # Если не получилось через callback, пробуем обычное сообщение
            try:
                error_msg = await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text="⚠️ Произошла ошибка при обработке вашего ввода"
                )
                # Удаляем через 5 секунд, чтобы не засорять чат
                await asyncio.sleep(5)
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=error_msg.message_id
                )
            except Exception as msg_error:
                logger.error(f"Не удалось отправить сообщение об ошибке: {msg_error}")

        # Пытаемся удалить исходное сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as delete_error:
            logger.warning(f"Не удалось удалить сообщение: {delete_error}")


def register_draft_handlers(application):
    """Регистрирует обработчики черновиков"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_draft_message
    ))