import sqlite3

from telegram.ext import ContextTypes


async def restore_drafts_quietly(context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает черновики без уведомлений пользователя."""
    conn = sqlite3.connect(context.bot_data["drafts_db_path"])
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drafts WHERE status != 'DONE'")
    drafts = cursor.fetchall()
    conn.close()

    for draft in drafts:
        # Сохраняем данные в глобальный контекст (например, в Redis или словарь)
        # Пример для простоты (в реальности используйте persistent storage):
        context.bot_data.setdefault("active_drafts", {})
        context.bot_data["active_drafts"][draft["creator_id"]] = {
            "draft_id": draft["id"],
            "current_state": draft["current_state"],
            "bot_message_id": draft["bot_message_id"],
            "chat_id": draft["chat_id"]
        }