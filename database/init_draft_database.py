import sqlite3

def init_drafts_db(db_path):
    """Инициализирует базу данных для черновиков."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message_id INTEGER,
            bot_message_id INTEGER,
            status TEXT NOT NULL,
            description TEXT,
            date TEXT,
            time TEXT,
            participant_limit INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()