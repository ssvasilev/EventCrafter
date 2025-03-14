from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.db_operations import update_draft, add_event
from jobs.notification_jobs import unpin_and_delete_event, send_notification
from message.send_message import send_event_message

from handlers.conversation_handler_states import SET_LIMIT

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст лимита участников
    limit_text = update.message.text
    try:
        # Преобразуем введённый текст в число
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Обновляем черновик
        draft_id = context.user_data["draft_id"]
        update_draft(
            db_path=context.bot_data["db_path"],
            draft_id=draft_id,
            status="DONE",
            participant_limit=limit
        )

        # Получаем данные черновика
        draft = get_draft(context.bot_data["db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик мероприятия не найден.")
            return ConversationHandler.END

        # Создаем мероприятие в основной базе данных
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=draft["description"],
            date=draft["date"],
            time=draft["time"],
            limit=limit if limit != 0 else None,
            creator_id=draft["creator_id"],
            chat_id=draft["chat_id"],
            message_id=None
        )

        # Проверяем, что мероприятие успешно создано
        if not event_id:
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Удаляем черновик
        delete_draft(context.bot_data["db_path"], draft_id)

        # Удаляем последнее сообщение бота с параметрами мероприятия
        await context.bot.delete_message(
            chat_id=draft["chat_id"],
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, draft["chat_id"])

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Планируем задачи для уведомлений и удаления мероприятия
        event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=tz)

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
            data={"event_id": event_id, "chat_id": draft["chat_id"]},
        )

        # Завершаем диалог
        context.user_data.clear()
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