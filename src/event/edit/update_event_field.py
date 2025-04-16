from datetime import datetime

from config import tz
from src.database.db_operations import get_event
from src.event.edit.final_edit import finalize_edit

from src.jobs.notification_jobs import remove_existing_notification_jobs, remove_existing_job, schedule_notifications, \
    schedule_unpin_and_delete
from src.logger import logger
from src.utils.show_input_error import show_input_error


async def update_event_field(context, draft, field, value):
    """Обновляет поле мероприятия"""
    from src.database.db_operations import update_event_field

    # Обновляем поле в базе данных
    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field=field,
        value=value
    )

    # Если обновляется дата или время, пересоздаем задачи уведомлений
    if field in ["date", "time"]:
        # Удаляем старые задачи
        remove_existing_notification_jobs(draft["event_id"], context)
        remove_existing_job(draft["event_id"], context)  # Для задачи открепления

        # Получаем новые дату и время
        event = get_event(context.bot_data["db_path"], draft["event_id"])
        if event:
            try:
                event_datetime = datetime.strptime(
                    f"{event['date']} {event['time']}",
                    "%d.%m.%Y %H:%M"
                ).replace(tzinfo=tz)

                # Создаем новые задачи
                await schedule_notifications(
                    event_id=draft["event_id"],
                    context=context,
                    event_datetime=event_datetime,
                    chat_id=draft["chat_id"]
                )

                await schedule_unpin_and_delete(
                    event_id=draft["event_id"],
                    context=context,
                    chat_id=draft["chat_id"]
                )
            except ValueError as e:
                logger.error(f"Ошибка при обработке новой даты/времени: {e}")

    await finalize_edit(context, draft)

async def validate_and_update(update, context, draft, field, value, fmt, error_hint):
    """Проверяет формат и обновляет поле с унифицированным выводом ошибок"""
    try:
        datetime.strptime(value, fmt)  # Валидация формата
        await update_event_field(context, draft, field, value)
    except ValueError:
        await show_input_error(
            update, context,
            f"❌ Неверный формат {field}. Используйте {error_hint}"
        )
