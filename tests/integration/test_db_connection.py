import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_db_connection(db_session: AsyncSession):
    """Тест проверяет работоспособность подключения к БД"""
    result = await db_session.execute("SELECT 1")
    assert result.scalar() == 1