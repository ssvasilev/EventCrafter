import sqlite3

from eventcrafterbot import DB_PATH
from logger.logger import logger

def get_db_connection(db_path: str = DB_PATH):
    """
    Возвращает соединение с базой данных.
    :param db_path: Путь к файлу базы данных.
    :return: Соединение с базой данных.
    """
    return sqlite3.connect(db_path)


def add_event(db_path, description, date, time, limit, creator_id, chat_id, message_id=None):
    """
    Добавляет мероприятие в базу данных.
    :param db_path: Путь к базе данных.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия в формате "дд-мм-гггг".
    :param time: Время мероприятия в формате "чч:мм".
    :param limit: Лимит участников (0 означает неограниченный лимит).
    :param creator_id: ID создателя мероприятия.
    :param chat_id: ID чата, в котором создано мероприятие.
    :param message_id: ID сообщения в Telegram (опционально).
    :return: ID добавленного мероприятия.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (description, date, time, participant_limit, creator_id, chat_id, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (description, date, time, limit, creator_id, chat_id, message_id),
            )
            event_id = cursor.lastrowid  # Получаем ID добавленного мероприятия
            conn.commit()
            logger.info(f"Мероприятие добавлено с ID: {event_id}")
            return event_id
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении мероприятия в базу данных: {e}")
        return None

def get_event(db_path, event_id):
    """Возвращает информацию о мероприятии по его ID."""
    with get_db_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Получаем основную информацию о мероприятии
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()

        if not event:
            return None

        # Получаем участников
        cursor.execute("SELECT user_id, user_name FROM participants WHERE event_id = ?", (event_id,))
        participants = [{"user_id": row["user_id"], "name": row["user_name"]} for row in cursor.fetchall()]

        # Получаем резерв
        cursor.execute("SELECT user_id, user_name FROM reserve WHERE event_id = ?", (event_id,))
        reserve = [{"user_id": row["user_id"], "name": row["user_name"]} for row in cursor.fetchall()]

        # Получаем отказавшихся
        cursor.execute("SELECT user_id, user_name FROM declined WHERE event_id = ?", (event_id,))
        declined = [{"user_id": row["user_id"], "name": row["user_name"]} for row in cursor.fetchall()]

        event_data = {
            "id": event["id"],
            "description": event["description"],
            "date": event["date"],
            "time": event["time"],
            "participant_limit": event["participant_limit"],  # Переименовано с "limit" на "participant_limit"
            "creator_id": event["creator_id"],
            "chat_id": event["chat_id"],  # Добавлено поле chat_id
            "message_id": event["message_id"],
            "participants": participants,
            "reserve": reserve,
            "declined": declined,
        }

        return event_data

def get_events_by_participant(db_path, user_id):
    """
    Возвращает список мероприятий, в которых участвует пользователь.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT e.id, e.description, e.date, e.time, e.chat_id, e.message_id
            FROM events e
            JOIN participants p ON e.id = p.event_id
            WHERE p.user_id = ?
            """,
            (user_id,),
        )
        return cursor.fetchall()

def get_all_events(db_path):
    conn = get_db_connection(db_path)
    events = conn.execute("SELECT * FROM events").fetchall()
    conn.close()
    return [dict(event) for event in events]

#Получение одного из списков
def get_participants(db_path, event_id):
    """Возвращает список участников мероприятия."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, user_name FROM participants WHERE event_id = ?", (event_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_reserve(db_path, event_id):
    """Возвращает список резерва мероприятия."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, user_name FROM reserve WHERE event_id = ?", (event_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_declined(db_path, event_id):
    """Возвращает список отказавшихся."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, user_name FROM declined WHERE event_id = ?", (event_id,))
        return [dict(row) for row in cursor.fetchall()]

def is_user_in_participants(db_path, event_id, user_id):
    """Проверяет, есть ли пользователь в списке участников."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM participants WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        return cursor.fetchone() is not None

def is_user_in_reserve(db_path, event_id, user_id):
    """Проверяет, есть ли пользователь в резерве."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM reserve WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        return cursor.fetchone() is not None

def is_user_in_declined(db_path, event_id, user_id):
    """Проверяет, есть ли пользователь в списке отказавшихся."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM declined WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        return cursor.fetchone() is not None

#Добавление в один из трёх списков
def add_participant(db_path, event_id, user_id, user_name):
    """Добавляет участника в таблицу participants."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO participants (event_id, user_id, user_name) VALUES (?, ?, ?)",
            (event_id, user_id, user_name),
        )
        conn.commit()

def add_to_reserve(db_path, event_id, user_id, user_name):
    """Добавляет пользователя в резерв."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reserve (event_id, user_id, user_name) VALUES (?, ?, ?)",
            (event_id, user_id, user_name),
        )
        conn.commit()

def add_to_declined(db_path, event_id, user_id, user_name):
    """Добавляет пользователя в список отказавшихся."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO declined (event_id, user_id, user_name) VALUES (?, ?, ?)",
            (event_id, user_id, user_name),
        )
        conn.commit()

#Удаление из списков
def remove_participant(db_path, event_id, user_id):
    """Удаляет участника из таблицы participants."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM participants WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()

def remove_from_reserve(db_path, event_id, user_id):
    """Удаляет пользователя из резерва."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reserve WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()

def remove_from_declined(db_path, event_id, user_id):
    """Удаляет пользователя из списка отказавшихся."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM declined WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()

#Подсчёт количества участников
def get_participants_count(db_path, event_id):
    """Возвращает количество участников мероприятия."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM participants WHERE event_id = ?", (event_id,))
        return cursor.fetchone()[0]


#Обновление поля в мероприятии
def update_event_field(db_path: str, event_id: int, field: str, value: str | int | None):
    """
    Универсальная функция для обновления любого поля в таблице events.
    :param db_path: Путь к базе данных.
    :param event_id: ID мероприятия.
    :param field: Название поля (например, "description", "date", "time", "participant_limit").
    :param value: Новое значение поля.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE events SET {field} = ? WHERE id = ?", (value, event_id))
        conn.commit()

def update_event(db_path, event_id, participants, reserve, declined):
    """
    Обновляет списки участников, резерва и отказавшихся.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Удаляем старые записи
        cursor.execute("DELETE FROM participants WHERE event_id = ?", (event_id,))
        cursor.execute("DELETE FROM reserve WHERE event_id = ?", (event_id,))
        cursor.execute("DELETE FROM declined WHERE event_id = ?", (event_id,))

        # Добавляем новых участников
        for participant in participants:
            cursor.execute(
                "INSERT INTO participants (event_id, user_id, user_name) VALUES (?, ?, ?)",
                (event_id, participant["user_id"], participant["name"]),
            )

        # Добавляем новый резерв
        for user in reserve:
            cursor.execute(
                "INSERT INTO reserve (event_id, user_id, user_name) VALUES (?, ?, ?)",
                (event_id, user["user_id"], user["name"]),
            )

        # Добавляем новых отказавшихся
        for user in declined:
            cursor.execute(
                "INSERT INTO declined (event_id, user_id, user_name) VALUES (?, ?, ?)",
                (event_id, user["user_id"], user["name"]),
            )

        conn.commit()

def update_message_id(db_path, event_id, message_id):
    """
    Обновляет message_id мероприятия.
    :param db_path: Путь к файлу базы данных.
    :param event_id: ID мероприятия.
    :param message_id: ID сообщения в Telegram.
    """
    try:
        conn = get_db_connection(db_path)
        conn.execute("""
            UPDATE events
            SET message_id = ?
            WHERE id = ?
        """, (message_id, event_id))
        conn.commit()
        logger.info(f"message_id={message_id} обновлен для мероприятия с ID={event_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении message_id: {e}")
    finally:
        conn.close()

def add_scheduled_job(db_path, event_id, job_id, chat_id, execute_at, job_type=None):
    """
    Сохраняет информацию о запланированной задаче в базу данных.
    :param db_path: Путь к базе данных.
    :param event_id: ID мероприятия.
    :param job_id: ID задачи в JobQueue.
    :param chat_id: ID чата.
    :param execute_at: Время выполнения задачи (в формате ISO).
    :param job_type: Тип задачи (например, "notification_day", "notification_minutes", "unpin_delete").
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO scheduled_jobs (event_id, job_id, chat_id, execute_at, job_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, job_id, chat_id, execute_at, job_type),
        )
        conn.commit()
def get_scheduled_job_id(db_path: str, event_id: int) -> str:
    """Возвращает job_id запланированной задачи для указанного мероприятия."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT job_id FROM scheduled_jobs WHERE event_id = ?", (event_id,))
        result = cursor.fetchone()
        return result["job_id"] if result else None

def delete_scheduled_job(db_path: str, event_id: int, job_id: str = None, job_type: str = None):
    """
    Удаляет задачу из базы данных по event_id.
    Если указан job_id, удаляет только задачу с этим ID.
    Если указан job_type, удаляет только задачи этого типа.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if job_id:
            cursor.execute("DELETE FROM scheduled_jobs WHERE event_id = ? AND job_id = ?", (event_id, job_id))
        elif job_type:
            cursor.execute("DELETE FROM scheduled_jobs WHERE event_id = ? AND job_type = ?", (event_id, job_type))
        else:
            cursor.execute("DELETE FROM scheduled_jobs WHERE event_id = ?", (event_id,))
        conn.commit()
        logger.info(f"Задачи для мероприятия {event_id} удалены из базы данных.")

def delete_event(db_path: str, event_id: int):
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()