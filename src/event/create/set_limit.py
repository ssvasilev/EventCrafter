from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.database.db_operations import add_event, update_event_field, add_scheduled_job
from src.database.db_draft_operations import update_draft, get_draft, delete_draft
from src.jobs.notification_jobs import unpin_and_delete_event, send_notification
from src.logger.logger import logger
from src.message.send_message import send_event_message

from src.handlers.conversation_handler_states import SET_LIMIT

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст лимита участников
    limit_text = update.message.text
    try:
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Получаем ID черновика из user_data
        draft_id = context.user_data["draft_id"]

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="DONE",
            participant_limit=limit
        )

        # Получаем данные черновика из базы данных
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
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
            message_id=None  # message_id будет обновлён после отправки сообщения
        )

        if not event_id:
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Отправляем сообщение о мероприятии и получаем его message_id
        try:
            message_id = await send_event_message(event_id, context, draft["chat_id"])
            # Обновляем мероприятие с message_id
            update_event_field(context.bot_data["db_path"], event_id, "message_id", message_id)
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о мероприятии: {e}")
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Уведомляем создателя об успешном создании мероприятия
        try:
            # Преобразуем chat_id для ссылки
            chat_id = draft["chat_id"]
            if str(chat_id).startswith("-100"):  # Для супергрупп и каналов
                chat_id_link = int(str(chat_id)[4:])  # Убираем "-100" в начале
            else:
                chat_id_link = chat_id  # Для обычных групп и личных чатов

            # Формируем ссылку на мероприятие
            event_link = f"https://t.me/c/{chat_id_link}/{message_id}"

            # Формируем текст уведомления с кликабельным названием мероприятия
            message = (
                f"✅ Мероприятие успешно создано!\n\n"
                f"📢 <a href='{event_link}'>{draft['description']}</a>\n"
                f"📅 Дата: {draft['date']}\n"
                f"🕒 Время: {draft['time']}"
            )

            # Отправляем уведомление создателю
            await context.bot.send_message(
                chat_id=draft["creator_id"],
                text=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления создателю: {e}")

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Удаляем последнее сообщение бота с параметрами мероприятия
        try:
            await context.bot.delete_message(
                chat_id=draft["chat_id"],
                message_id=context.user_data["bot_message_id"]
            )
        except BadRequest as e:
            logger.warning(f"Сообщение для удаления не найдено: {e}")

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Сообщение пользователя не найдено: {e}")

        # Получаем часовой пояс из context.bot_data
        tz = context.bot_data["tz"]

        # Планируем задачи для уведомлений и удаления мероприятия
        event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=tz)

        # Уведомление за день до мероприятия
        job_day = context.job_queue.run_once(
            send_notification,
            when=event_datetime - timedelta(days=1),
            data={"event_id": event_id, "time_until": "1 день"},
            name=f"notification_{event_id}_day"
        )

        # Уведомление за 15 минут до мероприятия
        job_minutes = context.job_queue.run_once(
            send_notification,
            when=event_datetime - timedelta(minutes=15),
            data={"event_id": event_id, "time_until": "15 минут"},
            name=f"notification_{event_id}_minutes"
        )

        # Планируем задачу для открепления и удаления мероприятия после его завершения
        job_unpin = context.job_queue.run_once(
            unpin_and_delete_event,
            when=event_datetime,
            data={"event_id": event_id, "chat_id": draft["chat_id"]},
            name=f"unpin_delete_{event_id}"
        )

        # Сохраняем задачи в базу данных
        add_scheduled_job(context.bot_data["db_path"], event_id, job_day.id, draft["chat_id"], (event_datetime - timedelta(days=1)).isoformat(), job_type="notification_day")
        add_scheduled_job(context.bot_data["db_path"], event_id, job_minutes.id, draft["chat_id"], (event_datetime - timedelta(minutes=15)).isoformat(), job_type="notification_minutes")
        add_scheduled_job(context.bot_data["db_path"], event_id, job_unpin.id, draft["chat_id"], event_datetime.isoformat(), job_type="unpin_delete")

        # Завершаем диалог
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError as e:
        # Если введённый текст не является числом или лимит отрицательный
        error_message = (
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )

        # Редактируем существующее сообщение бота с ошибкой
        try:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=context.user_data["bot_message_id"],
                text=error_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
                parse_mode="HTML"
            )
        except BadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Сообщение пользователя не найдено: {e}")

        # Остаемся в состоянии SET_LIMIT
        return SET_LIMIT