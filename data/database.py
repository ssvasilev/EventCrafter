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
            participants_limit INTEGER,
            participants TEXT,
            reserve TEXT,
            message_id INTEGER  -- Добавьте этот столбец, если его нет
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

def add_event(db_path, description, date, time, participants_limit, participants=None, reserve=None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (description, date, time, participants_limit, participants, reserve) VALUES (?, ?, ?, ?, ?, ?)",
        (
            description,
            date,
            time,
            participants_limit,
            "\n".join(participants) if participants else "",  # Сохраняем как строку, разделенную \n
            "\n".join(reserve) if reserve else "",             # Сохраняем как строку, разделенную \n
        ),
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id

def get_event(db_path, event_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    conn.close()
    if event:
        return {
            "id": event[0],
            "description": event[1],
            "date": event[2],
            "time": event[3],
            "participants_limit": event[4],
            "participants": event[5].split("\n") if event[5] else [],  # Преобразуем строку в список
            "reserve": event[6].split("\n") if event[6] else [],      # Преобразуем строку в список
            "message_id": event[7],
        }
    return None

def update_event(db_path, event_id, participants, reserve):
    """
    Обновляет списки участников и резерва мероприятия.
    :param db_path: Путь к файлу базы данных.
    :param event_id: ID мероприятия.
    :param participants: Список участников.
    :param reserve: Список резерва.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET participants = ?, reserve = ? WHERE id = ?",
        (
            "\n".join(participants) if participants else "",  # Сохраняем как строку, разделенную \n
            "\n".join(reserve) if reserve else "",            # Сохраняем как строку, разделенную \n
            event_id,
        ),
    )
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