import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, CallbackQuery, User, Chat
from telegram.ext import ContextTypes

@pytest.mark.asyncio
async def test_my_events_button_no_events(mock_update, mock_context):
    from src.buttons.my_events_button import my_events_button

    # Настройка mock объектов
    mock_update.callback_query = MagicMock(spec=CallbackQuery)
    mock_update.callback_query.from_user = MagicMock(spec=User)
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    # Мокируем bot_data
    mock_context.bot_data = {"db_path": "test_db_path"}

    # Мокируем функцию get_events_by_participant
    with patch('src.buttons.my_events_button.get_events_by_participant') as mock_get_events:
        mock_get_events.return_value = []

        # Вызываем тестируемую функцию
        result = await my_events_button(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "Вы не участвуете ни в одном мероприятии."
        )
        assert result is None

@pytest.mark.asyncio
async def test_my_events_button_with_events(mock_update, mock_context):
    from src.buttons.my_events_button import my_events_button

    # Настройка mock объектов
    mock_update.callback_query = MagicMock(spec=CallbackQuery)
    mock_update.callback_query.from_user = MagicMock(spec=User)
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    # Мокируем bot и его методы
    mock_context.bot = AsyncMock()
    mock_context.bot.send_message = AsyncMock()
    mock_context.bot.get_chat = AsyncMock(return_value=MagicMock(
        title="Test Chat",
        username="testchat",
        invite_link="https://t.me/testchat"
    ))

    # Мокируем bot_data
    mock_context.bot_data = {"db_path": "test_db_path"}

    # Мокируем функцию get_events_by_participant
    with patch('src.buttons.my_events_button.get_events_by_participant') as mock_get_events:
        mock_get_events.return_value = [
            {
                "chat_id": -100123,
                "message_id": 456,
                "description": "Test Event",
                "date": "2023-01-01",
                "time": "12:00",
                "creator_id": 123
            }
        ]

        # Вызываем тестируемую функцию
        result = await my_events_button(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once()

        # Проверяем вызов send_message
        assert mock_context.bot.send_message.call_count == 1

        # Получаем аргументы вызова
        _, kwargs = mock_context.bot.send_message.call_args

        # Проверяем именованные аргументы
        assert kwargs['chat_id'] == 123
        assert kwargs['parse_mode'] == "HTML"
        assert kwargs['disable_web_page_preview'] is True

        # Проверяем содержимое сообщения
        expected_text = (
            "📋 Мероприятия, в которых вы участвуете:\n\n"
            "💬 <b>Test Chat</b> (https://t.me/testchat):\n"
            "  - <a href='https://t.me/c/123/456'>📅 Test Event</a> (2023-01-01 12:00)\n\n"
        )
        assert kwargs['text'] == expected_text

        # Проверяем вызов edit_message_text
        mock_update.callback_query.edit_message_text.assert_called_once_with(
            "Список мероприятий отправлен вам в личные сообщения."
        )

        assert result == -1  # ConversationHandler.END

@pytest.mark.asyncio
async def test_my_events_button_send_error(mock_update, mock_context):
    from src.buttons.my_events_button import my_events_button
    from unittest.mock import patch

    # Настройка mock объектов
    mock_update.callback_query = MagicMock(spec=CallbackQuery)
    mock_update.callback_query.from_user = MagicMock(spec=User)
    mock_update.callback_query.from_user.id = 123
    mock_update.callback_query.answer = AsyncMock()
    mock_update.callback_query.edit_message_text = AsyncMock()

    # Мокируем bot_data
    mock_context.bot_data = {"db_path": "test_db_path"}

    # Мокируем logger.error
    with patch('src.buttons.my_events_button.logger.error') as mock_logger_error:
        # Мокируем функцию get_events_by_participant
        with patch('src.buttons.my_events_button.get_events_by_participant') as mock_get_events:
            mock_get_events.return_value = [
                {
                    "chat_id": -100123,
                    "message_id": 456,
                    "description": "Test Event",
                    "date": "2023-01-01",
                    "time": "12:00",
                    "creator_id": 123
                }
            ]

            # Мокируем send_message с ошибкой
            mock_context.bot = AsyncMock()
            mock_context.bot.send_message = AsyncMock(side_effect=Exception("Send error"))

            # Вызываем тестируемую функцию
            result = await my_events_button(mock_update, mock_context)

            # Проверки
            mock_update.callback_query.answer.assert_called_once()
            mock_update.callback_query.edit_message_text.assert_called_once_with(
                "Не удалось отправить сообщение. Пожалуйста, начните чат с ботом."
            )
            mock_logger_error.assert_called_once_with("Ошибка при отправке сообщения: Send error")
            assert result == -1  # ConversationHandler.END