import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import CallbackQuery, Message, User, InlineKeyboardMarkup


@pytest.mark.asyncio
async def test_edit_event_button_success(mock_update, mock_context):
    # Патчим модуль с состояниями перед импортом тестируемой функции
    with patch('src.buttons.edit_event_button.EDIT_EVENT', new='EDIT_EVENT'):
        from temp.edit_event_button import edit_event_button

        # Настройка mock объектов
        mock_update.callback_query = MagicMock(spec=CallbackQuery)
        mock_update.callback_query.data = "edit_event|123"
        mock_update.callback_query.from_user = MagicMock(spec=User)
        mock_update.callback_query.from_user.id = 456  # ID автора
        mock_update.callback_query.message = MagicMock(spec=Message)
        mock_update.callback_query.message.message_id = 789
        mock_update.callback_query.message.text = "Original text"
        mock_update.callback_query.message.reply_markup = MagicMock()
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        # Мокируем bot_data
        mock_context.bot_data = {"db_path": "test_db_path"}

        # Мокируем функцию get_event
        with patch('src.buttons.edit_event_button.get_event') as mock_get_event:
            mock_get_event.return_value = {
                "creator_id": 456,  # Совпадает с ID пользователя
                "chat_id": 123,
                "description": "Test event",
                "date": "2023-01-01",
                "time": "12:00"
            }

            # Вызываем тестируемую функцию
            result = await edit_event_button(mock_update, mock_context)

            # Проверки
            mock_update.callback_query.answer.assert_not_called()
            mock_get_event.assert_called_once_with("test_db_path", "123")

            # Проверяем вызов edit_message_text
            assert mock_update.callback_query.edit_message_text.call_count == 1

            # Получаем аргументы вызова (учитываем позиционные аргументы)
            call_args, call_kwargs = mock_update.callback_query.edit_message_text.call_args

            # Проверяем позиционные аргументы
            assert call_args[0] == "Что вы хотите изменить?"

            # Проверяем именованные аргументы (reply_markup)
            assert 'reply_markup' in call_kwargs
            reply_markup = call_kwargs['reply_markup']
            assert isinstance(reply_markup, InlineKeyboardMarkup)

            # Проверяем структуру клавиатуры
            keyboard = reply_markup.inline_keyboard
            assert len(keyboard) == 3  # 3 строки кнопок

            # Проверяем первую строку кнопок
            assert len(keyboard[0]) == 2
            assert keyboard[0][0].text == "📝 Описание"
            assert keyboard[0][0].callback_data == "edit_description|123"
            assert keyboard[0][1].text == "👥 Лимит участников"
            assert keyboard[0][1].callback_data == "edit_limit|123"

            # Проверяем вторую строку кнопок
            assert len(keyboard[1]) == 2
            assert keyboard[1][0].text == "📅 Дата"
            assert keyboard[1][0].callback_data == "edit_date|123"
            assert keyboard[1][1].text == "🕒 Время"
            assert keyboard[1][1].callback_data == "edit_time|123"

            # Проверяем третью строку кнопок
            assert len(keyboard[2]) == 2
            assert keyboard[2][0].text == "🗑️ Удалить"
            assert keyboard[2][0].callback_data == "delete|123"
            assert keyboard[2][1].text == "⛔ Отмена"
            assert keyboard[2][1].callback_data == "cancel_input"

            # Проверяем сохраненные данные
            assert mock_context.user_data["event_id"] == "123"
            assert mock_context.user_data["bot_message_id"] == 789
            assert mock_context.user_data["original_text"] == "Original text"
            assert isinstance(mock_context.user_data["original_reply_markup"], MagicMock)

            assert result == "EDIT_EVENT"


@pytest.mark.asyncio
async def test_edit_event_button_not_author(mock_update, mock_context):
    from temp.edit_event_button import edit_event_button

    # Настройка mock объектов
    mock_update.callback_query = MagicMock(spec=CallbackQuery)
    mock_update.callback_query.data = "edit_event|123"
    mock_update.callback_query.from_user = MagicMock(spec=User)
    mock_update.callback_query.from_user.id = 789  # Не автор
    mock_update.callback_query.answer = AsyncMock()

    # Мокируем bot_data
    mock_context.bot_data = {"db_path": "test_db_path"}

    # Мокируем функцию get_event
    with patch('src.buttons.edit_event_button.get_event') as mock_get_event:
        mock_get_event.return_value = {
            "creator_id": 456,  # Другой ID
            "chat_id": 123,
            "description": "Test event",
            "date": "2023-01-01",
            "time": "12:00"
        }

        # Вызываем тестируемую функцию
        result = await edit_event_button(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once_with(
            "Только автор мероприятия может редактировать его.",
            show_alert=False
        )
        assert result == -1  # ConversationHandler.END

@pytest.mark.asyncio
async def test_edit_event_button_not_found(mock_update, mock_context):
    from temp.edit_event_button import edit_event_button

    # Настройка mock объектов
    mock_update.callback_query = MagicMock(spec=CallbackQuery)
    mock_update.callback_query.data = "edit_event|123"
    mock_update.callback_query.answer = AsyncMock()

    # Мокируем bot_data
    mock_context.bot_data = {"db_path": "test_db_path"}

    # Мокируем функцию get_event
    with patch('src.buttons.edit_event_button.get_event') as mock_get_event:
        mock_get_event.return_value = None

        # Вызываем тестируемую функцию
        result = await edit_event_button(mock_update, mock_context)

        # Проверки
        mock_update.callback_query.answer.assert_called_once_with(
            "Мероприятие не найдено.",
            show_alert=True
        )
        assert result == -1  # ConversationHandler.END