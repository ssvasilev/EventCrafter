from telegram import User
from html import escape


class UserNamingService:
    @staticmethod
    def get_display_name(user: User) -> str:
        """Для новых записей - унифицированный формат"""
        name = user.first_name or 'Без имени'
        if user.username:
            return f"{escape(name)} (@{user.username})"
        return f"{escape(name)} (ID: {user.id})"

    @staticmethod
    def normalize_existing_name(existing_name: str) -> str:
        """Исправляет старые записи в БД"""
        if not existing_name:
            return "Удалённый пользователь"

        # Удаляем дублирование (@username)
        if ') @' in existing_name:
            parts = existing_name.split(') @')
            return f"{parts[0]})"

        # Удаляем лишние ID если есть username
        if '@' in existing_name and '(ID:' in existing_name:
            parts = existing_name.split(' (ID:')
            return parts[0]

        return existing_name