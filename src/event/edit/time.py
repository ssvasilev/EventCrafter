from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.database.db_operations import update_event_field, get_event
from src.handlers.conversation_handler_states import EDIT_TIME
from src.jobs.notification_jobs import remove_existing_notification_jobs, schedule_notifications, \
    schedule_unpin_and_delete
from src.logger.logger import logger
from src.message.send_message import send_event_message

# Обработка ввода нового времени
async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем новое время
    time_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        # Преобразуем введённое время
        time_obj = datetime.strptime(time_text, "%H:%M").time()

        # Получаем данные о мероприятии из базы данных
        event = get_event(db_path, event_id)
        if not event:
            await update.message.reply_text("Мероприятие не найдено.")
            return ConversationHandler.END

        # Преобразуем дату из строки в объект datetime.date
        date = datetime.strptime(event["date"], "%d.%m.%Y").date()

        # Обновляем время в базе данных
        update_event_field(db_path, event_id, "time", time_obj.strftime("%H:%M"))

        # Удаляем старые задачи на уведомления
        remove_existing_notification_jobs(event_id, context)

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Создаём объект datetime с учётом часового пояса
        event_datetime = datetime.combine(date, time_obj)
        event_datetime = event_datetime.replace(tzinfo=tz)

        # Создаём новые задачи на уведомления
        await schedule_notifications(event_id, context, event_datetime, update.message.chat_id)

        # Создаём новую задачу для открепления и удаления
        await schedule_unpin_and_delete(event_id, context, update.message.chat_id)

        # Редактируем существующее сообщение с информацией о мероприятии
        await send_event_message(event_id, context, update.message.chat_id, context.user_data["bot_message_id"])

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END
    except ValueError:
        # Если формат времени неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии EDIT_TIME
        return EDIT_TIME
    except BadRequest as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении времени.")
        return ConversationHandler.END