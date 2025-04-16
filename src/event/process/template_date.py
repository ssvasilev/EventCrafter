from datetime import datetime

from src.database.db_draft_operations import get_draft, delete_draft
from src.database.db_operations import add_event
from src.logger import logger
from src.message.send_event_creation_notification import send_event_creation_notification
from src.message.send_message import send_event_message
from src.utils.show_input_error import show_input_error


async def process_template_date(update, context, draft, date_input):
    """Обработка даты только для мероприятий из шаблонов"""
    try:
        # 1. Валидация даты
        datetime.strptime(date_input, "%d.%m.%Y").date()

        # 2. Явная загрузка свежих данных
        fresh_draft = get_draft(context.bot_data["drafts_db_path"], draft['id'])
        if not fresh_draft:
            raise ValueError("Черновик не найден")

        # 3. Проверка bot_message_id
        if not fresh_draft.get('bot_message_id'):
            logger.error("Отсутствует bot_message_id в черновике из шаблона")
            raise ValueError("Не найден ID сообщения")

        # 4. Создание мероприятия
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=fresh_draft['description'],
            date=date_input,
            time=fresh_draft['time'],
            limit=fresh_draft['participant_limit'],
            creator_id=update.message.from_user.id,
            chat_id=update.message.chat_id,
            message_id=fresh_draft['bot_message_id']
        )

        # 5. Отправка/редактирование сообщения
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=update.message.chat_id,
            message_id=fresh_draft['bot_message_id']
        )

        # 6. Очистка
        delete_draft(context.bot_data["drafts_db_path"], fresh_draft['id'])
        await update.message.delete()

        # 7. Отправляем уведомление создателю (используем общую функцию)
        await send_event_creation_notification(context, event_id, fresh_draft['bot_message_id'])

    except ValueError as e:
        logger.error(f"Ошибка в шаблонном сценарии: {e}")
        await show_input_error(update, context, f"❌ Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Критическая ошибка в шаблонном сценарии: {e}")
        await show_input_error(update, context, "⚠️ Ошибка создания мероприятия")