from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.handlers.conversation_handler_states import SET_TIME, SET_DATE
from src.database.db_draft_operations import update_draft, get_draft

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст даты
    date_text = update.message.text
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()

        # Получаем ID черновика из user_data
        draft_id = context.user_data["draft_id"]

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_TIME",
            date=date.strftime("%d.%m.%Y")
        )

        # Получаем данные черновика из базы данных
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик мероприятия не найден.")
            return ConversationHandler.END

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Переходим к состоянию SET_TIME
        return SET_TIME
    except ValueError:
        # Если формат даты неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Остаемся в состоянии SET_DATE
        return SET_DATE

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.database.db_operations import update_event_field, get_event, delete_scheduled_job
from src.handlers.conversation_handler_states import EDIT_DATE
from src.jobs.notification_jobs import remove_existing_notification_jobs, schedule_notifications, \
    schedule_unpin_and_delete
from src.logger.logger import logger
from src.message.send_message import send_event_message

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

        # Получаем данные о мероприятии из базы данных
        event = get_event(db_path, event_id)
        if not event:
            await update.message.reply_text("Мероприятие не найдено.")
            return ConversationHandler.END

        # Преобразуем время из строки в объект datetime.time
        event_time = datetime.strptime(event["time"], "%H:%M").time()

        # Обновляем дату в базе данных
        update_event_field(db_path, event_id, "date", date.strftime("%d.%m.%Y"))  # Используем новый формат

        # Удаляем старые задачи на уведомления и открепление
        remove_existing_notification_jobs(event_id, context)
        delete_scheduled_job(context.bot_data["db_path"], event_id, job_type="unpin_delete")

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Создаём объект datetime с учётом часового пояса
        event_datetime = datetime.combine(date, event_time)
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
    except BadRequest as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении даты.")
        return ConversationHandler.END