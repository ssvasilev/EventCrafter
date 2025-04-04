import os
import sqlite3
from datetime import datetime
from src.logger.logger import logger

def get_db_connection(db_path):
    """Устанавливает соединение с базой данных SQLite."""
    directory = os.path.dirname(db_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def add_draft(db_path, creator_id, chat_id, status, description=None, date=None, time=None, participant_limit=None, bot_message_id=None):
    """Добавляет черновик мероприятия в базу данных."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO drafts (creator_id, chat_id, status, description, date, time, participant_limit, bot_message_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (creator_id, chat_id, status, description, date, time, participant_limit, bot_message_id, now, now),
            )
            draft_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Черновик добавлен с ID: {draft_id}")
            return draft_id
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении черновика: {e}")
        return None

def update_draft(db_path, draft_id, status=None, description=None, date=None, time=None, participant_limit=None, bot_message_id=None):
    """Обновляет черновик мероприятия в базе данных."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            if status: updates.append("status = ?"); params.append(status)
            if description: updates.append("description = ?"); params.append(description)
            if date: updates.append("date = ?"); params.append(date)
            if time: updates.append("time = ?"); params.append(time)
            if participant_limit is not None: updates.append("participant_limit = ?"); params.append(participant_limit)
            if bot_message_id is not None: updates.append("bot_message_id = ?"); params.append(bot_message_id)

            updates.append("updated_at = ?")
            params.append(now)
            params.append(draft_id)

            cursor.execute(f"UPDATE drafts SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            logger.info(f"Черновик с ID {draft_id} обновлен.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении черновика: {e}")

def get_draft(db_path, draft_id):
    """Возвращает черновик мероприятия по его ID."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        result = cursor.fetchone()
        return dict(result) if result else None

def get_active_draft(db_path, creator_id, chat_id):
    """Возвращает активный черновик пользователя в указанном чате."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE creator_id = ? AND chat_id = ? AND status != 'DONE'",
            (creator_id, chat_id)
        )
        result = cursor.fetchone()
        return dict(result) if result else None

def delete_draft(db_path, draft_id):
    """Удаляет черновик мероприятия из базы данных по его ID."""
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.commit()
            logger.info(f"Черновик с ID {draft_id} удалён.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении черновика: {e}")