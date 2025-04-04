from datetime import datetime, timedelta
from telegram.ext import ContextTypes, Application
from telegram.error import BadRequest
from src.database.db_operations import get_event, delete_event, get_scheduled_job_id, delete_scheduled_job, \
    add_scheduled_job, get_participants, get_db_connection
from src.logger.logger import logger

async def send_notification(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет уведомление участникам мероприятия."""
    event_id = context.job.data["event_id"]
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    participants = get_participants(db_path, event_id)
    if not participants:
        logger.info(f"Нет участников для мероприятия с ID {event_id}.")
        return

    # Формируем текст уведомления
    message = (
        f"⏰ Напоминание о мероприятии:\n"
        f"📢 {event['description']}\n"
        f"📅 Дата: {event['date']}\n"
        f"🕒 Время: {event['time']}"
    )

    # Отправляем уведомление каждому участнику
    for participant in participants:
        try:
            await context.bot.send_message(
                chat_id=participant["user_id"],
                text=message
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления участнику {participant['user_id']}: {e}")

async def unpin_and_delete_event(context: ContextTypes.DEFAULT_TYPE):
    """Открепляет сообщение мероприятия и удаляет его из базы данных."""
    event_id = context.job.data["event_id"]
    chat_id = context.job.data["chat_id"]
    db_path = context.bot_data["db_path"]

    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    try:
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=event["message_id"])
    except BadRequest as e:
        logger.error(f"Ошибка при откреплении сообщения: {e}")

    delete_event(db_path, event_id)
    delete_scheduled_job(db_path, event_id, job_type="unpin_delete")

async def schedule_notifications(event_id: int, context: ContextTypes.DEFAULT_TYPE, event_datetime: datetime, chat_id: int):
    """Создаёт задачи для уведомлений."""
    db_path = context.bot_data["db_path"]

    # Уведомление за сутки
    job_day = context.job_queue.run_once(
        send_notification,
        when=event_datetime - timedelta(days=1),
        data={"event_id": event_id, "time_until": "1 день"},
        name=f"notification_{event_id}_day"
    )

    # Уведомление за 15 минут
    job_minutes = context.job_queue.run_once(
        send_notification,
        when=event_datetime - timedelta(minutes=15),
        data={"event_id": event_id, "time_until": "15 минут"},
        name=f"notification_{event_id}_minutes"
    )

    # Сохраняем задачи в базу данных
    add_scheduled_job(
        db_path, event_id, job_day.id, chat_id,
        (event_datetime - timedelta(days=1)).isoformat(),
        job_type="notification_day"
    )
    add_scheduled_job(
        db_path, event_id, job_minutes.id, chat_id,
        (event_datetime - timedelta(minutes=15)).isoformat(),
        job_type="notification_minutes"
    )

async def schedule_unpin_and_delete(event_id: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Создаёт задачу для открепления и удаления мероприятия."""
    db_path = context.bot_data["db_path"]

    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    try:
        event_datetime = datetime.strptime(f"{event['date']} {event['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=context.bot_data["tz"])
    except ValueError as e:
        logger.error(f"Ошибка при обработке даты и времени мероприятия: {e}")
        return

    job = context.job_queue.run_once(
        unpin_and_delete_event,
        when=event_datetime,
        data={"event_id": event_id, "chat_id": chat_id},
        name=f"unpin_delete_{event_id}"
    )

    add_scheduled_job(
        db_path, event_id, job.id, chat_id,
        event_datetime.isoformat(),
        job_type="unpin_delete"
    )

def remove_existing_notification_jobs(event_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет существующие задачи напоминания для мероприятия."""
    db_path = context.bot_data["db_path"]

    # Удаляем задачи из JobQueue
    jobs = context.job_queue.get_jobs_by_name(f"notification_{event_id}")
    for job in jobs:
        job.schedule_removal()

    # Удаляем задачи из базы данных
    delete_scheduled_job(db_path, event_id, job_type="notification_day")
    delete_scheduled_job(db_path, event_id, job_type="notification_minutes")

def restore_scheduled_jobs(application: Application):
    """Восстанавливает запланированные задачи из базы данных при запуске бота."""
    db_path = application.bot_data["db_path"]
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_jobs")
        jobs = cursor.fetchall()

        for job in jobs:
            event_id = job["event_id"]
            chat_id = job["chat_id"]
            execute_at = datetime.fromisoformat(job["execute_at"])

            if execute_at.tzinfo is None:
                execute_at = application.bot_data["tz"].localize(execute_at)

            if execute_at > datetime.now(application.bot_data["tz"]):
                if job["job_type"] == "unpin_delete":
                    application.job_queue.run_once(
                        unpin_and_delete_event,
                        when=execute_at,
                        data={"event_id": event_id, "chat_id": chat_id},
                        name=f"unpin_delete_{event_id}"
                    )
                elif job["job_type"] == "notification_day":
                    application.job_queue.run_once(
                        send_notification,
                        when=execute_at,
                        data={"event_id": event_id, "time_until": "1 день"},
                        name=f"notification_{event_id}_day"
                    )
                elif job["job_type"] == "notification_minutes":
                    application.job_queue.run_once(
                        send_notification,
                        when=execute_at,
                        data={"event_id": event_id, "time_until": "15 минут"},
                        name=f"notification_{event_id}_minutes"
                    )
                logger.info(f"Восстановлена задача для мероприятия с ID: {event_id}")
            else:
                cursor.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job["id"],))
                conn.commit()