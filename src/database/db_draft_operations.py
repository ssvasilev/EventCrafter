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

def add_draft(db_path, creator_id, chat_id, status, description=None, date=None, time=None,
              participant_limit=None, current_state=None, bot_message_id=None):
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
    :param current_state: Текущее состояние диалога (новое поле).
    :param bot_message_id: ID сообщения бота (новое поле).
    :return: ID добавленного черновика.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Текущее время для created_at и updated_at
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO drafts (
                    creator_id, 
                    chat_id, 
                    status, 
                    description, 
                    date, 
                    time, 
                    participant_limit, 
                    current_state,
                    bot_message_id,
                    created_at, 
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    creator_id,
                    chat_id,
                    status,
                    description,
                    date,
                    time,
                    participant_limit,
                    current_state,
                    bot_message_id,
                    now,
                    now
                ),
            )
            draft_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Добавлен черновик ID {draft_id}. Состояние: {current_state}")
            return draft_id
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении черновика: {e}")
        return None

def update_draft(db_path, draft_id, status=None, current_state=None, description=None,
                date=None, time=None, participant_limit=None, bot_message_id=None):
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
            if current_state:
                updates.append("current_state = ?")
                params.append(current_state)
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
            if bot_message_id:
                updates.append("bot_message_id = ?")
                params.append(bot_message_id)

            updates.append("updated_at = ?")
            params.append(now)
            params.append(draft_id)

            cursor.execute(
                f"UPDATE drafts SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
            logger.info(f"Черновик {draft_id} обновлен. Изменения: {', '.join(updates)}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении черновика {draft_id}: {e}")
        raise

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
        return cursor.fetchone()

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