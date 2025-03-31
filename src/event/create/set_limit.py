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
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id

        # 1. Сначала сохраняем все данные мероприятия
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="DONE",
            participant_limit=limit
        )

        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик не найден.")
            return ConversationHandler.END

        # 2. Создаем мероприятие
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=draft["description"],
            date=draft["date"],
            time=draft["time"],
            limit=limit if limit != 0 else None,
            creator_id=user_id,
            chat_id=chat_id,
            message_id=None
        )

        # 3. Отправляем сообщение о мероприятии
        try:
            message_id = await send_event_message(event_id, context, chat_id)
            update_event_field(context.bot_data["db_path"], event_id, "message_id", message_id)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # 4. Пытаемся удалить сообщения (с обработкой ошибок)
        try:
            # Удаляем сообщение бота с параметрами
            if "bot_message_id" in context.user_data:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=context.user_data["bot_message_id"]
                )
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение бота: {e}")

        try:
            # Удаляем сообщение пользователя с лимитом
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        # 5. Уведомляем создателя
        try:
            chat_id_link = int(str(chat_id)[4:]) if str(chat_id).startswith("-100") else chat_id
            event_link = f"https://t.me/c/{chat_id_link}/{message_id}"
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Мероприятие создано!\n\n📢 <a href='{event_link}'>{draft['description']}</a>\n📅 Дата: {draft['date']}\n🕒 Время: {draft['time']}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления создателя: {e}")

        # 6. Планируем уведомления (с обработкой ошибок)
        try:
            event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
            event_datetime = event_datetime.replace(tzinfo=context.bot_data["tz"])

            jobs = [
                (event_datetime - timedelta(days=1), "1 день", "notification_day"),
                (event_datetime - timedelta(minutes=15), "15 минут", "notification_minutes"),
                (event_datetime, None, "unpin_delete")
            ]

            for when, time_until, job_type in jobs:
                job = context.job_queue.run_once(
                    send_notification if job_type != "unpin_delete" else unpin_and_delete_event,
                    when,
                    data={"event_id": event_id, "time_until": time_until} if time_until else {"event_id": event_id, "chat_id": chat_id},
                    name=f"{job_type}_{event_id}"
                )
                add_scheduled_job(
                    context.bot_data["db_path"],
                    event_id,
                    job.id,
                    chat_id,
                    when.isoformat(),
                    job_type
                )
        except Exception as e:
            logger.error(f"Ошибка планирования уведомлений: {e}")

        # 7. Финализация - очистка состояния
        try:
            delete_draft(context.bot_data["drafts_db_path"], draft_id)
            clear_user_state(context.bot_data["drafts_db_path"], user_id)
            context.user_data.clear()
        except Exception as e:
            logger.error(f"Ошибка очистки состояния: {e}")

        return ConversationHandler.END

    except ValueError:
        # Ошибка формата лимита
        error_text = "Неверный формат лимита. Введите положительное число или 0:"
        try:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=context.user_data["bot_message_id"],
                text=error_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
            )
            await update.message.delete()
        except BadRequest as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            try:
                await update.message.reply_text(error_text)
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение: {e}")

        return SET_LIMIT