from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, delete_draft, get_user_chat_draft, add_draft
from src.database.db_operations import add_event, get_event
from src.message.send_message import send_event_message
from src.logger.logger import logger


async def start_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id, field_name):
    """Начинает редактирование поля мероприятия"""
    query = update.callback_query
    await query.answer()

    event = get_event(context.bot_data["db_path"], event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Создаем черновик для редактирования
    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=query.from_user.id,
        chat_id=query.message.chat_id,
        status=f"EDIT_{field_name}",
        event_id=event_id,
        original_message_id=query.message.message_id,
        description=event["description"],
        date=event["date"],
        time=event["time"],
        participant_limit=event["participant_limit"]
    )

    # Запрашиваем новое значение
    field_prompts = {
        "description": "Введите новое описание мероприятия:",
        "date": "Введите новую дату (ДД.ММ.ГГГГ):",
        "time": "Введите новое время (ЧЧ:ММ):",
        "limit": "Введите новый лимит участников (0 - без лимита):"
    }

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_input|{draft_id}")]]
    await query.edit_message_text(
        text=field_prompts[field_name],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает текущий шаг черновика на основе его статуса"""
    user_input = update.message.text
    chat_id = update.message.chat_id

    try:
        if draft["status"].startswith("EDIT_"):
            await process_edit_step(update, context, draft)
        else:
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
            chat_id=update.message.chat_id,
            message_id=draft["bot_message_id"]
        )

        if not event_id:
            raise Exception("Не удалось создать мероприятие")

        # Редактируем существующее сообщение
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=update.message.chat_id,
            message_id=draft["bot_message_id"]
        )

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

        # Удаляем сообщение пользователя с вводом лимита
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        # Уведомление о успешном создании можно отправить как reply к отредактированному сообщению
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="✅ Мероприятие успешно создано!",
            reply_to_message_id=draft["bot_message_id"]
        )

    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат лимита. Введите целое число (0 - без лимита)",
            reply_to_message_id=draft["bot_message_id"]
        )
    except Exception as e:
        logger.error(f"Ошибка создания мероприятия: {e}")
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Произошла ошибка при создании мероприятия",
            reply_to_message_id=draft["bot_message_id"]
        )


async def process_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает шаг редактирования"""
    field = draft["status"].split("_")[1]  # Получаем поле из статуса (EDIT_description -> description)
    user_input = update.message.text

    if field == "description":
        await _update_event_field(context, draft, "description", user_input)
    elif field == "date":
        await _validate_and_update(update, context, draft, "date", user_input, "%d.%m.%Y", "ДД.ММ.ГГГГ")
    elif field == "time":
        await _validate_and_update(update, context, draft, "time", user_input, "%H:%M", "ЧЧ:ММ")
    elif field == "limit":
        await _update_participant_limit(update, context, draft, user_input)

    # Удаляем сообщение пользователя
    try:
        await update.message.delete()
    except BadRequest as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")


async def _update_event_field(context, draft, field, value):
    """Обновляет поле мероприятия"""
    from src.database.db_operations import update_event_field

    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field=field,
        value=value
    )
    await _finalize_edit(context, draft)


async def _validate_and_update(update, context, draft, field, value, fmt, error_hint):
    """Проверяет формат и обновляет поле"""
    from datetime import datetime
    try:
        datetime.strptime(value, fmt)  # Валидация формата
        await _update_event_field(context, draft, field, value)
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"❌ Неверный формат. Используйте {error_hint}"
        )


async def _update_participant_limit(update, context, draft, value):
    """Обновляет лимит участников"""
    try:
        limit = int(value)
        if limit < 0:
            raise ValueError
        await _update_event_field(
            context, draft,
            "participant_limit",
            limit if limit != 0 else None
        )
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Лимит должен быть целым числом ≥ 0"
        )


async def _finalize_edit(context, draft):
    """Завершает редактирование"""
    from src.message.send_message import send_event_message

    # Обновляем сообщение мероприятия
    await send_event_message(
        event_id=draft["event_id"],
        context=context,
        chat_id=draft["chat_id"],
        message_id=draft["original_message_id"]
    )

    # Удаляем черновик
    delete_draft(context.bot_data["drafts_db_path"], draft["id"])