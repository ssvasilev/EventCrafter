from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_all_active_drafts, get_user_draft
from src.handlers.conversation_handler_states import SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT
from src.event.create.set_description import set_description
from src.event.create.set_date import set_date
from src.event.create.set_time import set_time
from src.event.create.set_limit import set_limit


async def continue_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, есть ли у пользователя активный черновик
    draft = get_user_draft(context.bot_data["drafts_db_path"], update.message.from_user.id)
    if not draft:
        return  # Нет активного черновика - игнорируем

    # В зависимости от статуса черновика продолжаем соответствующий диалог
    if draft["status"] == "AWAIT_DESCRIPTION":
        context.user_data.update({
            "draft_id": draft["id"],
            "bot_message_id": None,  # Будет установлено при ответе
            "chat_id": draft["chat_id"]
        })
        return await set_description(update, context)

    elif draft["status"] == "AWAIT_DATE":
        context.user_data.update({
            "draft_id": draft["id"],
            "bot_message_id": None,
            "chat_id": draft["chat_id"],
            "description": draft["description"]
        })
        return await set_date(update, context)

    elif draft["status"] == "AWAIT_TIME":
        context.user_data.update({
            "draft_id": draft["id"],
            "bot_message_id": None,
            "chat_id": draft["chat_id"],
            "description": draft["description"],
            "date": draft["date"]
        })
        return await set_time(update, context)

    elif draft["status"] == "AWAIT_PARTICIPANT_LIMIT":
        context.user_data.update({
            "draft_id": draft["id"],
            "bot_message_id": None,
            "chat_id": draft["chat_id"],
            "description": draft["description"],
            "date": draft["date"],
            "time": draft["time"]
        })
        return await set_limit(update, context)