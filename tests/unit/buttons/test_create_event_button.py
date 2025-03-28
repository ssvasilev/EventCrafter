import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, CallbackQuery, Message, User, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

@pytest.mark.asyncio
async def test_create_event_button_success(mock_update, mock_context):
    # Патчим модуль с состояниями перед импортом тестируемой функции
    with patch('src.buttons.create_event_button.SET_DESCRIPTION', new='SET_DESCRIPTION'):
        from src.buttons.create_event_button import create_event_button

        # Настройка mock объектов
        mock_update.callback_query = MagicMock(spec=CallbackQuery)
        mock_update.callback_query.from_user = MagicMock(spec=User)
        mock_update.callback_query.from_user.id = 123
        mock_update.callback_query.message = MagicMock(spec=Message)
        mock_update.callback_query.message.chat_id = 456
        mock_update.callback_query.message.message_id = 789
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        # Мокируем bot_data
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}

        # Делаем context.bot асинхронным моком
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Мокируем функцию add_draft
        with patch('src.buttons.create_event_button.add_draft') as mock_add_draft:
            mock_add_draft.return_value = 1  # Успешное создание черновика

            # Вызываем тестируемую функцию
            result = await create_event_button(mock_update, mock_context)

            # Проверки
            mock_update.callback_query.answer.assert_called_once()
            mock_add_draft.assert_called_once_with(
                db_path="test_db_path",
                creator_id=123,
                chat_id=456,
                status="AWAIT_DESCRIPTION"
            )

            # Проверяем вызов edit_message_text с детальными проверками клавиатуры
            assert mock_context.bot.edit_message_text.call_count == 1
            call_args = mock_context.bot.edit_message_text.call_args[1]

            assert call_args['chat_id'] == 456
            assert call_args['message_id'] == 789
            assert call_args['text'] == "Введите описание мероприятия:"

            # Проверяем структуру клавиатуры
            reply_markup = call_args['reply_markup']
            assert isinstance(reply_markup, InlineKeyboardMarkup)

            keyboard = reply_markup.inline_keyboard
            assert len(keyboard) == 1  # Одна строка кнопок
            assert len(keyboard[0]) == 1  # Одна кнопка в строке

            button = keyboard[0][0]
            assert isinstance(button, InlineKeyboardButton)
            assert button.text == "⛔ Отмена"
            assert button.callback_data == "cancel_input"

            # Проверяем сохраненные данные
            assert mock_context.user_data["draft_id"] == 1
            assert result == "SET_DESCRIPTION" #Итоговое состояние после нажатия кнопки