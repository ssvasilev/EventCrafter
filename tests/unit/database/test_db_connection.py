import sqlite3

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text  # Добавляем импорт text

def test_db_connection(test_databases):
    """Тест проверяет работоспособность подключения к БД"""
    with sqlite3.connect(test_databases["main_db"]) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]
        assert result == 1