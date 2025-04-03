from telegram.ext import MessageHandler, filters
from src.database.db_draft_operations import get_draft
from src.database.session_manager import SessionManager

from src.handlers.draft_utils import process_draft_step
from src.logger.logger import logger


async def handle_draft_message(update, context):
    """Обработчик сообщений для черновиков с проверкой сессии"""
    if not update.message:
        return

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Инициализация менеджера сессий
    session_manager = SessionManager(context.bot_data["sessions_db_path"])

    # Получаем активную сессию для этого пользователя в этом чате
    draft_id = session_manager.get_active_session(user_id, chat_id)
    if not draft_id:
        return  # Нет активной сессии для этого чата

    # Получаем черновик с проверкой принадлежности
    draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
    if not draft or draft["creator_id"] != user_id or draft["chat_id"] != chat_id:
        session_manager.clear_session(user_id, chat_id)
        return

    try:
        # Обработка шага черновика
        await process_draft_step(update, context, draft)

        # Обновляем время жизни сессии при успешной обработке
        session_manager.create_session(user_id, chat_id, draft_id)

    except Exception as e:
        logger.error(f"Draft processing error: {str(e)}")
        try:
            await update.message.reply_text("⚠️ Ошибка обработки данных. Попробуйте ещё раз.")
        except:
            pass


def register_draft_handlers(application):
    """Регистрирует обработчики черновиков с фильтрацией по сессиям"""

    # Фильтр для текстовых сообщений, не команд, с проверкой активной сессии
    class DraftFilter(filters.MessageFilter):
        def filter(self, message):
            if not message.text or message.text.startswith('/'):
                return False

            session_manager = SessionManager(application.bot_data["sessions_db_path"])
            return bool(
                session_manager.get_active_session(
                    message.from_user.id,
                    message.chat_id
                )
            )

    application.add_handler(MessageHandler(
        DraftFilter(),
        handle_draft_message
    ))