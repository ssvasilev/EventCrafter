from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_state, get_draft, clear_user_state
from src.handlers.conversation_handler_states import *
from src.logger.logger import logger


async def restore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пропускаем команды и не текстовые сообщения
    if not update.message or not update.message.text or update.message.text.startswith('/'):
        return None

    user_id = update.message.from_user.id
    db_path = context.bot_data["drafts_db_path"]

    # Получаем только активные сессии
    user_state = get_active_user_state(db_path, user_id)
    if not user_state:
        return None

    draft = get_draft(db_path, user_state["draft_id"])
    if not draft:
        clear_user_state(db_path, user_id)
        return None

    # Восстанавливаем контекст
    context.user_data.update({
        "draft_id": draft["id"],
        "description": draft.get("description"),
        "date": draft.get("date"),
        "time": draft.get("time"),
        "restored": True  # Флаг восстановления
    })

    # Отправляем новое сообщение вместо редактирования
    try:
        message = await send_restored_message(context, update.message.chat_id, draft, user_state["state"])
        context.user_data["bot_message_id"] = message.message_id
    except Exception as e:
        logger.error(f"Ошибка отправки восстановленного сообщения: {e}")
        return None

    # Перенаправляем в нужный обработчик
    return await redirect_to_handler(update, context, user_state["handler"], user_state["state"])


def get_active_user_state(db_path, user_id):
    """Получает только активные сессии с существующими черновиками"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT us.current_handler, us.current_state, us.draft_id
            FROM user_states us
            JOIN drafts d ON us.draft_id = d.id
            WHERE us.user_id = ? AND d.status NOT IN ('DONE', 'CANCELED')
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# Добавляем этот обработчик в главный файл бота
def get_restore_handler():
    return MessageHandler(filters.TEXT & ~filters.COMMAND, restore_handler)