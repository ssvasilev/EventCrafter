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

def add_event(db_path, description, date, time, limit, message_id=None):
    """
    Добавляет новое мероприятие в базу данных.
    :param db_path: Путь к файлу базы данных.
    :param description: Описание мероприятия.
    :param date: Дата мероприятия в формате строки (YYYY-MM-DD).
    :param time: Время мероприятия в формате строки (HH:MM).
    :param limit: Лимит участников. Если None, лимит бесконечный.
    :param message_id: ID сообщения в Telegram (опционально).
    :return: ID созданного мероприятия.
    """
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (description, date, time, participant_limit, participants, reserve, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (description, date, time, limit, json.dumps([]), json.dumps([]), None))
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()
        return event_id
    except sqlite3.Error as e:
        print(f"Ошибка при добавлении мероприятия: {e}")
        return None

def get_event(db_path, event_id):
    """
    Возвращает данные о мероприятии по его ID.
    :param db_path: Путь к файлу базы данных.
    :param event_id: ID мероприятия.
    :return: Словарь с данными о мероприятии или None, если мероприятие не найдено.
    """
    conn = get_db_connection(db_path)
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    if event:
        return {
            "id": event["id"],
            "description": event["description"],
            "date": event["date"],
            "time": event["time"],
            "limit": event["participant_limit"],
            "participants": json.loads(event["participants"]),
            "reserve": json.loads(event["reserve"]),
            "message_id": event["message_id"],  # Новый столбец
        }
    return None

def get_all_events(db_path):
    conn = get_db_connection(db_path)
    events = conn.execute("SELECT * FROM events").fetchall()
    conn.close()
    return [dict(event) for event in events]

def update_event(db_path, event_id, participants, reserve):
    """
    Обновляет списки участников и резерва мероприятия.
    :param db_path: Путь к файлу базы данных.
    :param event_id: ID мероприятия.
    :param participants: Список участников.
    :param reserve: Список резерва.
    """
    conn = get_db_connection(db_path)
    conn.execute("""
        UPDATE events
        SET participants = ?, reserve = ?
        WHERE id = ?
    """, (json.dumps(participants), json.dumps(reserve), event_id))
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
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET description = ? WHERE id = ?", (new_description, event_id))
    conn.commit()
    conn.close()

def update_event_date(db_path: str, event_id: int, new_date: str):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET date = ? WHERE id = ?", (new_date, event_id))
    conn.commit()
    conn.close()

def update_event_time(db_path: str, event_id: int, new_time: str):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET time = ? WHERE id = ?", (new_time, event_id))
    conn.commit()
    conn.close()

def update_event_participant_limit(db_path: str, event_id: int, new_limit: int):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE events SET participant_limit = ? WHERE id = ?", (new_limit, event_id))
    conn.commit()
    conn.close()

def delete_event(db_path: str, event_id: int):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()