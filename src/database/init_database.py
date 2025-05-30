import sqlite3

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
            chat_id INTEGER,
            message_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
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
            job_type TEXT,
            chat_id INTEGER NOT NULL,
            execute_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
        )
        """
    )
    #Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        username TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    #Таблица для шаблонов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        date TEXT,
        time TEXT NOT NULL,
        participant_limit INTEGER,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)


    # Создание индексов
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_event_id ON participants (event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reserve_event_id ON reserve (event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_declined_event_id ON declined (event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_templates_user_id ON event_templates (user_id)")

    conn.commit()
    conn.close()