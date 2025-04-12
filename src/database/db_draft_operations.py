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
             original_message_id=None, is_from_template=False, bot_message_id=None):
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
                    original_message_id, created_at, updated_at,
                    is_from_template, bot_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (creator_id, chat_id, status, description,
                 date, time, participant_limit, event_id,
                 original_message_id, now, now,
                 is_from_template),
            )
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении черновика: {e}")
        return None


def update_draft(db_path, draft_id, status=None, description=None, date=None,
                 time=None, participant_limit=None, bot_message_id=None):
    """
    Обновляет черновик мероприятия в базе данных.
    :param db_path: Путь к базе данных.
    :param draft_id: ID черновика.
    :param status: Статус черновика.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия.
    :param time: Время мероприятия.
    :param participant_limit: Лимит участников.
    :param bot_message_id: ID сообщения бота.
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
            if bot_message_id is not None:
                updates.append("bot_message_id = ?")
                params.append(bot_message_id)

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
    """Возвращает черновик как словарь со ВСЕМИ полями"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)  # Преобразуем Row в dict со всеми полями
        return None

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
            "SELECT * FROM drafts WHERE creator_id = ? AND chat_id = ? ORDER BY id DESC LIMIT 1",
            (creator_id, chat_id)
        )
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'creator_id': row['creator_id'],
                'chat_id': row['chat_id'],
                'status': row['status'],
                'description': row['description'],
                'date': row['date'],
                'time': row['time'],
                'participant_limit': row['participant_limit'],
                'is_from_template': bool(row['is_from_template']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        return None

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

def log_draft_contents(draft):
    """Логирует содержимое черновика для отладки"""
    if draft:
        draft_dict = dict(draft)
        logger.info("Содержимое черновика:")
        for key, value in draft_dict.items():
            logger.info(f"{key}: {value}")
    else:
        logger.info("Черновик не найден")