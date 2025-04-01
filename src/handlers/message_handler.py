from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_chat_draft
from src.handlers.draft_utils import process_draft_step
from src.logger.logger import logger


async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перехватывает ВСЕ текстовые сообщения в чате"""
    if not update.message or not update.message.text:
        return

    # Игнорируем команды
    if update.message.text.startswith('/'):
        return

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], user_id, chat_id)
    if draft:
        try:
            await process_draft_step(update, context, draft)
            # Удаляем сообщение пользователя после обработки
            try:
                await update.message.delete()
            except BadRequest:
                pass
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")


def register_message_handlers(application):
    """Регистрирует обработчик всех сообщений"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_all_messages
    ), group=0)  # Группа 0 для приоритетной обработки