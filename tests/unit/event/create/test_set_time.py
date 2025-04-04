import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler
from telegram.error import BadRequest


@pytest.mark.asyncio
async def test_set_time_success(mock_update, mock_context):
    """Тест успешной обработки корректного времени"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_time import set_time

        # Настройка тестовых данных
        test_time = "14:30"
        test_description = "Тестовое мероприятие"
        test_date = "15.12.2023"

        # Мокируем сообщение
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_time
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()

        # Мокируем контекст
        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Мокируем функции БД
        with patch('src.event.create.set_time.update_draft') as mock_update_draft, \
                patch('src.event.create.set_time.get_draft') as mock_get_draft:
            mock_get_draft.return_value = {
                "description": test_description,
                "date": test_date,
                "time": test_time
            }

            # Вызываем тестируемую функцию
            result = await set_time(mock_update, mock_context)

            # Проверки
            mock_update_draft.assert_called_once_with(
                db_path="test_db_path",
                draft_id=1,
                status="AWAIT_PARTICIPANT_LIMIT",
                time=test_time
            )

            mock_get_draft.assert_called_once_with("test_db_path", 1)

            mock_context.bot.edit_message_text.assert_called_once_with(
                chat_id=12345,
                message_id=54321,
                text=f"📢 {test_description}\n\n📅 Дата: {test_date}\n\n🕒 Время: {test_time}\n\nВведите количество участников (0 - неограниченное):",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
            )

            mock_update.message.delete.assert_called_once()
            assert result == "SET_LIMIT"


@pytest.mark.asyncio
async def test_set_time_invalid_format(mock_update, mock_context):
    """Тест обработки неверного формата времени"""
    with patch('src.handlers.conversation_handler_states.SET_TIME', new=2):
        from temp.set_time import set_time

        # Настройка неверного времени
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "14-30"  # Неправильный формат
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Вызываем тестируемую функцию
        result = await set_time(mock_update, mock_context)

        # Проверки
        mock_context.bot.edit_message_text.assert_called_once_with(
            chat_id=12345,
            message_id=54321,
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        mock_update.message.delete.assert_called_once()
        assert result == 2


@pytest.mark.asyncio
async def test_set_time_draft_not_found(mock_update, mock_context):
    """Тест случая, когда черновик не найден"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_time import set_time

        # Настройка тестовых данных
        test_time = "14:30"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_time
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Мокируем функции БД
        with patch('src.event.create.set_time.update_draft'), \
                patch('src.event.create.set_time.get_draft') as mock_get_draft:
            mock_get_draft.return_value = None  # Черновик не найден

            # Вызываем тестируемую функцию
            result = await set_time(mock_update, mock_context)

            # Проверки
            mock_update.message.reply_text.assert_called_once_with(
                "Ошибка: черновик мероприятия не найден."
            )
            assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_time_delete_message_error(mock_update, mock_context):
    """Тест обработки ошибки при удалении сообщения"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_time import set_time

        # Настройка тестовых данных
        test_time = "14:30"
        test_description = "Тестовое мероприятие"
        test_date = "15.12.2023"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_time
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock(side_effect=BadRequest("Message to delete not found"))

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()
        mock_context.bot.edit_message_text = AsyncMock()

        # Мокируем функции БД
        with patch('src.event.create.set_time.update_draft'), \
                patch('src.event.create.set_time.get_draft') as mock_get_draft:
            mock_get_draft.return_value = {
                "description": test_description,
                "date": test_date,
                "time": test_time
            }

            # Вызываем тестируемую функцию
            result = await set_time(mock_update, mock_context)

            # Проверяем, что функция продолжает работу после ошибки удаления
            mock_update.message.delete.assert_called_once()
            mock_context.bot.edit_message_text.assert_called_once()
            assert result == "SET_LIMIT"


@pytest.mark.asyncio
async def test_set_time_keyboard_structure(mock_update, mock_context):
    """Тест структуры клавиатуры"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_time import set_time
        from telegram import InlineKeyboardMarkup

        # Настройка тестовых данных
        test_time = "14:30"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_time
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()

        # Мокируем функции БД
        with patch('src.event.create.set_time.update_draft'), \
                patch('src.event.create.set_time.get_draft') as mock_get_draft:
            mock_get_draft.return_value = {
                "description": "Тест",
                "date": "01.01.2023",
                "time": test_time
            }

            # Вызываем тестируемую функцию
            await set_time(mock_update, mock_context)

            # Проверяем структуру клавиатуры
            call_args = mock_context.bot.edit_message_text.call_args[1]
            reply_markup = call_args['reply_markup']

            assert isinstance(reply_markup, InlineKeyboardMarkup)
            assert len(reply_markup.inline_keyboard) == 1
            assert len(reply_markup.inline_keyboard[0]) == 1

            button = reply_markup.inline_keyboard[0][0]
            assert button.text == "⛔ Отмена"
            assert button.callback_data == "cancel_input"