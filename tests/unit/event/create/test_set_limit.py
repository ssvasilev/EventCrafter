import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta, timezone
from telegram import Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler

@pytest.mark.asyncio
async def test_set_limit_success(mock_update, mock_context, mock_config, mock_logger):
    """Тест успешной обработки корректного лимита"""
    # Импортируем тестируемый модуль после всех моков
    from temp.set_limit import set_limit

    # Настройка тестовых данных
    test_limit = "10"
    test_description = "Тестовое мероприятие"
    test_date = "15.12.2023"
    test_time = "14:30"
    test_chat_id = -1001234567890
    test_creator_id = 12345
    test_message_id = 54321

    # Мокируем сообщение
    mock_update.message = MagicMock(spec=Message)
    mock_update.message.text = test_limit
    mock_update.message.chat_id = test_chat_id
    mock_update.message.delete = AsyncMock()

    # Мокируем контекст
    mock_context.user_data = {
        "draft_id": 1,
        "bot_message_id": test_message_id
    }
    mock_context.bot_data = {
        "drafts_db_path": "test_drafts_db_path",
        "db_path": "test_db_path",
        "tz": timezone(timedelta(hours=3))  # UTC+3
    }
    mock_context.bot = AsyncMock()
    mock_context.job_queue = MagicMock()

    # Мокируем все зависимости
    with patch('src.event.create.set_limit.update_draft') as mock_update_draft, \
         patch('src.event.create.set_limit.get_draft') as mock_get_draft, \
         patch('src.event.create.set_limit.delete_draft') as mock_delete_draft, \
         patch('src.event.create.set_limit.add_event') as mock_add_event, \
         patch('src.event.create.set_limit.update_event_field') as mock_update_event_field, \
         patch('src.event.create.set_limit.add_scheduled_job') as mock_add_scheduled_job, \
         patch('src.event.create.set_limit.send_event_message') as mock_send_event_message:

        # Настройка возвращаемых значений
        mock_get_draft.return_value = {
            "description": test_description,
            "date": test_date,
            "time": test_time,
            "creator_id": test_creator_id,
            "chat_id": test_chat_id
        }
        mock_add_event.return_value = 1  # event_id
        mock_send_event_message.return_value = 11111  # message_id

        # Вызываем тестируемую функцию
        result = await set_limit(mock_update, mock_context)

        # Проверки
        mock_update_draft.assert_called_once_with(
            db_path="test_drafts_db_path",
            draft_id=1,
            status="DONE",
            participant_limit=10
        )

        mock_get_draft.assert_called_once_with("test_drafts_db_path", 1)
        mock_add_event.assert_called_once_with(
            db_path="test_db_path",
            description=test_description,
            date=test_date,
            time=test_time,
            limit=10,
            creator_id=test_creator_id,
            chat_id=test_chat_id,
            message_id=None
        )

        # Проверяем что message_id обновляется после отправки
        mock_send_event_message.assert_called_once_with(1, mock_context, test_chat_id)
        mock_update_event_field.assert_called_once_with("test_db_path", 1, "message_id", 11111)

        # Проверяем уведомление создателю
        assert "https://t.me/c/" in mock_context.bot.send_message.call_args[1]['text']

        # Проверяем удаление сообщений
        mock_update.message.delete.assert_called_once()
        mock_context.bot.delete_message.assert_called_once_with(
            chat_id=test_chat_id,
            message_id=test_message_id
        )

        # Проверяем планирование задач
        assert mock_context.job_queue.run_once.call_count == 3
        assert mock_add_scheduled_job.call_count == 3

        # Проверяем очистку user_data и завершение диалога
        assert mock_context.user_data == {}
        assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_limit_unlimited(mock_update, mock_context):
    """Тест обработки неограниченного лимита (0)"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_limit import set_limit

        # Настройка тестовых данных
        test_limit = "0"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_limit
        mock_update.message.chat_id = -1001234567890
        mock_update.message.delete = AsyncMock()

        mock_context.user_data = {"draft_id": 1, "bot_message_id": 54321}
        mock_context.bot_data = {
            "drafts_db_path": "test_drafts_db_path",
            "db_path": "test_db_path",
            "tz": timezone(timedelta(hours=3))  # UTC+3 для Москвы
        }
        mock_context.bot = AsyncMock()
        mock_context.job_queue = MagicMock()

        with patch('src.event.create.set_limit.update_draft'), \
                patch('src.event.create.set_limit.get_draft') as mock_get_draft, \
                patch('src.event.create.set_limit.add_event') as mock_add_event, \
                patch('src.event.create.set_limit.send_event_message'):
            mock_get_draft.return_value = {
                "description": "Тест",
                "date": "01.01.2023",
                "time": "12:00",
                "creator_id": 12345,
                "chat_id": -1001234567890
            }
            mock_add_event.return_value = 1

            result = await set_limit(mock_update, mock_context)

            # Проверяем, что для лимита передается None при значении 0
            mock_add_event.assert_called_once()
            assert mock_add_event.call_args[1]['limit'] is None
            assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_limit_invalid_format(mock_update, mock_context):
    """Тест обработки неверного формата лимита"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new=3):
        from temp.set_limit import set_limit

        # Настройка неверного лимита
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "не число"
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
        result = await set_limit(mock_update, mock_context)

        # Проверки
        mock_context.bot.edit_message_text.assert_called_once_with(
            chat_id=12345,
            message_id=54321,
            text="Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
            parse_mode="HTML"
        )
        mock_update.message.delete.assert_called_once()
        assert result == 3


@pytest.mark.asyncio
async def test_set_limit_negative(mock_update, mock_context):
    """Тест обработки отрицательного лимита"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new=3):
        from temp.set_limit import set_limit

        # Настройка отрицательного лимита
        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = "-5"
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
        result = await set_limit(mock_update, mock_context)

        # Проверки
        mock_context.bot.edit_message_text.assert_called_once_with(
            chat_id=12345,
            message_id=54321,
            text="Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
            parse_mode="HTML"
        )
        mock_update.message.delete.assert_called_once()
        assert result == 3


@pytest.mark.asyncio
async def test_set_limit_draft_not_found(mock_update, mock_context):
    """Тест случая, когда черновик не найден"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_limit import set_limit

        # Настройка тестовых данных
        test_limit = "10"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_limit
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path"}
        mock_context.bot = AsyncMock()

        # Мокируем функции БД
        with patch('src.event.create.set_limit.update_draft'), \
                patch('src.event.create.set_limit.get_draft') as mock_get_draft:
            mock_get_draft.return_value = None  # Черновик не найден

            # Вызываем тестируемую функцию
            result = await set_limit(mock_update, mock_context)

            # Проверки
            mock_update.message.reply_text.assert_called_once_with(
                "Ошибка: черновик мероприятия не найден."
            )
            assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_limit_event_creation_failed(mock_update, mock_context):
    """Тест случая, когда не удалось создать мероприятие"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_limit import set_limit

        # Настройка тестовых данных
        test_limit = "10"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_limit
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path", "db_path": "test_db_path"}
        mock_context.bot = AsyncMock()

        # Мокируем функции БД
        with patch('src.event.create.set_limit.update_draft'), \
                patch('src.event.create.set_limit.get_draft') as mock_get_draft, \
                patch('src.event.create.set_limit.add_event') as mock_add_event:
            mock_get_draft.return_value = {
                "description": "Тест",
                "date": "01.01.2023",
                "time": "12:00",
                "creator_id": 12345,
                "chat_id": 12345
            }
            mock_add_event.return_value = None  # Не удалось создать мероприятие

            # Вызываем тестируемую функцию
            result = await set_limit(mock_update, mock_context)

            # Проверки
            mock_update.message.reply_text.assert_called_once_with(
                "Ошибка при создании мероприятия."
            )
            assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_set_limit_message_send_failed(mock_update, mock_context):
    """Тест случая, когда не удалось отправить сообщение о мероприятии"""
    with patch('src.handlers.conversation_handler_states.SET_LIMIT', new='SET_LIMIT'):
        from temp.set_limit import set_limit

        # Настройка тестовых данных
        test_limit = "10"

        mock_update.message = MagicMock(spec=Message)
        mock_update.message.text = test_limit
        mock_update.message.chat_id = 12345
        mock_update.message.delete = AsyncMock()
        mock_update.message.reply_text = AsyncMock()

        mock_context.user_data = {
            "draft_id": 1,
            "bot_message_id": 54321
        }
        mock_context.bot_data = {"drafts_db_path": "test_db_path", "db_path": "test_db_path"}
        mock_context.bot = AsyncMock()

        # Мокируем функции БД и отправки сообщения
        with patch('src.event.create.set_limit.update_draft'), \
                patch('src.event.create.set_limit.get_draft') as mock_get_draft, \
                patch('src.event.create.set_limit.add_event') as mock_add_event, \
                patch('src.event.create.set_limit.send_event_message') as mock_send_event_message:
            mock_get_draft.return_value = {
                "description": "Тест",
                "date": "01.01.2023",
                "time": "12:00",
                "creator_id": 12345,
                "chat_id": 12345
            }
            mock_add_event.return_value = 1  # event_id
            mock_send_event_message.side_effect = Exception("Ошибка отправки")

            # Вызываем тестируемую функцию
            result = await set_limit(mock_update, mock_context)

            # Проверки
            mock_update.message.reply_text.assert_called_once_with(
                "Ошибка при создании мероприятия."
            )
            assert result == ConversationHandler.END