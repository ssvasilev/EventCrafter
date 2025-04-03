from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_draft_operations import delete_draft, get_draft
from src.database.db_operations import get_event
from src.message.send_message import send_event_message
from src.session_manager import SessionManager
from src.logger.logger import logger

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    session_manager = SessionManager(context.bot_data["sessions_db_path"])

    try:
        if not query.data.startswith("cancel|"):
            raise ValueError("Invalid cancel command")

        draft_id = int(query.data.split("|")[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise ValueError("Draft not found")

        # Проверка принадлежности черновика пользователю и чату
        active_draft_id = session_manager.get_active_session(user_id, chat_id)
        if str(draft_id) != str(active_draft_id):
            raise ValueError("Draft doesn't belong to this user/chat")

        delete_draft(context.bot_data["drafts_db_path"], draft_id)
        session_manager.clear_session(user_id, chat_id)

        if draft.get("event_id"):  # Редактирование
            await restore_original_message(context, draft)
        else:  # Создание
            await query.message.delete()

    except Exception as e:
        logger.error(f"Cancel error: {str(e)}")
        await safe_edit_message(query, "⚠️ Не удалось выполнить отмену")

async def restore_original_message(context, draft):
    event = get_event(context.bot_data["db_path"], draft["event_id"])
    if event and draft.get("original_message_id"):
        try:
            await context.bot.delete_message(
                chat_id=draft["chat_id"],
                message_id=draft.get("bot_message_id")
            )
        except:
            pass

        await send_event_message(
            event["id"],
            context,
            draft["chat_id"],
            message_id=draft["original_message_id"]
        )

async def safe_edit_message(query, text):
    try:
        await query.edit_message_text(text)
    except:
        pass