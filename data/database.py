import sqlite3
import json
import os

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
    """
    Инициализирует базу данных и применяет миграции.
    :param db_path: Путь к файлу базы данных.
    """
    conn = get_db_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            participant_limit INTEGER,
            participants TEXT NOT NULL,
            reserve TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    # Применяем миграции
    migrate_db(db_path)

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

def add_event(db_path: str, description: str, date: str, time: str, limit: int = None) -> int:
    """
    Добавляет новое мероприятие в базу данных.
    :param db_path: Путь к базе данных.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия.
    :param time: Время мероприятия.
    :param limit: Лимит участников (опционально).
    :return: ID добавленного мероприятия.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Убедимся, что participants и reserve инициализированы как "[]"
    cursor.execute(
        "INSERT INTO events (description, date, time, limit, participants, reserve) VALUES (?, ?, ?, ?, ?, ?)",
        (description, date, time, limit, "[]", "[]")
    )

    event_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return event_id

def get_event(db_path: str, event_id: int) -> dict:
    """
    Получает данные мероприятия по его ID.
    :param db_path: Путь к базе данных.
    :param event_id: ID мероприятия.
    :return: Словарь с данными мероприятия.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()

    conn.close()

    if not event:
        return None

    # Преобразуем данные из базы в словарь
    event_dict = {
        "id": event[0],
        "description": event[1],
        "date": event[2],
        "time": event[3],
        "limit": event[4],
        "participants": json.loads(event[5]) if event[5] else [],  # Проверка на пустую строку
        "reserve": json.loads(event[6]) if event[6] else [],      # Проверка на пустую строку
        "message_id": event[7]
    }

    return event_dict

def update_event(db_path: str, event_id: int, participants: list, reserve: list, description: str = None, date: str = None, time: str = None, limit: int = None):
    """
    Обновляет данные мероприятия в базе данных.
    :param db_path: Путь к базе данных.
    :param event_id: ID мероприятия.
    :param participants: Список участников.
    :param reserve: Список резерва.
    :param description: Новое описание (опционально).
    :param date: Новая дата (опционально).
    :param time: Новое время (опционально).
    :param limit: Новый лимит участников (опционально).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Преобразуем списки в JSON-строки
    participants_json = json.dumps(participants)
    reserve_json = json.dumps(reserve)

    # Формируем SQL-запрос для обновления данных
    query = """
    UPDATE events
    SET participants = ?,
        reserve = ?,
        description = COALESCE(?, description),
        date = COALESCE(?, date),
        time = COALESCE(?, time),
        "limit" = COALESCE(?, "limit")
    WHERE id = ?
    """
    cursor.execute(query, (
        participants_json,
        reserve_json,
        description,
        date,
        time,
        limit,
        event_id
    ))

    conn.commit()
    conn.close()

def update_message_id(db_path, event_id, message_id):
    """
    Обновляет message_id мероприятия.
    :param db_path: Путь к файлу базы данных.
    :param event_id: ID мероприятия.
    :param message_id: ID сообщения в Telegram.
    """
    conn = get_db_connection(db_path)
    conn.execute("""
        UPDATE events
        SET message_id = ?
        WHERE id = ?
    """, (message_id, event_id))
    conn.commit()
    conn.close()

def update_event_description(db_path: str, event_id: int, new_description: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET description = ? WHERE id = ?", (new_description, event_id))
    conn.commit()
    conn.close()

def delete_event(db_path: str, event_id: int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()