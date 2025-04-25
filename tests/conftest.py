import pytest
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from telegram import User, Chat, Message, CallbackQuery, Update
from telegram.ext import CallbackContext, Application, ContextTypes

from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.logger import logger

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()

@pytest.fixture
def app():
    application = Application.builder().token("FAKE-TOKEN").build()
    return application

@pytest.fixture(scope="session")
def temp_dir(tmp_path_factory):
    """Фикстура для временной директории"""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture
def test_databases(temp_dir):

    """
    Фикстура создает и инициализирует обе тестовые базы данных:
    - Основную БД (events, participants и др.)
    - БД черновиков (drafts)
    Возвращает словарь с путями к созданным БД
    """
    # Создаем пути к БД
    main_db_path = temp_dir / "test_main.db"
    drafts_db_path = temp_dir / "test_drafts.db"

    # Инициализируем основную БД
    init_db(main_db_path)

    # Инициализируем БД черновиков
    init_drafts_db(drafts_db_path)

    # Добавляем тестовые данные
    now = datetime.now().isoformat()
    with sqlite3.connect(main_db_path) as conn:
        cursor = conn.cursor()

        # Тестовое мероприятие
        cursor.execute("""
            INSERT INTO events (
                id, description, date, time, participant_limit,
                creator_id, chat_id, message_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1, "Test Event", "2023-01-01", "12:00", 10,
            123, 456, 666, now, now
        ))

        # Тестовый пользователь
        cursor.execute("""
            INSERT INTO users (
                id, first_name, username, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            123, "Test", "test_user", now, now
        ))

        conn.commit()

    return {
        "main_db": str(main_db_path),
        "drafts_db": str(drafts_db_path)
    }


@pytest.fixture
def db_operations(test_databases):
    """Фикстура для операций с основной базой данных"""
    from src.database.db_operations import (
        get_event, add_event, update_event_field,
        add_participant, remove_participant,
        add_to_reserve, remove_from_reserve,
        add_to_declined, remove_from_declined,
        get_participants_count, delete_event
    )

    class DBOps:
        def __init__(self, db_path):
            self.db_path = db_path

        def get_event(self, event_id):
            return get_event(self.db_path, event_id)

        def add_event(self, **kwargs):
            return add_event(self.db_path, **kwargs)

        # Добавьте остальные методы по аналогии

    return DBOps(test_databases["main_db"])


@pytest.fixture
def draft_operations(test_databases):
    """Фикстура для операций с черновиками"""
    from src.database.db_draft_operations import (
        add_draft, update_draft, get_draft, delete_draft
    )

    class DraftOps:
        def __init__(self, db_path):
            self.db_path = db_path

        def add_draft(self, **kwargs):
            logger.info(f"Добавление черновика в фикстуре с параметрами: {kwargs}")
            return add_draft(self.db_path, **kwargs)

        # Добавьте остальные методы по аналогии

    return DraftOps(test_databases["drafts_db"])


def test_draft_operations_fixture(draft_operations, test_databases):
    """Проверяем, что фикстура draft_operations работает правильно"""
    draft_id = draft_operations.add_draft(
        creator_id=123,
        chat_id=456,
        status="TEST",
        is_from_template=False,
        original_message_id=789
    )
    assert draft_id is not None

    with sqlite3.connect(test_databases["drafts_db"]) as conn:
        drafts = conn.execute("SELECT * FROM drafts").fetchall()
        assert len(drafts) == 1

@pytest.fixture(autouse=True)
def clean_databases(test_databases, request):
    """Очищает базы данных после каждого теста."""
    # Очистка перед тестом
    with sqlite3.connect(test_databases["main_db"]) as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM participants")
        conn.execute("DELETE FROM users")
        conn.commit()

    with sqlite3.connect(test_databases["drafts_db"]) as conn:
        conn.execute("DELETE FROM drafts")
        conn.commit()

    def finalizer():
        # Очистка после теста
        with sqlite3.connect(test_databases["main_db"]) as conn:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM participants")
            conn.execute("DELETE FROM users")
            conn.commit()

        with sqlite3.connect(test_databases["drafts_db"]) as conn:
            conn.execute("DELETE FROM drafts")
            conn.commit()

    request.addfinalizer(finalizer)

@pytest.fixture
def mock_bot(test_databases):
    """Фикстура для мока бота"""
    bot = MagicMock()
    bot.bot_data = {
        "db_path": test_databases["main_db"],
        "drafts_db_path": test_databases["drafts_db"]
    }
    bot.answer_callback_query = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_user():
    """Фикстура для тестового пользователя"""
    user = MagicMock(spec=User)
    user.id = 123
    user.first_name = "Test"
    user.is_bot = False
    user.username = "test_user"
    return user


@pytest.fixture
def mock_chat():
    """Фикстура для тестового чата"""
    return Chat(
        id=456,
        type="group",
        title="Test Chat"
    )


@pytest.fixture
def mock_message(mock_chat, mock_user):
    """Фикстура для тестового сообщения"""
    message = MagicMock(spec=Message)
    message.message_id = 789
    message.date = datetime.now()
    message.chat = mock_chat
    message.from_user = mock_user
    message.reply_text = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """Фикстура для тестового callback_query"""
    bot = AsyncMock()  # Используем AsyncMock для асинхронного вызова
    bot.answer_callback_query = AsyncMock()

    query = AsyncMock(spec=CallbackQuery)  # Используем AsyncMock вместо MagicMock
    query.id = "test_query_id"
    query.from_user = mock_user
    query.chat_instance = "test_chat_instance"
    query.data = "test_data"
    query.message = mock_message
    query.edit_message_text = AsyncMock()  # <-- Важно!
    query.answer = AsyncMock()

    # Возвращаем AsyncMock через get_bot
    query.get_bot = MagicMock(return_value=bot)  # Здесь возвращаем AsyncMock
    return query


@pytest.fixture
def mock_update(mock_user):
    def _create_update(data="test_data"):
        message = MagicMock(spec=Message)
        callback_query = MagicMock(spec=CallbackQuery)
        callback_query.id = "test_callback_id"
        callback_query.data = data
        callback_query.from_user = mock_user
        callback_query.message = message
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        callback_query.get_bot = MagicMock(return_value=AsyncMock())

        update = MagicMock(spec=Update)
        update.callback_query = callback_query
        return update
    return _create_update


@pytest.fixture
def mock_context(mock_bot):
    """Фикстура для тестового контекста с доступным user_data"""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = mock_bot
    context.bot_data = {
        "db_path": "test_main.db",
        "drafts_db_path": "test_drafts.db"
    }
    context.user_data = {}  # Здесь можно, т.к. это MagicMock
    return context


@pytest.fixture(autouse=True)
def setup_teardown(test_databases):
    """Фикстура для setup/teardown перед/после каждого теста"""
    # Setup: очищаем таблицы перед каждым тестом
    with sqlite3.connect(test_databases["main_db"]) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM participants")
        cursor.execute("DELETE FROM reserve")
        cursor.execute("DELETE FROM declined")
        conn.commit()

    with sqlite3.connect(test_databases["drafts_db"]) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drafts")
        conn.commit()

    yield

    # Teardown (при необходимости)