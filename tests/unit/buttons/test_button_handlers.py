import logging
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY, PropertyMock
from telegram import Update, CallbackQuery, User, Message, Chat, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import sqlite3
from src.buttons.button_handlers import (
    button_handler,
    handle_join,
    handle_leave,
    handle_edit_event,
    handle_edit_field,
    handle_confirm_delete,
    handle_delete_event,
    handle_cancel_delete,
    update_event_message
)

@pytest.mark.asyncio
async def test_button_handler_simple_actions(mock_update, mock_context):
    update = mock_update()  # Важно: вызываем mock_update, чтобы получить объект update

    # Создаем mock-пользователя с нужным ID
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    mock_user.first_name = "Test"
    mock_user.is_bot = False
    mock_user.username = "test_user"

    # Настроим mock_update
    update.callback_query.from_user = mock_user

    test_cases = [
        ("close_templates", True, False),
        ("noop", False, True),
    ]

    for data, expect_edit, expect_answer in test_cases:
        # Сбрасываем моки
        update.callback_query.edit_message_text.reset_mock()
        update.callback_query.answer.reset_mock()
        update.callback_query.data = data

        await button_handler(update, mock_context)

        if expect_edit:
            update.callback_query.edit_message_text.assert_called_once()
        else:
            update.callback_query.edit_message_text.assert_not_called()

        if expect_answer:
            update.callback_query.answer.assert_called_once()
        else:
            update.callback_query.answer.assert_not_called()



@pytest.mark.asyncio
async def test_button_handler_event_actions(mock_update, mock_context, test_databases):
    update = mock_update()
    # Настройка пользователя
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    mock_user.first_name = "Test"
    update.callback_query.from_user = mock_user

    # Очищаем таблицу events перед тестом
    with sqlite3.connect(test_databases["main_db"]) as conn:
        conn.execute("DELETE FROM events")
        conn.commit()

        # Добавляем тестовое мероприятие с новым ID
        conn.execute("""
            INSERT INTO events (
                description, date, time, participant_limit, 
                creator_id, chat_id, message_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            "Test Event", "2023-01-01", "12:00", 10,
            123, 456, 789
        ))
        conn.commit()

        # Получаем ID добавленного мероприятия
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    test_cases = [
        (f"join|{event_id}", "join", True),
        (f"leave|{event_id}", "leave", True),
        (f"edit|{event_id}", "edit", False),
        (f"confirm_delete|{event_id}", "confirm_delete", False),
    ]

    for data, action, expect_answer in test_cases:
        update.callback_query.data = data
        update.callback_query.answer.reset_mock()
        update.callback_query.edit_message_text.reset_mock()

        await button_handler(update, mock_context)

        if expect_answer:
            update.callback_query.answer.assert_called_once()
        else:
            update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_button_handler_edit_actions(mock_update, mock_context, test_databases):
    update = mock_update()
    # 1. Настройка тестового окружения

    # Настраиваем пользователя
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    mock_user.first_name = "Test"
    update.callback_query.from_user = mock_user

    # Настраиваем сообщение
    mock_message = MagicMock(spec=Message)
    mock_message.reply_text = AsyncMock()
    mock_message.chat = MagicMock(spec=Chat)
    mock_message.chat.id = 456
    mock_message.message_id = 789
    update.callback_query.message = mock_message

    # Настраиваем контекст
    mock_context._bot = MagicMock()
    mock_context._bot.bot_data = {
        "db_path": test_databases["main_db"],
        "drafts_db_path": test_databases["drafts_db"]
    }
    mock_context._chat_data = None
    mock_context._user_data = None

    # 2. Подготовка тестовых данных в БД
    with sqlite3.connect(test_databases["main_db"]) as conn:
        conn.execute("DELETE FROM events WHERE id = 1")
        conn.execute("""
            INSERT INTO events VALUES 
            (1, 'Test Event', '2023-01-01', '12:00', 10, 123, 456, 789,
            datetime('now'), datetime('now'))
        """)
        conn.commit()

    # 3. Тестируемые случаи с разными полями для редактирования
    # Обновляем ожидаемые имена полей в соответствии с реальным кодом
    test_cases = [
        ("edit_field|1|description", "description"),
        ("edit_field|1|date", "date"),
        ("edit_field|1|time", "time"),
        ("edit_field|1|limit", "limit"),  # Изменили с 'participant_limit' на 'limit'
    ]

    for data, field_name in test_cases:
        # Подготовка перед каждым тестом
        mock_message.reply_text.reset_mock()
        update.callback_query.data = data

        # 4. Патчим handle_edit_field для проверки его вызова
        with patch('src.buttons.button_handlers.handle_edit_field', new=AsyncMock()) as mock_handler:
            await button_handler(update, mock_context)

            # Проверяем что обработчик был вызван с правильными параметрами
            mock_handler.assert_called_once_with(
                update.callback_query,
                mock_context,
                1,  # event_id
                field_name  # field_name
            )

            # Для edit_field не ожидается прямой вызов reply_text в button_handler
            mock_message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_handle_edit_field(mock_update, mock_context, test_databases):
    update = mock_update()
    # 1. Настройка тестового окружения

    # Настраиваем пользователя (должен быть создателем)
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    update.callback_query.from_user = mock_user

    # Настраиваем сообщение
    mock_message = MagicMock(spec=Message)
    mock_message.chat_id = 456
    mock_message.message_id = 789
    update.callback_query.message = mock_message

    # Настраиваем асинхронные методы
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()

    # Настраиваем контекст
    mock_context._bot = MagicMock()
    mock_context._bot.bot_data = {
        "db_path": test_databases["main_db"],
        "drafts_db_path": test_databases["drafts_db"]
    }
    mock_context._bot.send_message = AsyncMock()
    mock_context._user_data = {}

    # 2. Подготовка тестовых данных в БД
    with sqlite3.connect(test_databases["main_db"]) as conn:
        conn.execute("DELETE FROM events")
        conn.execute("""
            INSERT INTO events 
            (description, date, time, participant_limit, creator_id, chat_id, message_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            "Test Event", "2023-01-01", "12:00", 10,
            123, 456, 789  # creator_id должен совпадать с mock_user.id
        ))
        conn.commit()

    # 3. Патчим вспомогательные функции и классы
    with patch('src.buttons.button_handlers.get_event') as mock_get_event, \
         patch('src.buttons.button_handlers.add_draft') as mock_add_draft, \
         patch('telegram.InlineKeyboardMarkup') as mock_markup:

        # Настраиваем возвращаемые значения
        mock_get_event.return_value = {
            "id": 1,
            "description": "Test Event",
            "date": "2023-01-01",
            "time": "12:00",
            "participant_limit": 10,
            "creator_id": 123,  # Должен совпадать с mock_user.id
            "chat_id": 456,
            "message_id": 789
        }

        mock_add_draft.return_value = 1  # ID нового черновика
        mock_markup.return_value = MagicMock()  # Мок для клавиатуры

        # 4. Тестируем для разных полей
        test_cases = [
            ("description", "описание"),
            ("date", "дату"),
            ("time", "время"),
            ("limit", "лимит участников"),
        ]

        for field_name, expected_text_part in test_cases:
            # Сбрасываем моки перед каждым тестом

            update.callback_query.edit_message_text.reset_mock()
            update.callback_query.answer.reset_mock()
            mock_context._bot.send_message.reset_mock()
            fake_user_data = {}
            fake_user_data.clear()
            mock_markup.reset_mock()
            type(mock_context).user_data = PropertyMock(return_value=fake_user_data)
            mock_add_draft.reset_mock()
            # Вызываем тестируемую функцию
            await handle_edit_field(
                update.callback_query,
                mock_context,
                1,  # event_id
                field_name
            )

            # Отладочная информация
            print(f"\nTesting field: {field_name}")
            print("edit_message_text calls:", update.callback_query.edit_message_text.call_args_list)
            print("send_message calls:", mock_context._bot.send_message.call_args_list)
            print("User data:", mock_context._user_data)

            # Проверяем что был вызван edit_message_text или send_message
            if update.callback_query.edit_message_text.called:
                call_args = update.callback_query.edit_message_text.call_args
                text = call_args.kwargs.get('text', call_args.args[0] if call_args.args else '')
                print(f"Edit message text: {text}")
            elif mock_context._bot.send_message.called:
                call_args = mock_context._bot.send_message.call_args
                text = call_args.kwargs.get('text', call_args.args[0] if call_args.args else '')
                print(f"Send message text: {text}")
            else:
                pytest.fail("Ни edit_message_text, ни send_message не были вызваны")

            # Проверяем текст ответа
            assert expected_text_part.lower() in text.lower(), \
                f"Ожидался текст содержащий '{expected_text_part}', но получено: '{text}'"

            # Проверяем что add_draft был вызван
            mock_add_draft.assert_called_once()

            # Проверяем что user_data был обновлен
            assert 'current_draft_id' in fake_user_data, \
                "current_draft_id не найден в user_data"


@pytest.mark.asyncio
async def test_handle_edit_event_author(mock_update, mock_context):
    update = mock_update()
    from src.buttons.button_handlers import handle_edit_event
    from telegram import InlineKeyboardMarkup

    mock_query = update.callback_query
    mock_query.edit_message_text = AsyncMock()
    mock_query.answer = AsyncMock()
    mock_query.from_user.id = 123

    with patch("src.buttons.button_handlers.get_event") as mock_get_event:
        mock_get_event.return_value = {
            "id": 1,
            "description": "Test",
            "date": "2023-01-01",
            "time": "12:00",
            "participant_limit": 10,
            "creator_id": 123,
            "chat_id": 456,
            "message_id": 789
        }
        print("User ID:", mock_query.from_user.id)
        await handle_edit_event(mock_query, mock_context, event_id=1)

        mock_query.edit_message_text.assert_called_once()
        args, kwargs = mock_query.edit_message_text.call_args
        assert "✏️ Редактирование мероприятия:" in kwargs["text"]
        assert isinstance(kwargs["reply_markup"], InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_handle_edit_event_not_author(mock_update, mock_context):

    update = mock_update()
    mock_query = update.callback_query
    mock_query.answer = AsyncMock()
    mock_query.from_user.id = 999  # не автор

    with patch("src.buttons.button_handlers.get_event") as mock_get_event:
        mock_get_event.return_value = {
            "id": 1,
            "creator_id": 123
        }

        await handle_edit_event(mock_query, mock_context, event_id=1)
        mock_query.answer.assert_called_with("❌ Только автор может редактировать мероприятие", show_alert=False)


@pytest.mark.asyncio
async def test_handle_edit_event_not_found(mock_update, mock_context):
    update = mock_update()


    mock_query = update.callback_query
    mock_query.answer = AsyncMock()

    with patch("src.buttons.button_handlers.get_event", return_value=None):
        await handle_edit_event(mock_query, mock_context, event_id=1)
        mock_query.answer.assert_called_with("Мероприятие не найдено", show_alert=False)





@pytest.mark.asyncio
async def test_handle_edit_field_success(mock_update, mock_context):
    update = mock_update()


    mock_query = update.callback_query
    mock_query.edit_message_text = AsyncMock()
    mock_query.answer = AsyncMock()
    mock_query.from_user.id = 123
    mock_query.message.chat_id = 456
    mock_query.message.message_id = 789

    fake_user_data = {}

    # Патчим user_data, чтобы вернуть наш словарь
    type(mock_context).user_data = PropertyMock(return_value=fake_user_data)

    with patch("src.buttons.button_handlers.get_event") as mock_get_event, \
         patch("src.buttons.button_handlers.add_draft") as mock_add_draft:

        mock_get_event.return_value = {
            "id": 1,
            "description": "Test",
            "date": "2023-01-01",
            "time": "12:00",
            "participant_limit": 10,
            "creator_id": 123,
            "chat_id": 456,
            "message_id": 789
        }

        mock_add_draft.return_value = 42

        await handle_edit_field(mock_query, mock_context, event_id=1, field="description")

        mock_query.edit_message_text.assert_called_once()
        assert fake_user_data["current_draft_id"] == 42



@pytest.mark.asyncio
async def test_handle_edit_field_not_author(mock_update, mock_context):
    update = mock_update()

    mock_query = update.callback_query
    mock_query.from_user.id = 999
    mock_query.answer = AsyncMock()

    with patch("src.buttons.button_handlers.get_event") as mock_get_event:
        mock_get_event.return_value = {"creator_id": 123}

        await handle_edit_field(mock_query, mock_context, event_id=1, field="description")

        mock_query.answer.assert_called_with("❌ Только автор может редактировать мероприятие", show_alert=False)


@pytest.mark.asyncio
async def test_handle_edit_field_event_not_found(mock_update, mock_context):
    update = mock_update()
    from src.buttons.button_handlers import handle_edit_field

    mock_query = update.callback_query
    mock_query.edit_message_text = AsyncMock()

    with patch("src.buttons.button_handlers.get_event", return_value=None):
        await handle_edit_field(mock_query, mock_context, event_id=1, field="description")

        mock_query.edit_message_text.assert_called_with("❌ Мероприятие не найдено")



@pytest.mark.asyncio
@pytest.mark.parametrize("callback_data, expected_response", [
    ("delete_event|1", "Мероприятие удалено"),
    ("cancel_delete|1", "Удаление отменено"),
])
async def test_delete_and_cancel_event(monkeypatch, callback_data, expected_response):
    # Подготовка фиктивного callback_query
    mock_query = AsyncMock()
    mock_query.data = callback_data
    mock_query.from_user.id = 456
    mock_query.message.chat_id = -100123456
    mock_query.message.message_id = 321

    update = MagicMock()
    update.callback_query = mock_query

    context = MagicMock()
    context.user_data = {}
    context.bot_data = {
        "db_path": "test_event_db.sqlite",
        "drafts_db_path": "test_drafts_db.sqlite"
    }

    # Мокаем send_message чтобы проверить, что правильный ответ отправлен
    called = {}

    async def mock_send_message(chat_id, text, **kwargs):
        called["text"] = text

    context.bot.send_message = mock_send_message

    # Мокаем delete_event и cancel_delete
    async def mock_delete_event(query, context, event_id):
        await context.bot.send_message(query.message.chat_id, "Мероприятие удалено")

    async def mock_cancel_delete(query, context, event_id):
        await context.bot.send_message(query.message.chat_id, "Удаление отменено")

    monkeypatch.setattr("src.buttons.button_handlers.handle_delete_event", mock_delete_event)
    monkeypatch.setattr("src.buttons.button_handlers.handle_cancel_delete", mock_cancel_delete)

    # Действие
    await button_handler(update, context)

    # Проверка
    assert called["text"] == expected_response


@pytest.mark.asyncio
async def test_handle_join_new_participant(test_databases, mock_context, mock_callback_query):
    # Подготовка данных в базе
    with sqlite3.connect(test_databases["main_db"]) as conn:
        conn.execute("""
            INSERT INTO events VALUES
            (1, 'Test Event', '2023-01-01', '12:00', 10, 123, 456, 789,
            datetime('now'), datetime('now'))
        """)
        conn.commit()

    # Подготовка данных для теста
    mock_callback_query.data = "join|1"
    mock_callback_query.from_user.id = 123
    mock_callback_query.from_user.first_name = "Test"
    mock_callback_query.from_user.username = "test_user"

    # Вызов тестируемой функции
    await handle_join(mock_callback_query, mock_context, 1)

    # Проверка, был ли вызван ответ в callback_query
    mock_callback_query.answer.assert_called_once_with("Test (@test_user), вы добавлены в список участников!")

    # Проверка, добавлен ли пользователь в базу данных
    with sqlite3.connect(test_databases["main_db"]) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM participants WHERE event_id = 1 AND user_id = 123")
        assert cur.fetchone() is not None



@pytest.mark.asyncio
async def test_handle_confirm_delete(mock_update, mock_context):
    # Настройка тестового мероприятия
    with sqlite3.connect(mock_context.bot_data["db_path"]) as conn:
        conn.execute("DELETE FROM events")
        conn.execute("""
            INSERT INTO events 
            (id, description, date, time, participant_limit, creator_id, chat_id, message_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            1, "Test Event", "2023-01-01", "12:00", 10,
            123, 456, 789  # creator_id должен совпадать с mock_user.id
        ))
        conn.commit()
    update = mock_update(data="confirm_delete|1")
    update.callback_query.from_user.id = 123  # Делаем пользователя автором
    await handle_confirm_delete(update.callback_query, mock_context, 1)

    # Проверяем отображение подтверждения удаления
    assert update.callback_query.edit_message_text.call_count == 1

#До этого места работает
#Дальше пока не отлаживал


@pytest.mark.asyncio
async def test_update_event_message(mock_update, mock_context):
    # Настройка тестового мероприятия
    with sqlite3.connect(mock_context.bot_data["db_path"]) as conn:
        # Создаем таблицу events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                creator_id INTEGER,
                description TEXT,
                date TEXT,
                time TEXT,
                participant_limit INTEGER,
                message_id INTEGER
            )
        """)
        # Создаем таблицу participants
        conn.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                event_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                PRIMARY KEY (event_id, user_id)
            )
        """)
        # Вставляем тестовые данные
        conn.execute("DELETE FROM events")
        conn.execute("""
            INSERT INTO events 
            (id, description, date, time, participant_limit, creator_id, chat_id, message_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            1, "Test Event", "2023-01-01", "12:00", 10,
            123, 456, 789  # creator_id должен совпадать с mock_user.id
        ))
        conn.commit()

    update = mock_update()
    update.callback_query.message.chat = MagicMock()  # 🔥 важно! сбрасываем старый мок
    update.callback_query.message.chat.id = 456
    update.callback_query.message.message_id = 789

    with patch('src.buttons.button_handlers.send_event_message', new=AsyncMock()) as mock_send:
        mock_context._bot = AsyncMock()
        mock_context._bot.send_message = AsyncMock()

        print("DEBUG chat_id:", update.callback_query.message.chat.id)  # Проверяем перед вызовом
        print("DEBUG message_id:", update.callback_query.message.message_id)

        await update_event_message(mock_context, 1, update.callback_query.message)

        assert mock_send.call_count == 1
        mock_send.assert_called_once_with(
            event_id=1,
            context=mock_context,
            chat_id=456,
            message_id=789
        )


@pytest.mark.asyncio
async def test_close_templates_permission_check(mock_update, mock_context):
    update = mock_update()  # ← теперь update — это объект, не функция

    # Настраиваем пользователя с ID 123
    mock_user = MagicMock(spec=User)
    mock_user.id = 123
    update.callback_query.from_user = mock_user

    # Пытаемся закрыть шаблоны для пользователя 456
    update.callback_query.data = "close_templates|456"  # ← исправлено!

    await button_handler(update, mock_context)

    # Проверяем, что был вызван answer с ошибкой
    update.callback_query.answer.assert_called_once_with(
        "❌ Только владелец шаблонов может закрыть это меню",
        show_alert=False
    )
    update.callback_query.edit_message_text.assert_not_called()