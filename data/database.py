import sqlite3
import json
import os
import logging

# Включаем логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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

def init_db(db_path):
    """Инициализирует базу данных и создает таблицы, если они не существуют."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Таблица мероприятий
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            participant_limit INTEGER,
            creator_id INTEGER NOT NULL,
            message_id INTEGER
        )
        """
    )

    # Таблица участников
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
        )
        """
    )

    # Таблица резерва
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reserve (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
        )
        """
    )

    # Таблица отказавшихся
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS declined (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
        )
        """
    )

    # Таблица для хранения запланированных задач
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            job_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            execute_at TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
        )
        """
    )

    # Создание индексов
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_event_id ON participants (event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reserve_event_id ON reserve (event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_declined_event_id ON declined (event_id)")

    conn.commit()
    conn.close()

    # Применяем миграции
    # migrate_db(db_path)

def migrate_db(db_path):
    """
    Добавляет столбец `message_id` в таблицу `events`, если он отсутствует.
    :param db_path: Путь к файлу базы данных.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Проверяем, существует ли столбец `message_id`
    cursor.execute("PRAGMA table_info(events)")
    columns = [column[1] for column in cursor.fetchall()]
    if "message_id" not in columns:
        # Добавляем столбец `message_id`
        cursor.execute("ALTER TABLE events ADD COLUMN message_id INTEGER")
        conn.commit()

    conn.close()

def add_event(db_path, description, date, time, limit, creator_id, message_id=None):
    """
    Добавляет мероприятие в базу данных.
    :param db_path: Путь к базе данных.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия в формате "дд-мм-гггг".
    :param time: Время мероприятия в формате "чч:мм".
    :param limit: Лимит участников (0 означает неограниченный лимит).
    :param creator_id: ID создателя мероприятия.
    :param message_id: ID сообщения в Telegram (опционально).
    :return: ID добавленного мероприятия.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Логируем данные перед выполнением запроса
        logger.info(
            f"Данные для добавления мероприятия: "
            f"description={description}, date={date}, time={time}, "
            f"limit={limit}, creator_id={creator_id}, message_id={message_id}"
        )

        # Выполняем SQL-запрос для добавления мероприятия
        cursor.execute(
            """
            INSERT INTO events (description, date, time, participant_limit, creator_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (description, date, time, limit, creator_id, message_id),
        )

        event_id = cursor.lastrowid  # Получаем ID добавленного мероприятия
        conn.commit()
        logger.info(f"Мероприятие добавлено с ID: {event_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении мероприятия в базу данных: {e}")
        event_id = None
    finally:
        conn.close()
    return event_id

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
            "limit": event["participant_limit"],
            "creator_id": event["creator_id"],
            "message_id": event["message_id"],
            "participants": participants,
            "reserve": reserve,
            "declined": declined,
        }

        return event_data

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

def add_scheduled_job(db_path, event_id, job_id, chat_id, execute_at):
    """
    Сохраняет информацию о запланированной задаче в базу данных.
    :param db_path: Путь к базе данных.
    :param event_id: ID мероприятия.
    :param job_id: ID задачи в JobQueue.
    :param chat_id: ID чата.
    :param execute_at: Время выполнения задачи (в формате ISO).
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO scheduled_jobs (event_id, job_id, chat_id, execute_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, job_id, chat_id, execute_at),
        )
        conn.commit()


def delete_event(db_path: str, event_id: int):
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()