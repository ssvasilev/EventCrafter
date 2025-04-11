from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters
from src.handlers.draft_utils import process_draft_step, _show_input_error
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
        draft = get_user_chat_draft(
            context.bot_data["drafts_db_path"],
            update.message.from_user.id,
            update.message.chat_id
        )
        if draft:
            await process_draft_step(update, context, draft)
    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")
        await _show_input_error(
            update, context,
            "⚠️ Произошла ошибка при обработке вашего ввода"
        )

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