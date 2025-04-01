from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from src.database.db_draft_operations import (
    update_draft, get_draft, delete_draft,
    get_user_chat_draft
)
from src.database.db_operations import add_event
from src.message.send_message import send_event_message
from src.logger.logger import logger


async def handle_draft_message(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает сообщение пользователя в контексте черновика"""
    user_message = update.message.text
    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    try:
        if draft["status"] == "AWAIT_DESCRIPTION":
            # Обновляем описание
            update_draft(
                db_path=context.bot_data["drafts_db_path"],
                draft_id=draft["id"],
                status="AWAIT_DATE",
                description=user_message
            )

            # Обновляем сообщение бота
            keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=draft["bot_message_id"],
                text=f"📢 {user_message}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif draft["status"] == "AWAIT_DATE":
            try:
                # Проверяем формат даты
                date = datetime.strptime(user_message, "%d.%m.%Y").date()
                update_draft(
                    db_path=context.bot_data["drafts_db_path"],
                    draft_id=draft["id"],
                    status="AWAIT_TIME",
                    date=user_message
                )

                # Обновляем сообщение бота
                keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=draft["bot_message_id"],
                    text=f"📢 {draft['description']}\n\n📅 Дата: {user_message}\n\nВведите время в формате ЧЧ:ММ",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            except ValueError:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ"
                )
                return

        elif draft["status"] == "AWAIT_TIME":
            try:
                # Проверяем формат времени
                time = datetime.strptime(user_message, "%H:%M").time()
                update_draft(
                    db_path=context.bot_data["drafts_db_path"],
                    draft_id=draft["id"],
                    status="AWAIT_LIMIT",
                    time=user_message
                )

                # Обновляем сообщение бота
                keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=draft["bot_message_id"],
                    text=f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {user_message}\n\n"
                         f"Введите лимит участников (0 - без лимита):",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

            except ValueError:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Неверный формат времени. Введите время в формате ЧЧ:ММ"
                )
                return

        elif draft["status"] == "AWAIT_LIMIT":
            try:
                limit = int(user_message)
                if limit < 0:
                    raise ValueError("Лимит не может быть отрицательным")

                # Создаем мероприятие
                event_id = add_event(
                    db_path=context.bot_data["db_path"],
                    description=draft["description"],
                    date=draft["date"],
                    time=draft["time"],
                    limit=limit if limit != 0 else None,
                    creator_id=creator_id,
                    chat_id=chat_id
                )

                if not event_id:
                    raise Exception("Не удалось создать мероприятие")

                # Отправляем сообщение о мероприятии
                message_id = await send_event_message(event_id, context, chat_id)

                # Удаляем черновик
                delete_draft(context.bot_data["drafts_db_path"], draft["id"])

                # Удаляем сообщение бота с формой
                try:
                    await context.bot.delete_message(
                        chat_id=chat_id,
                        message_id=draft["bot_message_id"]
                    )
                except BadRequest:
                    pass

            except ValueError:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Неверный формат лимита. Введите целое число (0 - без лимита)"
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при создании мероприятия: {e}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Произошла ошибка при создании мероприятия"
                )
                return

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

    except Exception as e:
        logger.error(f"Ошибка при обработке черновика: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка при обработке вашего запроса"
        )