from datetime import datetime, timedelta

from telegram.ext import ContextTypes, Application

from config import tz
from src.database.db_operations import (
    get_event, delete_event, get_scheduled_job_id, delete_scheduled_job, add_scheduled_job, get_db_connection
)
from src.utils.utils import time_until_event
import logging

logger = logging.getLogger(__name__)

async def send_notification(context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет уведомление участникам мероприятия.
    :param context: Контекст задачи.
    """
    event_id = context.job.data["event_id"]
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    # Получаем участников мероприятия
    participants = event.get("participants", [])
    if not participants:
        logger.info(f"Нет участников для мероприятия с ID {event_id}.")
        return

    # Получаем часовой пояс из context.bot_data
    tz = context.bot_data.get("tz")

    # Форматируем дату с днём недели
    try:
        date = datetime.strptime(event["date"], "%d.%m.%Y").date()  # Используем формат "%d.%m.%Y"
        formatted_date = date.strftime("%d.%m.%Y (%A)")  # %A — полное название дня недели
    except ValueError as e:
        logger.error(f"Ошибка при обработке даты мероприятия: {e}")
        return

    # Преобразуем chat_id для ссылки
    chat_id = event["chat_id"]
    if str(chat_id).startswith("-100"):  # Для супергрупп и каналов
        chat_id_link = int(str(chat_id)[4:])  # Убираем "-100" в начале
    else:
        chat_id_link = chat_id  # Для обычных групп и личных чатов

    # Формируем ссылку на мероприятие
    event_link = f"https://t.me/c/{chat_id_link}/{event['message_id']}"

    # Формируем текст уведомления с кликабельным названием мероприятия
    time_until = time_until_event(event["date"], event["time"], tz)
    message = (
        f"⏰ Напоминание о мероприятии:\n"
        f"📢 <a href='{event_link}'>{event['description']}</a>\n"
        f"📅 <i>Дата: </i> {formatted_date}\n"
        f"🕒 <i>Время: </i> {event['time']}\n"
        f"⏳ <i>До мероприятия: </i> {time_until}"
    )

    # Отправляем уведомление каждому участнику
    for participant in participants:
        try:
            # Используем user_id, если user_name отсутствует
            user_name = participant.get("user_name", f"пользователь с ID {participant['user_id']}")
            await context.bot.send_message(
                chat_id=participant["user_id"],
                text=message,
                parse_mode="HTML"
            )
            logger.info(f"Уведомление отправлено участнику {user_name}.")
        except Exception as e:
            user_name = participant.get("user_name", f"пользователь с ID {participant['user_id']}")
            logger.error(f"Ошибка при отправке уведомления участнику {user_name}: {e}")


async def unpin_and_delete_event(context: ContextTypes.DEFAULT_TYPE):
    """
    Открепляет сообщение мероприятия и удаляет его из базы данных.
    :param context: Контекст задачи.
    """
    event_id = context.job.data["event_id"]
    chat_id = context.job.data["chat_id"]
    db_path = context.bot_data["db_path"]

    # Получаем данные о мероприятии
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    # Открепляем сообщение
    try:
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=event["message_id"])
        logger.info(f"Сообщение {event['message_id']} откреплено в чате {chat_id}.")
    except Exception as e:
        logger.error(f"Ошибка при откреплении сообщения: {e}")

    # Удаляем мероприятие из базы данных
    delete_event(db_path, event_id)
    logger.info(f"Мероприятие с ID {event_id} удалено из базы данных.")

    # Удаляем задачу из базы данных
    delete_scheduled_job(db_path, event_id, job_type="unpin_delete")
    logger.info(f"Задача unpin_delete для мероприятия {event_id} удалена из базы данных.")


async def schedule_notifications(event_id: int, context: ContextTypes.DEFAULT_TYPE, event_datetime: datetime, chat_id: int):
    """
    Создаёт задачи для уведомлений за сутки и за 15 минут до мероприятия.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    :param event_datetime: Дата и время мероприятия.
    :param chat_id: ID чата, в котором создано мероприятие.
    """
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
    add_scheduled_job(db_path, event_id, job_day.id, chat_id, (event_datetime - timedelta(days=1)).isoformat(), job_type="notification_day")
    add_scheduled_job(db_path, event_id, job_minutes.id, chat_id, (event_datetime - timedelta(minutes=15)).isoformat(), job_type="notification_minutes")

    logger.info(f"Созданы новые задачи напоминания для мероприятия {event_id}.")


async def schedule_unpin_and_delete(event_id: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    Создаёт задачу для открепления и удаления мероприятия после его завершения.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    :param chat_id: ID чата, в котором создано мероприятие.
    """
    db_path = context.bot_data["db_path"]

    # Получаем данные о мероприятии
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    # Преобразуем дату и время мероприятия
    try:
        event_datetime = datetime.strptime(f"{event['date']} {event['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=tz)  # Устанавливаем часовой пояс
    except ValueError as e:
        logger.error(f"Ошибка при обработке даты и времени мероприятия: {e}")
        return

    # Создаём задачу
    job = context.job_queue.run_once(
        unpin_and_delete_event,
        when=event_datetime,
        data={"event_id": event_id, "chat_id": chat_id},
        name=f"unpin_delete_{event_id}"
    )

    # Сохраняем задачу в базу данных
    add_scheduled_job(db_path, event_id, job.id, chat_id, event_datetime.isoformat(), job_type="unpin_delete")
    logger.info(f"Создана задача для открепления и удаления мероприятия {event_id}.")


def remove_existing_job(event_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет существующую задачу для мероприятия, если она есть.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    """
    db_path = context.bot_data["db_path"]

    # Удаляем задачу из JobQueue по корректному имени
    jobs = context.job_queue.get_jobs_by_name(f"unpin_delete_{event_id}")
    if jobs:
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Удалена старая задача {job.id} для мероприятия {event_id}")

        # Удаляем запись из базы по типу задачи
        delete_scheduled_job(db_path, event_id, job_type="unpin_delete")
        logger.info(f"Задача unpin_delete для мероприятия {event_id} удалена из базы данных.")
    else:
        logger.warning(f"Задача unpin_delete для мероприятия {event_id} не найдена в очереди.")


def remove_existing_notification_jobs(event_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет существующие задачи напоминания для мероприятия.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    """
    db_path = context.bot_data["db_path"]

    # Удаляем задачи из JobQueue по корректным именам
    for name in (f"notification_{event_id}_day", f"notification_{event_id}_minutes"):
        jobs = context.job_queue.get_jobs_by_name(name)
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Удалена задача напоминания {job.id} для мероприятия {event_id}")

    # Удаляем задачи из базы данных
    delete_scheduled_job(db_path, event_id, job_type="notification_day")
    delete_scheduled_job(db_path, event_id, job_type="notification_minutes")
    logger.info(f"Задачи напоминания для мероприятия {event_id} удалены из базы данных.")


def restore_scheduled_jobs(application: Application):
    """
    Восстанавливает запланированные задачи из базы данных при запуске бота.
    :param application: Приложение бота.
    """
    db_path = application.bot_data["db_path"]
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_jobs")
        jobs = cursor.fetchall()

        for job in jobs:
            event_id = job["event_id"]
            chat_id = job["chat_id"]
            execute_at = datetime.fromisoformat(job["execute_at"])

            # Преобразуем execute_at в offset-aware, если он offset-naive
            if execute_at.tzinfo is None:
                execute_at = tz.localize(execute_at)

            # Проверяем, не истекло ли время выполнения задачи
            if execute_at > datetime.now(tz):
                # Создаем задачу в зависимости от её типа
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
                # Если время выполнения задачи истекло, удаляем её из базы данных
                cursor.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job["id"],))
                conn.commit()
                logger.info(f"Удалена устаревшая задача для мероприятия с ID: {event_id}")