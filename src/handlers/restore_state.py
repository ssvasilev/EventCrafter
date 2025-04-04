from telegram.ext import ContextTypes
from src.database.db_draft_operations import get_active_draft
from src.handlers.conversation_handler_states import (
    SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT
)
from src.logger.logger import logger

async def restore_user_state(user_id: int, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает состояние пользователя после перезагрузки бота"""
    try:
        active_draft = get_active_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id
        )

        if not active_draft:
            return None

        context.user_data.update({
            "draft_id": active_draft["id"],
            "restored_state": True
        })

        if active_draft["status"] == "AWAIT_DESCRIPTION":
            return SET_DESCRIPTION
        elif active_draft["status"] == "AWAIT_DATE":
            return SET_DATE
        elif active_draft["status"] == "AWAIT_TIME":
            return SET_TIME
        elif active_draft["status"] == "AWAIT_LIMIT":
            return SET_LIMIT

    except Exception as e:
        logger.error(f"Ошибка восстановления состояния: {e}")
        return None