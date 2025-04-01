from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import (
    update_draft, delete_draft, get_user_chat_draft
)
from src.database.db_operations import add_event
from src.message.send_message import send_event_message
from src.logger.logger import logger

async def handle_draft_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик ввода для черновиков"""
    if not update.message:
        return

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    user_input = update.message.text

    # Ищем активный черновик для этого пользователя в этом чате
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], user_id, chat_id)
    if not draft:
        return  # Нет активного черновика - игнорируем

    try:
        if draft["status"] == "AWAIT_DESCRIPTION":
            await _handle_description_input(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_DATE":
            await _handle_date_input(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_TIME":
            await _handle_time_input(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_LIMIT":
            await _handle_limit_input(update, context, draft, user_input)

        # Удаляем сообщение пользователя после обработки
        try:
            await update.message.delete()
        except BadRequest:
            pass

    except Exception as e:
        logger.error(f"Error processing draft input: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода"
        )

async def _handle_description_input(update: Update, context: ContextTypes.DEFAULT_TYPE, draft, description):
    """Обработка ввода описания"""
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft["id"],
        status="AWAIT_DATE",
        description=description
    )

    # Обновляем сообщение бота
    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=draft["bot_message_id"],
        text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def _handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE, draft, date_input):
    """Обработка ввода даты"""
    try:
        # Валидация даты
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
            text=f"📢 {draft['description']}\n\n📅 Дата: {date_input}\n\nВведите время в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ"
        )


async def _handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE, draft, time_input):
    """Обработка ввода времени мероприятия"""
    try:
        # Валидация времени
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
            text="❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 18:30)"
        )


async def _handle_limit_input(update: Update, context: ContextTypes.DEFAULT_TYPE, draft, limit_input):
    """Обработка ввода лимита участников"""
    try:
        limit = int(limit_input)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Создаем мероприятие в основной базе
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

        # Отправляем сообщение с информацией о мероприятии
        message_id = await send_event_message(event_id, context, update.message.chat_id)

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

        # Отправляем подтверждение создателю
        await context.bot.send_message(
            chat_id=update.message.from_user.id,
            text=f"✅ Мероприятие успешно создано! (ID: {event_id})"
        )

    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат лимита. Введите целое число (0 - без лимита)"
        )
    except Exception as e:
        logger.error(f"Ошибка при создании мероприятия: {e}")
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Произошла ошибка при создании мероприятия"
        )

def register_draft_handlers(application):
    """Регистрирует все обработчики для работы с черновиками"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_draft_input
    ))