import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler
from telegram.error import BadRequest


@pytest.mark.asyncio
async def test_set_date_success(mock_update, mock_context):
    """Тест успешной обработки корректной даты"""
    with patch('src.handlers.conversation_handler_states.SET_TIME', new='SET_TIME'):
        from temp.set_date import set_date

        # Настройка тестовых данных
        test_date = "15.12.2023"
        test_description = "Тестовое мероприятие"

        # Мокируем сообщение
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_date
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
        with patch('src.event.create.set_date.update_draft') as mock_update_draft, \
                patch('src.event.create.set_date.get_draft') as mock_get_draft:
            mock_get_draft.return_value = {
                "description": test_description,
                "date": test_date
            }

            # Вызываем тестируемую функцию
            result = await set_date(mock_update, mock_context)

            # Проверки
            mock_update_draft.assert_called_once_with(
                db_path="test_db_path",
                draft_id=1,
                status="AWAIT_TIME",
                date=test_date
            )

            mock_get_draft.assert_called_once_with("test_db_path", 1)

            mock_context.bot.edit_message_text.assert_called_once_with(
                chat_id=12345,
                message_id=54321,
                text=f"📢 {test_description}\n\n📅 Дата: {test_date}\n\nВведите время мероприятия в формате ЧЧ:ММ",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
            )

            mock_update.message.delete.assert_called_once()
            assert result == "SET_TIME"


@pytest.mark.asyncio
async def test_set_date_invalid_format(mock_update, mock_context):
    """Тест обработки неверного формата даты"""
    with patch('src.handlers.conversation_handler_states.SET_DATE', new=1):
        from temp.set_date import set_date

        # Настройка неверной даты
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "2023-12-15"  # Неправильный формат
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
        result = await set_date(mock_update, mock_context)

        # Проверки
        mock_context.bot.edit_message_text.assert_called_once_with(
            chat_id=12345,
            message_id=54321,
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        mock_update.message.delete.assert_called_once()
        assert result == 1


@pytest.mark.asyncio
async def test_set_date_draft_not_found(mock_update, mock_context):
    """Тест случая, когда черновик не найден"""
    with patch('src.handlers.conversation_handler_states.SET_TIME', new='SET_TIME'):
        from temp.set_date import set_date

        # Настройка тестовых данных
        test_date = "15.12.2023"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_date
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
        with patch('src.event.create.set_date.update_draft'), \
                patch('src.event.create.set_date.get_draft') as mock_get_draft:
            mock_get_draft.return_value = None  # Черновик не найден

            # Вызываем тестируемую функцию
            result = await set_date(mock_update, mock_context)

            # Проверки
            mock_update.message.reply_text.assert_called_once_with(
                "Ошибка: черновик мероприятия не найден."
            )
            assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_date_delete_message_error(mock_update, mock_context):
    """Тест обработки ошибки при удалении сообщения"""
    with patch('src.handlers.conversation_handler_states.SET_TIME', new='SET_TIME'):
        from temp.set_date import set_date

        # Настройка тестовых данных
        test_date = "15.12.2023"
        test_description = "Тестовое мероприятие"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_date
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
        with patch('src.event.create.set_date.update_draft'), \
                patch('src.event.create.set_date.get_draft') as mock_get_draft:
            mock_get_draft.return_value = {
                "description": test_description,
                "date": test_date
            }

            # Вызываем тестируемую функцию
            result = await set_date(mock_update, mock_context)

            # Проверяем, что функция продолжает работу после ошибки удаления
            mock_update.message.delete.assert_called_once()
            mock_context.bot.edit_message_text.assert_called_once()
            assert result == "SET_TIME"