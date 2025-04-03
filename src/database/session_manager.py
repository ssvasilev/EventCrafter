import sqlite3
from datetime import datetime, timedelta
from src.logger.logger import logger

class SessionManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    draft_id INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)
            conn.commit()

    def create_session(self, user_id, chat_id, draft_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?)",
                (user_id, chat_id, draft_id, (datetime.now() + timedelta(hours=1)).isoformat())
            )
            conn.commit()

    def get_active_session(self, user_id, chat_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT draft_id FROM sessions 
                WHERE user_id = ? AND chat_id = ? AND expires_at > ?
            """, (user_id, chat_id, datetime.now().isoformat()))
            result = cursor.fetchone()
            return result[0] if result else None

    def clear_session(self, user_id: int, chat_id: int):
        """Безопасная очистка сессии"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM sessions WHERE user_id = ? AND chat_id = ?",
                    (user_id, chat_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка очистки сессии: {str(e)}")