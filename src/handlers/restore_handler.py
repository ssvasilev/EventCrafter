from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_state, get_draft, clear_user_state
from src.handlers.conversation_handler_states import *
from src.logger.logger import logger


async def restore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Пропускаем не текстовые сообщения и команды
        if not update.message or not update.message.text or update.message.text.startswith('/'):
            return None

        user_id = update.message.from_user.id
        db_path = context.bot_data["drafts_db_path"]

        # Получаем состояние пользователя
        user_state = get_user_state(db_path, user_id)
        if not user_state:
            return None

        # Получаем черновик
        draft = get_draft(db_path, user_state["draft_id"])
        if not draft:
            return None

        # Преобразуем Row в dict если нужно
        draft = dict(draft) if hasattr(draft, 'keys') else draft

        # Восстанавливаем контекст
        context.user_data.update({
            "draft_id": draft["id"],
            "bot_message_id": draft.get("bot_message_id"),
            "description": draft.get("description"),
            "date": draft.get("date"),
            "time": draft.get("time"),
            "original_text": "Восстановление сессии...",
            "original_reply_markup": None
        })

        # Определяем обработчик и состояние
        handler = user_state["handler"]
        state = user_state["state"]

        logger.info(f"Восстановление: user={user_id}, handler={handler}, state={state}")

        # Перенаправляем в нужный обработчик
        if handler == "create_event_handler":
            if state == SET_DESCRIPTION:
                from src.event.create.set_description import set_description
                return await set_description(update, context)
            elif state == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            elif state == SET_TIME:
                from src.event.create.set_time import set_time
                return await set_time(update, context)
            elif state == SET_LIMIT:
                from src.event.create.set_limit import set_limit
                return await set_limit(update, context)

        elif handler == "mention_handler":
            if state == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            elif state == SET_TIME:
                from src.event.create.set_time import set_time
                return await set_time(update, context)
            elif state == SET_LIMIT:
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