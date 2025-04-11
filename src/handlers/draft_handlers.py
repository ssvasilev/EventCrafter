from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters
from src.handlers.draft_utils import process_draft_step
from src.database.db_draft_operations import get_user_chat_draft
from src.logger import logger


async def handle_draft_message(update, context):
    """Обработчик сообщений для черновиков с улучшенной обработкой ошибок"""
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
        await context.bot.answer_callback_query(
            callback_query_id=update.message.message_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода",
            show_alert=True
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass


def register_draft_handlers(application):
    """Регистрирует обработчики черновиков"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_draft_message
    ))