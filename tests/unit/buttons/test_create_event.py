import asyncio
import sqlite3
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from telegram import Update, CallbackQuery, User, Message, Chat, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext

from src.buttons.create_event_button import create_event_button
from src.logger import logger


async def test_create_event_flow(app, mock_callback_query, mock_context, test_databases, draft_operations):
    drafts_db_path = test_databases["drafts_db"]

    # Очистка таблицы drafts перед тестом
    with sqlite3.connect(drafts_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM drafts")  # Очистить таблицу drafts
        conn.commit()

    # Привязываем мок бота к сообщению вручную
    mock_callback_query.message.set_bot(app.bot)

    # Формируем update и context
    update = Update(update_id=1, callback_query=mock_callback_query)
    context = mock_context
    context.bot_data["drafts_db_path"] = drafts_db_path

    # Меняем query.data, чтобы соответствовало поведению create_event_button
    mock_callback_query.data = "create_event"

    # Логируем вызов функции create_event_button
    logger.info("Вызов функции create_event_button...")

    # Вызываем обрабатываемую функцию
    await create_event_button(update, context)

    # Логируем состояние базы данных после вызова
    with sqlite3.connect(drafts_db_path) as conn:
        drafts = conn.execute("SELECT * FROM drafts").fetchall()
        logger.info(f"Черновики в базе данных после выполнения функции: {drafts}")

        # Проверяем, что черновик был добавлен
        assert len(drafts) == 1, f"Ожидалось 1 черновик, но найдено {len(drafts)}"
