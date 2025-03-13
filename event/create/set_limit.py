from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data.database import add_event
from jobs.notification_jobs import unpin_and_delete_event, send_notification
from message.send_message import send_event_message

from handlers.conversation_handler_states import SET_LIMIT

# Обработка ввода лимита участников
async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст сообщения с лимитом участников
    limit_text = update.message.text
    try:
        # Преобразуем введённый текст в число
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Получаем данные мероприятия из context.user_data
        description = context.user_data.get("description")
        date = context.user_data.get("date")
        time = context.user_data.get("time")
        creator_id = update.message.from_user.id
        chat_id = update.message.chat_id

        # Проверяем, что все необходимые данные есть
        if not all([description, date, time, creator_id, chat_id]):
            await update.message.reply_text("Ошибка: недостаточно данных для создания мероприятия.")
            return ConversationHandler.END

        # Создаём мероприятие в базе данных
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=description,
            date=date.strftime("%d-%m-%Y"),  # Преобразуем дату в строку
            time=time.strftime("%H:%M"),     # Преобразуем время в строку
            limit=limit if limit != 0 else None,  # Лимит участников (0 -> None)
            creator_id=creator_id,
            chat_id=chat_id,
            message_id=None  # message_id будет обновлён после отправки сообщения
        )

        # Проверяем, что мероприятие успешно создано
        if not event_id:
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Сохраняем event_id в context.user_data для дальнейшего использования
        context.user_data["event_id"] = event_id

        # Удаляем последнее сообщение бота с параметрами мероприятия
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, chat_id)

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Планируем задачи для уведомлений и удаления мероприятия
        event_datetime = datetime.strptime(f"{date.strftime('%d-%m-%Y')} {time.strftime('%H:%M')}", "%d-%m-%Y %H:%M")
        event_datetime = tz.localize(event_datetime)  # Устанавливаем часовой пояс

        # Уведомление за день до мероприятия
        context.job_queue.run_once(
            send_notification,
            when=event_datetime - timedelta(days=1),
            data={"event_id": event_id, "time_until": "1 день"},
        )

        # Уведомление за 15 минут до мероприятия
        context.job_queue.run_once(
            send_notification,
            when=event_datetime - timedelta(minutes=15),
            data={"event_id": event_id, "time_until": "15 минут"},
        )

        # Задача для открепления и удаления мероприятия после его завершения
        context.job_queue.run_once(
            unpin_and_delete_event,
            when=event_datetime,
            data={"event_id": event_id, "chat_id": chat_id},
        )

        # Завершаем диалог
        context.user_data.clear()  # Очищаем user_data
        return ConversationHandler.END

    except ValueError as e:
        # Если введённый текст не является числом или лимит отрицательный
        error_message = (
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )

        # Редактируем существующее сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=error_message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
            parse_mode="HTML"
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_LIMIT
        return SET_LIMIT