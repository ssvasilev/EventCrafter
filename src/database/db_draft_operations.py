import os
import sqlite3
from datetime import datetime
from src.logger.logger import logger


def get_db_connection(db_path):
    """
    Устанавливает соединение с базой данных SQLite.
    :param db_path: Путь к файлу базы данных.
    :return: Объект соединения с базой данных.
    """
    # Проверяем и создаём директорию, если её нет
    directory = os.path.dirname(db_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Устанавливаем соединение с базой данных
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def add_draft(db_path, creator_id, chat_id, status,
             description=None, date=None, time=None,
             participant_limit=None, event_id=None,
             original_message_id=None):
    """Добавляет черновик с поддержкой редактирования"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO drafts (
                    creator_id, chat_id, status, description, 
                    date, time, participant_limit, event_id,
                    original_message_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (creator_id, chat_id, status, description,
                 date, time, participant_limit, event_id,
                 original_message_id, now, now),
            )
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении черновика: {e}")
        return None


def update_draft(db_path, draft_id, **kwargs):
    """
    Обновляет черновик мероприятия в базе данных.
    Возвращает True при успешном обновлении, False при ошибке.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            updates = []
            params = []

            valid_fields = {
                'status', 'description', 'date', 'time',
                'participant_limit', 'bot_message_id', 'event_id'
            }

            for field, value in kwargs.items():
                if field in valid_fields:
                    updates.append(f"{field} = ?")
                    params.append(value)

            if not updates:
                logger.warning("Нет полей для обновления")
                return False

            # Добавляем обновление времени
            updates.append("updated_at = ?")
            params.append(now)

            params.append(draft_id)

            query = f"UPDATE drafts SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Черновик {draft_id} обновлен: {kwargs}")
            else:
                logger.warning(f"Черновик {draft_id} не найден")

            return updated

    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении черновика {draft_id}: {e}")
        return False

def get_draft(db_path: str, draft_id: int) -> dict:
    """Возвращает черновик как словарь"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_draft_by_event_id(db_path: str, event_id: int):
    """Находит черновик по ID мероприятия"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE event_id = ? AND status LIKE 'EDIT_%'",
            (event_id,)
        )
        return cursor.fetchone()

def get_user_chat_draft(db_path, creator_id, chat_id):
    """
    Возвращает активный черновик для конкретного пользователя и чата.
    :param db_path: Путь к базе данных.
    :param creator_id: ID создателя.
    :param chat_id: ID чата.
    :return: Черновик мероприятия или None.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE creator_id = ? AND chat_id = ? AND status != 'DONE'",
            (creator_id, chat_id)
        )
        return cursor.fetchone()

def get_user_draft(db_path: str, user_id: int) -> dict:
    """Возвращает черновик как словарь"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE creator_id = ? AND status LIKE 'AWAIT_%'",
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_drafts(db_path: str, user_id: int):
    """Возвращает все черновики пользователя"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE creator_id = ? AND status != 'DONE'",
            (user_id,)
        )
        return cursor.fetchall()

def get_draft_by_bot_message(db_path: str, bot_message_id: int):
    """Находит черновик по ID сообщения бота"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE bot_message_id = ?",
            (bot_message_id,)
        )
        return cursor.fetchone()

def delete_draft(db_path: str, draft_id: int):
    """
    Удаляет черновик мероприятия из базы данных по его ID.
    :param db_path: Путь к базе данных.
    :param draft_id: ID черновика.
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.commit()
            logger.info(f"Черновик с ID {draft_id} удалён.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении черновика: {e}")