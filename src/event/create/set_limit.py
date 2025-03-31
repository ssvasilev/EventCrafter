from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.database.db_operations import add_event, update_event_field, add_scheduled_job
from src.database.db_draft_operations import update_draft, get_draft, delete_draft, clear_user_state
from src.jobs.notification_jobs import unpin_and_delete_event, send_notification
from src.logger.logger import logger
from src.message.send_message import send_event_message
from src.handlers.conversation_handler_states import SET_LIMIT

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка восстановленной сессии
    if context.user_data.get("restored"):
        del context.user_data["restored"]
    elif 'draft_id' not in context.user_data:
        await update.message.reply_text("Сессия устарела. Начните заново.")
        return ConversationHandler.END

    limit_text = update.message.text
    try:
        limit = int(limit_text)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        draft_id = context.user_data["draft_id"]

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="DONE",
            participant_limit=limit
        )

        # Получаем черновик
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик не найден.")
            return ConversationHandler.END

        # Создаем мероприятие
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

        # Отправляем сообщение о мероприятии
        try:
            message_id = await send_event_message(event_id, context, draft["chat_id"])
            update_event_field(context.bot_data["db_path"], event_id, "message_id", message_id)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Уведомляем создателя
        try:
            chat_id_link = int(str(draft["chat_id"])[4:]) if str(draft["chat_id"]).startswith("-100") else draft["chat_id"]
            event_link = f"https://t.me/c/{chat_id_link}/{message_id}"
            await context.bot.send_message(
                chat_id=draft["creator_id"],
                text=f"✅ Мероприятие создано!\n\n📢 <a href='{event_link}'>{draft['description']}</a>\n📅 Дата: {draft['date']}\n🕒 Время: {draft['time']}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления: {e}")

        # Удаляем черновик и очищаем состояние
        delete_draft(context.bot_data["drafts_db_path"], draft_id)
        clear_user_state(context.bot_data["drafts_db_path"], update.message.from_user.id)

        # Планируем уведомления
        try:
            event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
            event_datetime = event_datetime.replace(tzinfo=context.bot_data["tz"])

            # Уведомление за день
            job_day = context.job_queue.run_once(
                send_notification,
                event_datetime - timedelta(days=1),
                data={"event_id": event_id, "time_until": "1 день"},
                name=f"notification_{event_id}_day"
            )

            # Уведомление за 15 минут
            job_minutes = context.job_queue.run_once(
                send_notification,
                event_datetime - timedelta(minutes=15),
                data={"event_id": event_id, "time_until": "15 минут"},
                name=f"notification_{event_id}_minutes"
            )

            # Автоматическое удаление
            job_unpin = context.job_queue.run_once(
                unpin_and_delete_event,
                event_datetime,
                data={"event_id": event_id, "chat_id": draft["chat_id"]},
                name=f"unpin_delete_{event_id}"
            )

            # Сохраняем задачи в БД
            add_scheduled_job(context.bot_data["db_path"], event_id, job_day.id, draft["chat_id"], (event_datetime - timedelta(days=1)).isoformat(), "notification_day")
            add_scheduled_job(context.bot_data["db_path"], event_id, job_minutes.id, draft["chat_id"], (event_datetime - timedelta(minutes=15)).isoformat(), "notification_minutes")
            add_scheduled_job(context.bot_data["db_path"], event_id, job_unpin.id, draft["chat_id"], event_datetime.isoformat(), "unpin_delete")

        except Exception as e:
            logger.error(f"Ошибка планирования: {e}")

        # Завершаем диалог
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError:
        # Ошибка формата лимита
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат лимита. Введите положительное число или 0:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_LIMIT