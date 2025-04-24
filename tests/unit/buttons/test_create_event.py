import asyncio
import sqlite3
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from telegram import Update, CallbackQuery, User, Message, Chat, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from src.buttons.create_event_button import create_event_button
from src.logger import logger


@pytest.mark.asyncio
async def test_create_event_button(mocker):
    # Мокируем CallbackQuery и его атрибуты
    mock_query = MagicMock(spec=CallbackQuery)
    mock_query.message = MagicMock()
    mock_query.message.message_id = 789  # Устанавливаем нужное сообщение

    # Мокируем update и добавляем callback_query
    mock_update = MagicMock()
    mock_update.callback_query = mock_query  # Добавляем callback_query к mock_update

    # Мокируем context (например, для bot_data)
    mock_context = MagicMock()
    mock_context.bot_data = {
        "drafts_db_path": "mock/path/to/drafts.db"
    }

    # Мокируем edit_message_text, чтобы не отправлять запрос в Telegram
    mock_edit = mocker.patch("telegram.CallbackQuery.edit_message_text", new_callable=AsyncMock)

    # Мокируем часть, которая может вызывать исключение
    mocker.patch("your_module.some_function_that_raises_error", side_effect=Exception("Test exception"))

    # Вызов функции с mock_update и mock_context
    await create_event_button(mock_update, mock_context)

    # Проверяем, что метод был вызван
    mock_edit.assert_called_once_with("⚠️ Произошла непредвиденная ошибка")


"""
def test_event_creation(test_databases):
    main_db = test_databases["main_db"]
    drafts_db = test_databases["drafts_db"]

    # Проверяем основную БД
    with sqlite3.connect(main_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        assert len(events) == 1
        assert events[0][1] == "Test Event"  # description

    # Проверяем БД черновиков
    with sqlite3.connect(drafts_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM drafts")
        drafts = cursor.fetchall()
        assert len(drafts) == 1
        assert drafts[0][2] == 456  # chat_id
"""