import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram import CallbackQuery, Message, User

from src.buttons import create_event_button, my_events_button
from src.buttons.menu_button_handlers import menu_button_handler, show_main_menu
from src.handlers.template_handlers import handle_my_templates
from src.handlers.cancel_handler import cancel_draft


@pytest.mark.asyncio
@pytest.mark.parametrize("callback_data", [
    "menu_create_event",
    "menu_my_events",
    "menu_my_templates",
    "menu_main",
    "menu_unknown"
])
async def test_menu_actions(callback_data, mock_context, monkeypatch):
    """Тестирует обработку команд меню в menu_button_handler."""

    # Моки и заглушки
    mock_query = AsyncMock(spec=CallbackQuery)
    mock_query.data = callback_data
    mock_query.from_user = User(id=123, first_name="Test", is_bot=False)
    mock_query.message = Message(message_id=1, chat=MagicMock(id=456), date=None)
    mock_context.user_data = {}
    mock_context.bot_data = {
        "db_path": "test_main.db",
        "drafts_db_path": "test_drafts.db"
    }

    # Внедрение моков в update
    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    # Моки для функций
    mock_create_event_button = AsyncMock()
    mock_my_events_button = AsyncMock()
    mock_handle_my_templates = AsyncMock()
    mock_show_main_menu = AsyncMock()

    # Переопределение вызываемых функций
    monkeypatch.setattr("src.buttons.menu_button_handlers.create_event_button", mock_create_event_button)
    monkeypatch.setattr("src.buttons.menu_button_handlers.my_events_button", mock_my_events_button)
    monkeypatch.setattr("src.buttons.menu_button_handlers.handle_my_templates", mock_handle_my_templates)
    monkeypatch.setattr("src.buttons.menu_button_handlers.show_main_menu", mock_show_main_menu)

    await menu_button_handler(mock_update, mock_context)

    # Проверка, что соответствующая функция была вызвана
    if callback_data == "menu_create_event":
        mock_create_event_button.assert_awaited_once()
    elif callback_data == "menu_my_events":
        mock_my_events_button.assert_awaited_once()
    elif callback_data == "menu_my_templates":
        mock_handle_my_templates.assert_awaited_once()
    elif callback_data == "menu_main":
        mock_show_main_menu.assert_awaited_once()
    elif callback_data == "menu_unknown":
        mock_query.edit_message_text.assert_called_once_with("Неизвестная команда меню.")



@pytest.mark.asyncio
async def test_cancel_draft_authorized(monkeypatch, mock_context):
    """Проверка успешной отмены черновика автором."""
    mock_query = AsyncMock(spec=CallbackQuery)
    mock_query.data = "cancel_draft|1"
    mock_query.from_user.id = 123
    mock_query.message = Message(message_id=1, chat=MagicMock(id=456), date=None)
    mock_update = MagicMock(callback_query=mock_query)

    mock_context.bot_data = {
        "db_path": "test_main.db",
        "drafts_db_path": "test_drafts.db"
    }

    monkeypatch.setattr(
        "src.buttons.menu_button_handlers.get_draft",
        lambda *_: {"id": 1, "creator_id": 123, "event_id": None}
    )

    mock_cancel_draft = AsyncMock()
    monkeypatch.setattr("src.buttons.menu_button_handlers.cancel_draft", mock_cancel_draft)

    mock_cancel_delete = AsyncMock()
    monkeypatch.setattr("src.buttons.menu_button_handlers.handle_cancel_delete", mock_cancel_delete)

    await menu_button_handler(mock_update, mock_context)

    mock_cancel_draft.assert_awaited_once()



@pytest.mark.asyncio
async def test_cancel_draft_unauthorized(monkeypatch, mock_context):
    """Проверка запрета отмены чужого черновика."""

    # Создаем мок запроса
    mock_query = AsyncMock(spec=CallbackQuery)
    mock_query.data = "cancel_draft|1"
    mock_query.from_user.id = 321  # не автор
    mock_query.message = Message(message_id=1, chat=MagicMock(id=456), date=None)
    mock_update = MagicMock(callback_query=mock_query)

    # Настройка данных контекста
    mock_context.bot_data = {
        "db_path": "test_main.db",
        "drafts_db_path": "test_drafts.db"
    }

    # Мокируем возвращаемое значение get_draft
    mock_draft = {"id": 1, "creator_id": 123, "event_id": None}
    monkeypatch.setattr("src.buttons.menu_button_handlers.get_draft", lambda *_: mock_draft)

    # Запуск тестируемой функции
    await menu_button_handler(mock_update, mock_context)

    # Проверка, что было возвращено сообщение о том, что только автор может отменить черновик
    mock_query.answer.assert_awaited_with("❌ Только автор может отменить черновик", show_alert=False)



