from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters
from src.handlers.draft_utils import process_draft_step, _show_input_error
from src.database.db_draft_operations import get_user_chat_draft, get_draft
from src.logger import logger


async def handle_draft_message(update, context):
    """Обработчик сообщений для черновиков с поддержкой шаблонов"""
    if not update.message:
        return

    try:
        # 1. Пытаемся найти черновик в user_data (для шаблонов)
        draft = None
        if 'current_draft_id' in context.user_data:
            draft = get_draft(
                context.bot_data["drafts_db_path"],
                context.user_data['current_draft_id']
            )

        # 2. Если не нашли, проверяем обычные черновики
        if not draft:
            draft = get_user_chat_draft(
                context.bot_data["drafts_db_path"],
                update.message.from_user.id,
                update.message.chat_id
            )

        if draft:
            # Обрабатываем ввод в зависимости от статуса черновика
            await process_draft_step(update, context, draft)

            # Удаляем сообщение пользователя после успешной обработки
            try:
                await update.message.delete()
            except BadRequest as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}", exc_info=True)

        # Показываем пользователю ошибку
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