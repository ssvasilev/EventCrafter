import sqlite3

from src.logger.logger import logger


class SessionManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.active_sessions = {}
        self._init_db()

    def restore_sessions(self, context):
        """Восстанавливает все сессии и отправляет пользователям приглашения продолжить"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.session_key, d.status, d.chat_id, d.creator_id, 
                       d.bot_message_id, d.description, d.date, d.time
                FROM sessions s
                JOIN drafts d ON s.draft_id = d.id
                WHERE d.status != 'DONE'
            """)

            for row in cursor.fetchall():
                session_key, status, chat_id, creator_id, bot_message_id, desc, date, time = row

                # Восстанавливаем сессию в памяти
                self.active_sessions[session_key] = {
                    'chat_id': chat_id,
                    'creator_id': creator_id,
                    'bot_message_id': bot_message_id,
                    'status': status
                }

    def _get_restore_prompt(self, status, desc, date, time):
        prompts = {
            "AWAIT_DESCRIPTION": "Продолжаем создание мероприятия. Введите описание:",
            "AWAIT_DATE": f"Продолжаем создание мероприятия.\nОписание: {desc}\nВведите дату (ДД.ММ.ГГГГ):",
            "AWAIT_TIME": f"Продолжаем создание мероприятия.\nДата: {date}\nВведите время (ЧЧ:ММ):",
            "AWAIT_LIMIT": f"Продолжаем создание мероприятия.\nВремя: {time}\nВведите лимит участников:",
            **{f"EDIT_{field}": f"Продолжаем редактирование. Введите новое значение {field}:"
               for field in ["description", "date", "time", "limit"]}
        }
        return prompts.get(status, "Продолжаем ввод:")