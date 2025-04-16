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

            # Отправляем параметры в лог
            logger.info(f"Добавление черновика с параметрами: bot_message_id={bot_message_id}, original_message_id={original_message_id}")

            # Выполняем запрос
            cursor.execute(
                """
                INSERT INTO drafts (
                    creator_id, chat_id, status, description, 
                    date, time, participant_limit, event_id,
                    original_message_id, is_from_template, bot_message_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    creator_id, chat_id, status, description,
                    date, time, participant_limit, event_id,
                    original_message_id, is_from_template, bot_message_id,
                    now, now
                ),
            )
            draft_id = cursor.lastrowid
            conn.commit()

            # Проверяем, что данные сохранились правильно
            cursor.execute(
                "SELECT bot_message_id, original_message_id FROM drafts WHERE id = ?",
                (draft_id,)
            )
            row = cursor.fetchone()
            saved_bot_msg_id, saved_orig_msg_id = row[0], row[1]

            logger.info(
                f"Создан черновик ID {draft_id}. "
                f"bot_message_id в БД: {saved_bot_msg_id} (ожидалось: {bot_message_id}), "
                f"original_message_id в БД: {saved_orig_msg_id} (ожидалось: {original_message_id})"
            )

            if saved_bot_msg_id != bot_message_id:
                logger.error(
                    "РАЗЛИЧИЕ В ДАННЫХ: bot_message_id не совпадает! "
                    f"Ожидалось: {bot_message_id}, получено: {saved_bot_msg_id}"
                )

                # Проверяем структуру таблицы
                cursor.execute("PRAGMA table_info(drafts)")
                columns = cursor.fetchall()
                logger.info("Структура таблицы drafts:")
                for col in columns:
                    logger.info(f"  {col[1]} ({col[2]})")

            return draft_id

    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении черновика: {e}", exc_info=True)
        return None


def update_draft(db_path, draft_id, **kwargs):
    """
    Обновляет черновик мероприятия в базе данных.
    :param db_path: Путь к базе данных
    :param draft_id: ID черновика
    :kwargs: Поля для обновления (status, description, date, time, participant_limit, bot_message_id)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Формируем запрос динамически
            updates = []
            params = []

            for field, value in kwargs.items():
                if value is not None:
                    updates.append(f"{field} = ?")
                    params.append(value)

            if not updates:
                logger.warning("Нет полей для обновления")
                return False

            updates.append("updated_at = ?")
            params.append(now)
            params.append(draft_id)

            query = f"UPDATE drafts SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

            # Проверяем обновление
            if 'bot_message_id' in kwargs:
                cursor.execute("SELECT bot_message_id FROM drafts WHERE id = ?", (draft_id,))
                updated_value = cursor.fetchone()[0]
                if updated_value != kwargs['bot_message_id']:
                    logger.error(f"Ошибка обновления bot_message_id (ожидалось: {kwargs['bot_message_id']}, получено: {updated_value})")

            logger.info(f"Черновик {draft_id} обновлен: {kwargs}")
            return True

    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении черновика {draft_id}: {e}")
        return False

def get_draft(db_path, draft_id):
    """Возвращает черновик как словарь со ВСЕМИ полями"""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Проверяем существование столбца bot_message_id
            cursor.execute("PRAGMA table_info(drafts)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'bot_message_id' not in columns:
                logger.error("В таблице drafts отсутствует столбец bot_message_id!")
                return None

            cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
            row = cursor.fetchone()

            if not row:
                logger.warning(f"Черновик {draft_id} не найден")
                return None

            draft_data = dict(row)
            logger.debug(f"Получен черновик {draft_id}: bot_message_id={draft_data.get('bot_message_id')}")
            return draft_data

    except sqlite3.Error as e:
        logger.error(f"Ошибка получения черновика {draft_id}: {e}")
        return None

def get_user_chat_draft(db_path, creator_id, chat_id):
    """
    Возвращает активный черновик для конкретного пользователя и чата со всеми полями.
    :param db_path: Путь к базе данных.
    :param creator_id: ID создателя.
    :param chat_id: ID чата.
    :return: Полный словарь с данными черновика или None, если не найден.
    """
    with get_db_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row  # Для доступа к полям по имени
        cursor = conn.cursor()

        # Получаем последний активный черновик
        cursor.execute(
            """SELECT * FROM drafts 
            WHERE creator_id = ? AND chat_id = ? 
            ORDER BY id DESC LIMIT 1""",
            (creator_id, chat_id)
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Собираем все поля черновика в словарь
        draft = {
            'id': row['id'],
            'creator_id': row['creator_id'],
            'chat_id': row['chat_id'],
            'status': row['status'],
            'description': row['description'],
            'date': row['date'],
            'time': row['time'],
            'participant_limit': row['participant_limit'],
            'event_id': row['event_id'] if 'event_id' in row.keys() else None,
            'original_message_id': row['original_message_id'] if 'original_message_id' in row.keys() else None,
            'bot_message_id': row['bot_message_id'] if 'bot_message_id' in row.keys() else None,
            'is_from_template': bool(row['is_from_template']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }

        # Логирование для отладки
        logger.debug(f"Получен черновик: {draft}")

        return draft
"""
def get_user_draft(db_path, creator_id):

    #Возвращает активный черновик пользователя.
    #:param db_path: Путь к базе данных.
    #:param creator_id: ID создателя черновика.
    #:return: Черновик мероприятия.

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts WHERE creator_id = ? AND status != 'DONE'", (creator_id,))
        return cursor.fetchone()
"""
def get_user_drafts(db_path: str, user_id: int):
    """Возвращает все черновики пользователя"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE creator_id = ? AND status != 'DONE'",
            (user_id,)
        )
        return cursor.fetchall()
"""
def get_draft_by_bot_message(db_path: str, bot_message_id: int):
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE bot_message_id = ?",
            (bot_message_id,)
        )
        return cursor.fetchone()
"""
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

"""
def log_draft_contents(draft):
    if draft:
        draft_dict = dict(draft)
        logger.info("Содержимое черновика:")
        for key, value in draft_dict.items():
            logger.info(f"{key}: {value}")
    else:
        logger.info("Черновик не найден")
"""