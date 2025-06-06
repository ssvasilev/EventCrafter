from telegram.error import BadRequest
from telegram.ext import MessageHandler, filters
from src.handlers.draft_utils import process_draft_step, show_input_error
from src.database.db_draft_operations import get_user_chat_draft, get_draft, update_draft
from src.logger import logger


async def handle_draft_message(update, context):
    """Обработчик сообщений для черновиков"""
    if not update.message:
        return

    try:
        # Получаем черновик как словарь
        draft = None
        if 'current_draft_id' in context.user_data:
            draft = get_draft(context.bot_data["drafts_db_path"], context.user_data['current_draft_id'])

        # Если не нашли, проверяем обычные черновики
        if not draft:
            draft = get_user_chat_draft(
                context.bot_data["drafts_db_path"],
                update.message.from_user.id,
                update.message.chat_id
            )
            if draft:
                context.user_data['current_draft_id'] = draft['id']

        if draft:
            # Для черновиков редактирования проверяем наличие event_id
            if draft.get("status", "").startswith("EDIT_") and not draft.get("event_id"):
                logger.error(f"Черновик редактирования без event_id: {draft}")
                await show_input_error(update, context, "⚠️ Ошибка: мероприятие не найдено")
                return

            # Если у черновика нет bot_message_id, создаём новое сообщение (только для новых черновиков, не для редактирования)
            if not draft.get("bot_message_id") and not draft.get("status", "").startswith("EDIT_"):
                message = await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text="Обработка вашего мероприятия..."
                )
                update_draft(
                    db_path=context.bot_data["drafts_db_path"],
                    draft_id=draft['id'],
                    bot_message_id=message.message_id
                )
                draft["bot_message_id"] = message.message_id  # Обновляем локальный объект

            await process_draft_step(update, context, draft)
            await update.message.delete()  # Удаляем сообщение пользователя

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}", exc_info=True)
        await show_input_error(update, context, "⚠️ Произошла ошибка при обработке вашего ввода")

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