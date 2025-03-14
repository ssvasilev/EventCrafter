from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from database.db_operations import set_user_state, get_user_state, add_event, clear_user_state
from jobs.notification_jobs import unpin_and_delete_event, send_notification
from message.send_message import send_event_message
from handlers.conversation_handler_states import SET_LIMIT
from logger.logger import logger

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    limit_text = update.message.text

    try:
        # Преобразуем введённый текст в число
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Получаем текущее состояние пользователя
        user_state = get_user_state(context.bot_data["db_path"], user_id)
        if not user_state:
            await update.message.reply_text("Ошибка: состояние пользователя не найдено.")
            return ConversationHandler.END

        # Проверяем, что message_id существует
        if "bot_message_id" not in user_state:
            await update.message.reply_text("Ошибка: ID сообщения не найдено.")
            return ConversationHandler.END

        # Логируем message_id перед редактированием
        logger.info(f"Редактируем сообщение с ID: {user_state['bot_message_id']}")

        # Создаём мероприятие в базе данных
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=user_state["description"],
            date=user_state["date"],
            time=user_state["time"],
            limit=limit if limit != 0 else None,  # Лимит участников (0 -> None)
            creator_id=user_id,
            chat_id=chat_id,
            message_id=user_state.get("bot_message_id")  # Используем message_id из user_state
        )

        # Проверяем, что мероприятие успешно создано
        if not event_id:
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        """
        # Удаляем последнее сообщение бота с параметрами мероприятия
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=user_state["bot_message_id"]
        )
        """

        # Отправляем новое сообщение с информацией о мероприятии
        new_message = await send_event_message(
            event_id=event_id,
            chat_id=chat_id,
            db_path=context.bot_data["db_path"],  # Путь к базе данных
            tz=context.bot_data["tz"],           # Часовой пояс
        )

        # Обновляем message_id в базе данных
        set_user_state(
            db_path=context.bot_data["db_path"],
            user_id=user_id,
            chat_id=chat_id,
            state="SET_LIMIT",
            bot_message_id=new_message.message_id,  # Сохраняем новый message_id
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Планируем задачи для уведомлений и удаления мероприятия
        event_datetime = datetime.strptime(f"{user_state['date']} {user_state['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=tz)  # Устанавливаем часовой пояс

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

        # Очищаем состояние пользователя
        clear_user_state(context.bot_data["db_path"], user_id)

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError as e:
        # Если введённый текст не является числом или лимит отрицательный
        error_message = (
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )

        # Получаем текущее состояние пользователя
        user_state = get_user_state(context.bot_data["db_path"], user_id)
        if not user_state:
            await update.message.reply_text("Ошибка: состояние пользователя не найдено.")
            return ConversationHandler.END

        # Проверяем, что message_id существует
        if "bot_message_id" not in user_state:
            await update.message.reply_text("Ошибка: ID сообщения не найдено.")
            return ConversationHandler.END

        try:
            # Редактируем существующее сообщение бота с ошибкой
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_state["bot_message_id"],
                text=error_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
                parse_mode="HTML"
            )
        except BadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await update.message.reply_text("Не удалось обновить сообщение. Пожалуйста, начните заново.")
            return ConversationHandler.END

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_LIMIT
        return SET_LIMIT