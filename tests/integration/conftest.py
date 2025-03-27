import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, Message, Chat

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        try:
            yield session  # Теперь возвращаем именно сессию
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    await engine.dispose()

@pytest.fixture
def mock_update():
    mock_message = MagicMock(spec=Message)
    mock_message.chat_id = 12345
    mock_message.reply_text = AsyncMock()

    mock_chat = MagicMock(spec=Chat)
    mock_message.chat = mock_chat

    mock_update = MagicMock(spec=Update)
    mock_update.message = mock_message

    return mock_update


@pytest.fixture
def mock_context():
    mock_context = MagicMock()
    mock_context.user_data = {}
    return mock_context