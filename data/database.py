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
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (description, date, time, participant_limit, participants, reserve, message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (description, date, time, limit, json.dumps([]), json.dumps([]), None))
    conn.commit()
    event_id = cursor.lastrowid  # Получаем ID созданного мероприятия
    conn.close()
    return event_id

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

def update_event(db_path, event_id, participants=None, reserve=None, description=None, date=None, time=None, limit=None):
    """
    Обновляет данные мероприятия по его ID.
    :param db_path: Путь к файлу базы данных.
    :param event_id: ID мероприятия.
    :param participants: Список участников (опционально).
    :param reserve: Список резерва (опционально).
    :param description: Новое описание (опционально).
    :param date: Новая дата (опционально).
    :param time: Новое время (опционально).
    :param limit: Новый лимит участников (опционально).
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Проверяем, существует ли мероприятие
    event = cursor.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        conn.close()
        raise ValueError(f"Мероприятие с ID {event_id} не найдено.")

    # Формируем запрос на обновление
    updates = []
    params = []

    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if date is not None:
        updates.append("date = ?")
        params.append(date)
    if time is not None:
        updates.append("time = ?")
        params.append(time)
    if limit is not None:
        updates.append('"limit" = ?')  # Используем кавычки для зарезервированного слова
        params.append(limit)
    if participants is not None:
        updates.append("participants = ?")
        params.append(json.dumps(participants))
    if reserve is not None:
        updates.append("reserve = ?")
        params.append(json.dumps(reserve))

    # Если есть что обновлять
    if updates:
        query = f"UPDATE events SET {', '.join(updates)} WHERE id = ?"
        params.append(event_id)
        cursor.execute(query, params)
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