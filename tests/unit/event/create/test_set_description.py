import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Message
from telegram.error import BadRequest


@pytest.mark.asyncio
async def test_set_description_success(mock_update, mock_context):
    # Патчим модуль с состояниями перед импортом тестируемой функции
    with patch('src.handlers.conversation_handler_states.SET_DATE', new='SET_DATE'):
        from src.event.create.set_parameter import set_description
        from telegram import InlineKeyboardMarkup

        # Настройка mock объектов
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "Тестовое описание мероприятия"
        mock_update.message.chat_id = 12345
        mock_update.message.message_id = 67890
        mock_update.message.delete = AsyncMock()

        # Устанавливаем необходимые данные в user_data
        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }

        # Мокируем bot_data
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}

        # Мокируем функции и бота
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Мокируем функцию update_draft
        with patch('src.event.create.set_description.update_draft') as mock_update_draft:
            # Вызываем тестируемую функцию
            result = await set_description(mock_update, mock_context)

            # Проверки
            # Проверяем вызов update_draft
            mock_update_draft.assert_called_once_with(
                db_path="test_db_path",
                draft_id=1,
                status="AWAIT_DATE",
                description="Тестовое описание мероприятия"
            )

            # Проверяем вызов edit_message_text
            assert mock_context.bot.edit_message_text.call_count == 1
            call_args = mock_context.bot.edit_message_text.call_args[1]

            assert call_args['chat_id'] == 12345
            assert call_args['message_id'] == 54321
            assert call_args['text'] == "📢 Тестовое описание мероприятия\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ"

            # Проверяем структуру клавиатуры
            reply_markup = call_args['reply_markup']
            assert isinstance(reply_markup, InlineKeyboardMarkup)
            assert len(reply_markup.inline_keyboard) == 1
            assert len(reply_markup.inline_keyboard[0]) == 1
            button = reply_markup.inline_keyboard[0][0]
            assert button.text == "⛔ Отмена"
            assert button.callback_data == "cancel_input"

            # Проверяем вызов delete сообщения пользователя
            mock_update.message.delete.assert_called_once()

            # Проверяем возвращаемое состояние
            assert result == "SET_DATE"


@pytest.mark.asyncio
async def test_set_description_with_delete_error(mock_update, mock_context):
    # Патчим модуль с состояниями перед импортом тестируемой функции
    with patch('src.handlers.conversation_handler_states.SET_DATE', new='SET_DATE'):
        from src.event.create.set_parameter import set_description

        # Настройка mock объектов
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "Тестовое описание мероприятия"
        mock_update.message.chat_id = 12345
        mock_update.message.message_id = 67890
        mock_update.message.delete = AsyncMock(side_effect=BadRequest("Message to delete not found"))

        # Устанавливаем необходимые данные в user_data
        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }

        # Мокируем bot_data
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}

        # Мокируем функции и бота
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Мокируем функцию update_draft
        with patch('src.database.db_draft_operations.update_draft'):
            # Вызываем тестируемую функцию
            result = await set_description(mock_update, mock_context)

            # Проверяем, что функция продолжает работу после ошибки удаления
            mock_update.message.delete.assert_called_once()
            mock_context.bot.edit_message_text.assert_called_once()
            assert result == "SET_DATE"


@pytest.mark.asyncio
async def test_set_description_keyboard_structure(mock_update, mock_context):
    # Патчим модуль с состояниями перед импортом тестируемой функции
    with patch('src.handlers.conversation_handler_states.SET_DATE', new='SET_DATE'):
        from src.event.create.set_parameter import set_description
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        # Настройка mock объектов
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "Тестовое описание"
        mock_update.message.chat_id = 12345
        mock_update.message.message_id = 67890
        mock_update.message.delete = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()

        # Исправляем путь для мокирования update_draft
        with patch('src.event.create.set_description.update_draft'):
            # Вызываем тестируемую функцию
            await set_description(mock_update, mock_context)

            # Проверяем структуру клавиатуры
            call_args = mock_context.bot.edit_message_text.call_args[1]
            reply_markup = call_args['reply_markup']

            assert isinstance(reply_markup, InlineKeyboardMarkup)

            keyboard = reply_markup.inline_keyboard
            assert len(keyboard) == 1  # Одна строка кнопок
            assert len(keyboard[0]) == 1  # Одна кнопка в строке

            button = keyboard[0][0]
            assert isinstance(button, InlineKeyboardButton)
            assert button.text == "⛔ Отмена"
            assert button.callback_data == "cancel_input"