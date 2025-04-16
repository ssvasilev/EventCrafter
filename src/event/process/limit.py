from datetime import datetime

from telegram.error import BadRequest

from config import tz
from src.database.db_draft_operations import get_draft, delete_draft
from src.database.db_operations import add_event
from src.jobs.notification_jobs import schedule_notifications, schedule_unpin_and_delete, logger
from src.message.send_event_creation_notification import send_event_creation_notification
from src.message.send_message import send_event_message
from src.utils.show_input_error import show_input_error


async def process_limit(update, context, draft, limit_input):
    """Обработка шага ввода лимита участников"""
    try:
        limit = int(limit_input)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Получаем актуальный bot_message_id
        updated_draft = get_draft(context.bot_data["drafts_db_path"], draft["id"])
        bot_message_id = updated_draft.get("bot_message_id") if updated_draft else None

        # Создаем мероприятие
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=draft["description"],
            date=draft["date"],
            time=draft["time"],
            limit=limit if limit != 0 else None,
            creator_id=update.message.from_user.id,
            chat_id=update.message.chat_id,
            message_id=bot_message_id
        )

        if not event_id:
            raise Exception("Не удалось создать мероприятие")

        # Редактируем сообщение с информацией о мероприятии
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=update.message.chat_id,
            message_id=bot_message_id
        )

        # Планируем уведомления
        event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=tz)

        await schedule_notifications(
            event_id=event_id,
            context=context,
            event_datetime=event_datetime,
            chat_id=update.message.chat_id
        )

        await schedule_unpin_and_delete(
            event_id=event_id,
            context=context,
            chat_id=update.message.chat_id
        )

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        # Отправляем уведомление создателю
        await send_event_creation_notification(context, event_id, bot_message_id)

    except ValueError:
        await show_input_error(
            update, context,
            "❌ Лимит должен быть целым числом ≥ 0 (0 - без лимита)"
        )
    except Exception as e:
        logger.error(f"Ошибка создания мероприятия: {e}")
        await show_input_error(
            update, context,
            "⚠️ Произошла ошибка при создании мероприятия"
        )