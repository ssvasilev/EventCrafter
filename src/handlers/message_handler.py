from telegram.ext import MessageHandler, filters
from src.database.db_draft_operations import get_user_chat_draft
from src.handlers.draft_utils import process_draft_step


async def handle_message(update, context):
    """Основной обработчик сообщений"""
    if not update.message:
        return

    draft = get_user_chat_draft(
        context.bot_data["drafts_db_path"],
        update.message.from_user.id,
        update.message.chat_id
    )

    if draft:
        await process_draft_step(update, context, draft)


def register_message_handlers(application):
    """Регистрирует обработчики сообщений"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ), group=1)