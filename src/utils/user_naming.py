from telegram import User
from html import escape


class UserNamingService:
    @staticmethod
    def get_display_name(user: User) -> str:
        """Генерирует корректное отображаемое имя без дублирования"""
        name = user.first_name or 'Без имени'

        if user.username:
            return f"{escape(name)} (@{user.username})"
        return f"{escape(name)} (ID: {user.id})"

    @staticmethod
    def normalize_existing_name(existing_name: str) -> str:
        """Исправляет уже сохранённые имена с дублированием"""
        if not existing_name:
            return "Удалённый пользователь"

        # Убираем дублирование (@username)
        if ') @' in existing_name:
            return existing_name.split(') @')[0] + ')'

        return existing_name