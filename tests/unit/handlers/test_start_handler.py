import pytest
from telegram import InlineKeyboardMarkup
from unittest.mock import patch

#Тест проверки команды /start
@pytest.mark.asyncio
async def test_start_command(mock_update, mock_context):
    from src.handlers.start_handler import start

    await start(mock_update, mock_context)

    # Проверка вызова
    mock_update.message.reply_text.assert_called_once()

    # Проверка сообщения
    called_args = mock_update.message.reply_text.call_args[0]
    assert called_args[0] == "Привет! Я бот для организации мероприятий. Выберите действие:"

    # Проверка клавиатуры
    keyboard = mock_update.message.reply_text.call_args[1]['reply_markup'].inline_keyboard
    assert len(keyboard) == 2
    assert keyboard[0][0].text == "📅 Создать мероприятие"
    assert keyboard[0][0].callback_data == "create_event"
    assert keyboard[1][0].text == "📋 Мероприятия, в которых я участвую"
    assert keyboard[1][0].callback_data == "my_events"

    # Проверка user_data
    assert mock_context.user_data["chat_id"] == 12345
    assert "bot_message_id" in mock_context.user_data

#Проверка, если в ответ не пришло сообщение
@pytest.mark.asyncio
async def test_start_command_no_message(mock_update, mock_context):
    from src.handlers.start_handler import start

    # Убираем message из update
    mock_update.message = None

    with pytest.raises(AttributeError):
        await start(mock_update, mock_context)
