from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_chat_draft
from src.handlers.draft_handlers import process_draft_step
from src.logger.logger import logger


async def handle_draft_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик сообщений для черновиков"""
    if not update.message:
        return

    # Получаем активный черновик
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
        handle_draft_message
    ), group=1)