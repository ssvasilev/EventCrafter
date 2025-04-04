from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, get_draft, delete_draft
from src.database.db_operations import (
    add_event,
    update_event_field,
    get_event,
    delete_scheduled_job
)
from src.jobs.notification_jobs import (
    schedule_notifications,
    schedule_unpin_and_delete,
    remove_existing_notification_jobs
)
from src.logger.logger import logger
from src.message.send_message import send_event_message
from src.handlers.conversation_handler_states import (
    SET_DATE, SET_TIME, SET_LIMIT,
    EDIT_DATE, EDIT_TIME, EDIT_LIMIT
)


async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода описания мероприятия.
    Сохраняет описание в черновик и переводит в состояние ожидания даты.
    """
    description = update.message.text
    draft_id = context.user_data["draft_id"]
    chat_id = update.message.chat_id

    try:
        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_DATE",
            description=description
        )

        # Создаем клавиатуру с кнопкой отмены
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем сообщение бота
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_DATE

    except Exception as e:
        logger.error(f"Ошибка при обработке описания: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте снова.")
        return ConversationHandler.END


async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода даты мероприятия.
    Проверяет формат даты и переводит в состояние ожидания времени.
    """
    date_text = update.message.text
    draft_id = context.user_data["draft_id"]
    chat_id = update.message.chat_id

    try:
        # Проверяем формат даты
        datetime.strptime(date_text, "%d.%m.%Y")

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_TIME",
            date=date_text
        )

        # Получаем данные черновика
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик не найден.")
            return ConversationHandler.END

        # Создаем клавиатуру с кнопкой отмены
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем сообщение бота
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_TIME

    except ValueError:
        # Если формат даты неверный
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return SET_DATE


async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода времени мероприятия.
    Проверяет формат времени и переводит в состояние ожидания лимита участников.
    """
    time_text = update.message.text
    draft_id = context.user_data["draft_id"]
    chat_id = update.message.chat_id

    try:
        # Проверяем формат времени
        datetime.strptime(time_text, "%H:%M")

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_LIMIT",
            time=time_text
        )

        # Получаем данные черновика
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик не найден.")
            return ConversationHandler.END

        # Создаем клавиатуру с кнопкой отмены
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем сообщение бота
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
            reply_markup=reply_markup,
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_LIMIT

    except ValueError:
        # Если формат времени неверный
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return SET_TIME


async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода лимита участников.
    Создает мероприятие в основной базе и завершает процесс создания.
    """
    limit_text = update.message.text
    draft_id = context.user_data["draft_id"]
    chat_id = update.message.chat_id

    try:
        # Проверяем и преобразуем лимит
        limit = int(limit_text)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="DONE",
            participant_limit=limit
        )

        # Получаем данные черновика
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик не найден.")
            return ConversationHandler.END

        # Создаем мероприятие в основной базе
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=draft["description"],
            date=draft["date"],
            time=draft["time"],
            limit=limit if limit != 0 else None,
            creator_id=draft["creator_id"],
            chat_id=draft["chat_id"],
            message_id=None  # Будет обновлено после отправки сообщения
        )

        if not event_id:
            raise Exception("Не удалось создать мероприятие")

        # Отправляем сообщение о мероприятии
        message_id = await send_event_message(event_id, context, chat_id)

        # Обновляем message_id мероприятия
        update_event_field(context.bot_data["db_path"], event_id, "message_id", message_id)

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Планируем уведомления
        event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=context.bot_data["tz"])

        await schedule_notifications(event_id, context, event_datetime, chat_id)
        await schedule_unpin_and_delete(event_id, context, chat_id)

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Очищаем user_data
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        # Если введен неверный формат лимита
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return SET_LIMIT

    except Exception as e:
        logger.error(f"Ошибка при создании мероприятия: {e}")
        await update.message.reply_text("Произошла ошибка при создании мероприятия.")
        return ConversationHandler.END


async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохраняет новое описание мероприятия при редактировании.
    """
    new_description = update.message.text
    event_id = context.user_data["event_id"]
    chat_id = update.message.chat_id

    try:
        # Обновляем описание в базе данных
        update_event_field(
            db_path=context.bot_data["db_path"],
            event_id=event_id,
            field="description",
            value=new_description
        )

        # Редактируем сообщение с мероприятием
        await send_event_message(
            event_id,
            context,
            chat_id,
            context.user_data["bot_message_id"]
        )

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при обновлении описания: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении описания.")
        return ConversationHandler.END


async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохраняет новую дату мероприятия при редактировании.
    Обновляет запланированные уведомления.
    """
    date_text = update.message.text
    event_id = context.user_data["event_id"]
    chat_id = update.message.chat_id

    try:
        # Проверяем формат даты
        datetime.strptime(date_text, "%d.%m.%Y")

        # Получаем данные о мероприятии
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await update.message.reply_text("Мероприятие не найдено.")
            return ConversationHandler.END

        # Обновляем дату в базе данных
        update_event_field(
            db_path=context.bot_data["db_path"],
            event_id=event_id,
            field="date",
            value=date_text
        )

        # Удаляем старые задачи уведомлений
        remove_existing_notification_jobs(event_id, context)
        delete_scheduled_job(context.bot_data["db_path"], event_id, job_type="unpin_delete")

        # Создаем новые задачи уведомлений
        event_time = datetime.strptime(event["time"], "%H:%M").time()
        event_datetime = datetime.combine(
            datetime.strptime(date_text, "%d.%m.%Y").date(),
            event_time
        ).replace(tzinfo=context.bot_data["tz"])

        await schedule_notifications(event_id, context, event_datetime, chat_id)
        await schedule_unpin_and_delete(event_id, context, chat_id)

        # Редактируем сообщение с мероприятием
        await send_event_message(
            event_id,
            context,
            chat_id,
            context.user_data["bot_message_id"]
        )

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return ConversationHandler.END

    except ValueError:
        # Если формат даты неверный
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return EDIT_DATE


async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохраняет новое время мероприятия при редактировании.
    Обновляет запланированные уведомления.
    """
    time_text = update.message.text
    event_id = context.user_data["event_id"]
    chat_id = update.message.chat_id

    try:
        # Проверяем формат времени
        datetime.strptime(time_text, "%H:%M")

        # Получаем данные о мероприятии
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await update.message.reply_text("Мероприятие не найдено.")
            return ConversationHandler.END

        # Обновляем время в базе данных
        update_event_field(
            db_path=context.bot_data["db_path"],
            event_id=event_id,
            field="time",
            value=time_text
        )

        # Удаляем старые задачи уведомлений
        remove_existing_notification_jobs(event_id, context)
        delete_scheduled_job(context.bot_data["db_path"], event_id, job_type="unpin_delete")

        # Создаем новые задачи уведомлений
        event_date = datetime.strptime(event["date"], "%d.%m.%Y").date()
        event_datetime = datetime.combine(
            event_date,
            datetime.strptime(time_text, "%H:%M").time()
        ).replace(tzinfo=context.bot_data["tz"])

        await schedule_notifications(event_id, context, event_datetime, chat_id)
        await schedule_unpin_and_delete(event_id, context, chat_id)

        # Редактируем сообщение с мероприятием
        await send_event_message(
            event_id,
            context,
            chat_id,
            context.user_data["bot_message_id"]
        )

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return ConversationHandler.END

    except ValueError:
        # Если формат времени неверный
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return EDIT_TIME


async def save_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохраняет новый лимит участников при редактировании.
    """
    limit_text = update.message.text
    event_id = context.user_data["event_id"]
    chat_id = update.message.chat_id

    try:
        # Проверяем и преобразуем лимит
        limit = int(limit_text)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Обновляем лимит в базе данных
        update_event_field(
            db_path=context.bot_data["db_path"],
            event_id=event_id,
            field="participant_limit",
            value=limit if limit != 0 else None
        )

        # Редактируем сообщение с мероприятием
        await send_event_message(
            event_id,
            context,
            chat_id,
            context.user_data["bot_message_id"]
        )

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return ConversationHandler.END

    except ValueError:
        # Если введен неверный формат лимита
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass
        return EDIT_LIMIT