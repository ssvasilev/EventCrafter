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

def add_draft(db_path, creator_id, chat_id, status, description=None, date=None, time=None, participant_limit=None):
    """
    Добавляет черновик мероприятия в базу данных.
    :param db_path: Путь к базе данных.
    :param creator_id: ID создателя черновика.
    :param chat_id: ID чата.
    :param status: Статус черновика.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия.
    :param time: Время мероприятия.
    :param participant_limit: Лимит участников.
    :return: ID добавленного черновика.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Текущее время для created_at и updated_at
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO drafts (creator_id, chat_id, status, description, date, time, participant_limit, created_at , updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (creator_id, chat_id, status, description, date, time, participant_limit, now, now),
            )
            draft_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Черновик добавлен с ID: {draft_id}")
            return draft_id
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении черновика в базу данных: {e}")
        return None

def update_draft(db_path, draft_id, status=None, description=None, date=None, time=None, participant_limit=None):
    """
    Обновляет черновик мероприятия в базе данных.
    :param db_path: Путь к базе данных.
    :param draft_id: ID черновика.
    :param status: Статус черновика.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия.
    :param time: Время мероприятия.
    :param participant_limit: Лимит участников.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Текущее время для updated_at
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if status:
                updates.append("status = ?")
                params.append(status)
            if description:
                updates.append("description = ?")
                params.append(description)
            if date:
                updates.append("date = ?")
                params.append(date)
            if time:
                updates.append("time = ?")
                params.append(time)
            if participant_limit is not None:
                updates.append("participant_limit = ?")
                params.append(participant_limit)
            # Добавляем обновление поля updated_at
            updates.append("updated_at = ?")
            params.append(now)
            params.append(draft_id)
            cursor.execute(
                f"UPDATE drafts SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            logger.info(f"Черновик с ID {draft_id} обновлен.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении черновика: {e}")

def get_draft(db_path, draft_id):
    """
    Возвращает черновик мероприятия по его ID.
    :param db_path: Путь к базе данных.
    :param draft_id: ID черновика.
    :return: Черновик мероприятия.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_draft(db_path, creator_id):
    """
    Возвращает активный черновик пользователя.
    :param db_path: Путь к базе данных.
    :param creator_id: ID создателя черновика.
    :return: Черновик мероприятия.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE creator_id = ? AND status != 'DONE'", (creator_id,))
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

def set_user_state(db_path, user_id, handler_name, state, draft_id=None):
    """Сохраняет текущее состояние пользователя."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_states 
                (user_id, current_handler, current_state, draft_id) 
                VALUES (?, ?, ?, ?)
                """,
                (user_id, handler_name, state, draft_id),
            )
            conn.commit()
            logger.info(f"Состояние сохранено для пользователя {user_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при сохранении состояния: {e}")

def get_user_state(db_path, user_id):
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT current_handler, current_state, draft_id 
            FROM user_states 
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def clear_user_state(db_path, user_id):
    if not user_id:
        logger.warning("Попытка очистки состояния для None user_id")
        return
    """Очищает состояние пользователя."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_states WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
            logger.info(f"Состояние очищено для пользователя {user_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при очистке состояния: {e}")