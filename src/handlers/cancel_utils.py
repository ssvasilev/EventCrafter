from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.db_draft_operations import delete_draft, get_draft
from src.database.db_operations import get_event
from src.message.send_message import send_event_message
from src.logger import logger


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода при редактировании поля"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise Exception("Черновик не найден")

        if draft.get("event_id") and draft.get("original_message_id"):
            event = get_event(context.bot_data["db_path"], draft["event_id"])
            if event:
                await send_event_message(
                    event["id"],
                    context,
                    draft["chat_id"],
                    message_id=draft["original_message_id"]
                )

        delete_draft(context.bot_data["drafts_db_path"], draft_id)

    except Exception as e:
        logger.error(f"Ошибка при отмене ввода: {e}")
        await query.edit_message_text("⚠️ Не удалось отменить ввод")