from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, delete_draft, get_user_chat_draft
from src.database.db_operations import add_event
from src.handlers.message_handler import handle_draft_message
from src.message.send_message import send_event_message
from src.logger.logger import logger


async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает текущий шаг черновика на основе его статуса"""
    user_input = update.message.text
    chat_id = update.message.chat_id

    try:
        if draft["status"] == "AWAIT_DESCRIPTION":
            await _process_description(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_DATE":
            await _process_date(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_TIME":
            await _process_time(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_LIMIT":
            await _process_limit(update, context, draft, user_input)

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода"
        )

async def _process_description(update, context, draft, description):
    """Обработка шага ввода описания"""
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft["id"],
        status="AWAIT_DATE",
        description=description
    )

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=draft["bot_message_id"],
        text=f"📢 {description}\n\nВведите дату в формате ДД.ММ.ГГГГ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def _process_date(update, context, draft, date_input):
    """Обработка шага ввода даты"""
    try:
        datetime.strptime(date_input, "%d.%m.%Y").date()

        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_TIME",
            date=date_input
        )

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=draft["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {date_input}\n\nВведите время (ЧЧ:ММ)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ"
        )

async def _process_time(update, context, draft, time_input):
    """Обработка шага ввода времени"""
    try:
        datetime.strptime(time_input, "%H:%M").time()

        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_LIMIT",
            time=time_input
        )

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=draft["bot_message_id"],
            text=f"📢 {draft['description']}\n\n"
                 f"📅 Дата: {draft['date']}\n"
                 f"🕒 Время: {time_input}\n\n"
                 f"Введите лимит участников (0 - без лимита):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат времени. Используйте ЧЧ:ММ"
        )

async def _process_limit(update, context, draft, limit_input):
    """Обработка шага ввода лимита участников"""
    try:
        limit = int(limit_input)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Создаем мероприятие
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=draft["description"],
            date=draft["date"],
            time=draft["time"],
            limit=limit if limit != 0 else None,
            creator_id=update.message.from_user.id,
            chat_id=update.message.chat_id
        )

        if not event_id:
            raise Exception("Не удалось создать мероприятие")

        # Отправляем сообщение о мероприятии
        await send_event_message(event_id, context, update.message.chat_id)

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

        # Удаляем сообщение бота с формой
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=draft["bot_message_id"]
            )
        except BadRequest:
            pass

        # Уведомление о успешном создании
        await context.bot.send_message(
            chat_id=update.message.from_user.id,
            text="✅ Мероприятие успешно создано!"
        )

    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат лимита. Введите целое число (0 - без лимита)"
        )
    except Exception as e:
        logger.error(f"Ошибка создания мероприятия: {e}")
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Произошла ошибка при создании мероприятия"
        )

def register_draft_handlers(application):
    """Регистрирует обработчики для работы с черновиками"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        lambda update, context: handle_draft_message(update, context)
    ))