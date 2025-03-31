from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_state, get_draft, clear_user_state
from src.handlers.conversation_handler_states import *
from src.logger.logger import logger


async def restore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user_state = get_user_state(context.bot_data["drafts_db_path"], user_id)

        if not user_state:
            return None

        draft = get_draft(context.bot_data["drafts_db_path"], user_state["draft_id"])
        if not draft:
            clear_user_state(context.bot_data["drafts_db_path"], user_id)
            return None

        # Преобразуем Row в dict если нужно
        if hasattr(draft, 'keys'):  # Это sqlite3.Row
            draft = dict(draft)

        # Восстанавливаем данные
        context.user_data.update({
            "draft_id": user_state["draft_id"],
            "bot_message_id": draft.get("bot_message_id"),
            "description": draft.get("description"),
            "date": draft.get("date"),
            "time": draft.get("time")
        })

        # Перенаправляем в соответствующий обработчик
        if user_state["handler"] == "create_event_handler":
            if user_state["state"] == SET_DESCRIPTION:
                from src.event.create.set_description import set_description
                return await set_description(update, context)
            elif user_state["state"] == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            elif user_state["state"] == SET_TIME:
                from src.event.create.set_time import set_time
                return await set_time(update, context)
            elif user_state["state"] == SET_LIMIT:
                from src.event.create.set_limit import set_limit
                return await set_limit(update, context)

        elif user_state["handler"] == "mention_handler":
            if user_state["state"] == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            elif user_state["state"] == SET_TIME:
                from src.event.create.set_time import set_time
                return await set_time(update, context)
            elif user_state["state"] == SET_LIMIT:
                from src.event.create.set_limit import set_limit
                return await set_limit(update, context)

        return None

    except Exception as e:
        logger.error(f"Ошибка восстановления состояния: {e}")
        clear_user_state(context.bot_data["drafts_db_path"], update.message.from_user.id)
        return None


# Добавляем этот обработчик в главный файл бота
def get_restore_handler():
    return MessageHandler(filters.TEXT & ~filters.COMMAND, restore_handler)