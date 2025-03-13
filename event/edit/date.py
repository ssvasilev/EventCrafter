from datetime import datetime, time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.db_operations import update_event_field, get_event
from handlers.conversation_handler_states import EDIT_DATE
from jobs.notification_jobs import remove_existing_notification_jobs, schedule_notifications
from message.send_message import send_event_message


# Обработка редактирования даты
async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите новую дату мероприятия в формате ДД.ММ.ГГГГ",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию EDIT_DATE
    return EDIT_DATE

# Обработка ввода новой даты
async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем новую дату
    date_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        # Преобразуем введённую дату
        date = datetime.strptime(date_text, "%d.%m.%Y").date()

        # Получаем время из context.user_data или из базы данных
        event = get_event(db_path, event_id)
        if not event:
            await update.message.reply_text("Мероприятие не найдено.")
            return ConversationHandler.END

        # Преобразуем время из строки в объект datetime.time
        event_time = datetime.strptime(event["time"], "%H:%M").time()

        # Форматируем дату с днём недели
        formatted_date = date.strftime("%d.%m.%Y (%A)")

        # Обновляем дату в базе данных
        update_event_field(db_path, event_id, "date", date.strftime("%d-%m-%Y"))

        # Сохраняем отформатированную дату в context.user_data
        context.user_data["formatted_date"] = formatted_date

        # Удаляем старые задачи на уведомления
        remove_existing_notification_jobs(event_id, context)

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Создаём объект datetime с учётом часового пояса
        event_datetime = datetime.combine(date, event_time)
        event_datetime = event_datetime.replace(tzinfo=tz)  # Устанавливаем часовой пояс

        # Создаём новые задачи на уведомления
        await schedule_notifications(event_id, context, event_datetime, update.message.chat_id)

        # Редактируем существующее сообщение с информацией о мероприятии
        await send_event_message(event_id, context, update.message.chat_id, context.user_data["bot_message_id"])

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError:
        # Если формат даты неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии EDIT_DATE
        return EDIT_DATE