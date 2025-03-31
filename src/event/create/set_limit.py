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
    # Проверяем наличие необходимых данных
    if "draft_id" not in context.user_data:
        logger.error("No draft_id in user_data during set_limit")
        await update.message.reply_text("⚠️ Сессия создания утеряна. Начните заново.")
        return ConversationHandler.END

    limit_text = update.message.text
    try:
        # Валидация ввода
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Получаем ID черновика из user_data
        draft_id = context.user_data["draft_id"]

        # Финализируем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="DONE",
            participant_limit=limit
        )

        # Получаем данные черновика из базы данных
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            logger.error(f"Draft {draft_id} not found")
            await update.message.reply_text("Ошибка: черновик не найден")
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

        if not event_id:
            logger.error("Failed to create event")
            await update.message.reply_text("Ошибка при создании мероприятия")
            return ConversationHandler.END

        # Отправляем сообщение о мероприятии
        try:
            message_id = await send_event_message(event_id, context, draft["chat_id"])
            update_event_field(context.bot_data["db_path"], event_id, "message_id", message_id)
        except Exception as e:
            logger.error(f"Failed to send event message: {e}")
            await update.message.reply_text("Ошибка при публикации мероприятия")
            return ConversationHandler.END

        # Уведомление создателя
        try:
            chat_link = str(draft["chat_id"])[4:] if str(draft["chat_id"]).startswith("-100") else draft["chat_id"]
            event_link = f"https://t.me/c/{chat_link}/{message_id}"

            await context.bot.send_message(
                chat_id=draft["creator_id"],
                text=f"✅ Мероприятие создано!\n\n"
                     f"📢 <a href='{event_link}'>{draft['description']}</a>\n"
                     f"📅 {draft['date']} в {draft['time']}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify creator: {e}")

        # Планируем уведомления
        try:
            tz = context.bot_data["tz"]
            event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M").replace(tzinfo=tz)

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

            # Сохраняем задачи
            add_scheduled_job(context.bot_data["db_path"], event_id, job_day.id, draft["chat_id"],
                            (event_datetime - timedelta(days=1)).isoformat(), "notification_day")
            add_scheduled_job(context.bot_data["db_path"], event_id, job_minutes.id, draft["chat_id"],
                            (event_datetime - timedelta(minutes=15)).isoformat(), "notification_minutes")
            add_scheduled_job(context.bot_data["db_path"], event_id, job_unpin.id, draft["chat_id"],
                            event_datetime.isoformat(), "unpin_delete")
        except Exception as e:
            logger.error(f"Failed to schedule jobs: {e}")

        # Удаляем черновик и сообщения
        try:
            delete_draft(context.bot_data["drafts_db_path"], draft_id)
            if "bot_message_id" in context.user_data:
                await context.bot.delete_message(
                    chat_id=draft["chat_id"],
                    message_id=context.user_data["bot_message_id"]
                )
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")

        # Полная очистка состояния
        context.user_data.clear()
        return ConversationHandler.END

    except ValueError as e:
        error_msg = "Введите положительное число или 0 для неограниченного числа участников:"
        try:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=context.user_data["bot_message_id"],
                text=error_msg,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
            )
            await update.message.delete()
        except Exception as e:
            logger.error(f"Error handling invalid limit: {e}")
            await update.message.reply_text(error_msg)

        return SET_LIMIT

    except Exception as e:
        logger.error(f"Critical error in set_limit: {e}")
        try:
            await update.message.reply_text("⚠️ Критическая ошибка. Начните заново.")
        except:
            pass

        context.user_data.clear()
        return ConversationHandler.END