# database.py
import sqlite3
import json


# Подключение к базе данных (файл events.db будет создан автоматически)
def get_db_connection():
    conn = sqlite3.connect("events.db")
    conn.row_factory = sqlite3.Row  # Для доступа к данным по имени столбца
    return conn


# Инициализация базы данных
def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            participant_limit INTEGER NOT NULL,
            participants TEXT NOT NULL,
            reserve TEXT NOT NULL,
            message_id INTEGER
        )
    """)
    conn.commit()
    conn.close()


# Добавление мероприятия
def add_event(description, date, time, limit):
    conn = get_db_connection()
    cursor = conn.execute(
        """
        INSERT INTO events (description, date, time, participant_limit, participants, reserve)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (description, date, time, limit, json.dumps([]), json.dumps([])),
    )
    event_id = cursor.lastrowid  # Получаем ID добавленного мероприятия
    conn.commit()
    conn.close()
    return event_id  # Возвращаем ID


# Получение мероприятия по ID
def get_event(event_id):
    conn = get_db_connection()
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
            "message_id": event["message_id"],  # Добавляем message_id
        }
    return None


# Обновление мероприятия
def update_event(event_id, participants, reserve):
    conn = get_db_connection()
    conn.execute("""
        UPDATE events
        SET participants = ?, reserve = ?
        WHERE id = ?
    """, (json.dumps(participants), json.dumps(reserve), event_id))
    conn.commit()
    conn.close()


# Получение всех мероприятий
def get_all_events():
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events").fetchall()
    conn.close()
    return [
        {
            "id": event["id"],
            "description": event["description"],
            "date": event["date"],
            "time": event["time"],
            "limit": event["participant_limit"],
            "participants": json.loads(event["participants"]),
            "reserve": json.loads(event["reserve"]),
        }
        for event in events
    ]


# Обновление сообщения
def update_message_id(event_id, message_id):
    conn = get_db_connection()
    conn.execute("UPDATE events SET message_id = ? WHERE id = ?", (message_id, event_id))
    conn.commit()
    conn.close()
