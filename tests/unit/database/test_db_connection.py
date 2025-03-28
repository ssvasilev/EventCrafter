import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text  # Добавляем импорт text

@pytest.mark.asyncio
async def test_db_connection(db_session: AsyncSession):
    """Тест проверяет работоспособность подключения к БД"""
    # Явно используем text() для SQL-выражений
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1