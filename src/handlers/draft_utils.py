from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, delete_draft, get_draft, add_draft
from src.database.db_operations import add_event, get_event, update_event_field
from src.message.send_message import send_event_message, safe_edit_message
from src.database.session_manager import SessionManager
from src.logger.logger import logger

async def start_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id, field_name):
    """Начинает редактирование поля мероприятия с сохранением редактирования сообщения"""
    query = update.callback_query
    await query.answer()

    try:
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
            bot_message_id=query.message.message_id,  # Сохраняем ID сообщения для редактирования
            description=event["description"],
            date=event["date"],
            time=event["time"],
            participant_limit=event["participant_limit"]
        )

        # Создаем сессию
        session_manager = SessionManager(context.bot_data["sessions_db_path"])
        session_manager.create_session(query.from_user.id, query.message.chat_id, draft_id)

        field_prompts = {
            "description": "Введите новое описание мероприятия:",
            "date": "Введите новую дату (ДД.ММ.ГГГГ):",
            "time": "Введите новое время (ЧЧ:ММ):",
            "limit": "Введите новый лимит участников (0 - без лимита):"
        }

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft_id}")]]

        # Редактируем существующее сообщение
        await safe_edit_message(
            context.bot,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            text=field_prompts[field_name],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Ошибка начала редактирования: {str(e)}")
        await query.edit_message_text("⚠️ Ошибка при начале редактирования")

async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает текущий шаг черновика с редактированием сообщения"""
    user_input = update.message.text.strip()
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    session_manager = SessionManager(context.bot_data["sessions_db_path"])

    try:
        # Проверка сессии
        if not session_manager.get_active_session(user_id, chat_id) == draft["id"]:
            raise ValueError("Неактивная сессия")

        if draft["status"].startswith("EDIT_"):
            await process_edit_step(update, context, draft)
        else:
            if draft["status"] == "AWAIT_DESCRIPTION":
                await _process_description(context, draft, user_input, chat_id)
            elif draft["status"] == "AWAIT_DATE":
                await _process_date(context, draft, user_input, chat_id)
            elif draft["status"] == "AWAIT_TIME":
                await _process_time(context, draft, user_input, chat_id)
            elif draft["status"] == "AWAIT_LIMIT":
                await _process_limit(update, context, draft, user_input, chat_id)

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except ValueError as e:
        logger.warning(f"Ошибка валидации: {str(e)}")
        await _handle_validation_error(context, draft, chat_id, str(e))
    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {str(e)}")
        await _handle_processing_error(context, draft, chat_id)
        session_manager.clear_session(user_id, chat_id)

async def _process_description(context, draft, description, chat_id):
    """Обработка шага ввода описания с редактированием сообщения"""
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft["id"],
        status="AWAIT_DATE",
        description=description
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft['id']}")]]
    await _edit_draft_message(
        context,
        chat_id,
        draft["bot_message_id"],
        f"📢 {description}\n\nВведите дату в формате ДД.ММ.ГГГГ",
        keyboard
    )

async def _process_date(context, draft, date_input, chat_id):
    """Обработка шага ввода даты с редактированием сообщения"""
    # Валидация даты
    try:
        datetime.strptime(date_input, "%d.%m.%Y").date()
    except ValueError:
        raise ValueError("Неверный формат даты. Используйте ДД.ММ.ГГГГ")

    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft["id"],
        status="AWAIT_TIME",
        date=date_input
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft['id']}")]]
    await _edit_draft_message(
        context,
        chat_id,
        draft["bot_message_id"],
        f"📢 {draft['description']}\n\n📅 Дата: {date_input}\n\nВведите время (ЧЧ:ММ)",
        keyboard
    )

async def _process_time(context, draft, time_input, chat_id):
    """Обработка шага ввода времени с редактированием сообщения"""
    # Валидация времени
    try:
        datetime.strptime(time_input, "%H:%M").time()
    except ValueError:
        raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ")

    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft["id"],
        status="AWAIT_LIMIT",
        time=time_input
    )

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft['id']}")]]
    await _edit_draft_message(
        context,
        chat_id,
        draft["bot_message_id"],
        f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n🕒 Время: {time_input}\n\nВведите лимит участников (0 - без лимита):",
        keyboard
    )

async def _process_limit(update, context, draft, limit_input, chat_id):
    """Обработка шага ввода лимита участников с редактированием сообщения"""
    # Валидация лимита
    try:
        limit = int(limit_input)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")
    except ValueError:
        raise ValueError("Лимит должен быть целым числом ≥ 0")

    # Создаем мероприятие
    event_id = add_event(
        db_path=context.bot_data["db_path"],
        description=draft["description"],
        date=draft["date"],
        time=draft["time"],
        limit=limit if limit != 0 else None,
        creator_id=update.message.from_user.id,
        chat_id=chat_id,
        message_id=draft["bot_message_id"]
    )

    if not event_id:
        raise Exception("Не удалось создать мероприятие")

    # Обновляем сообщение с информацией о мероприятии
    await send_event_message(
        event_id=event_id,
        context=context,
        chat_id=chat_id,
        message_id=draft["bot_message_id"]
    )

    # Удаляем черновик и сессию
    delete_draft(context.bot_data["drafts_db_path"], draft["id"])
    SessionManager(context.bot_data["sessions_db_path"]).clear_session(update.message.from_user.id, chat_id)

    # Уведомление о успешном создании
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Мероприятие успешно создано!",
        reply_to_message_id=draft["bot_message_id"]
    )


async def _edit_draft_message(context, chat_id, message_id, text, reply_markup=None):
    """Безопасное редактирование сообщения черновика"""
    try:
        await safe_edit_message(
            context.bot,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
    except BadRequest as e:
        logger.error(f"Не удалось отредактировать сообщение черновика: {str(e)}")
        raise Exception("Не удалось обновить сообщение")

async def _handle_validation_error(context, draft, chat_id, error_msg):
    """Обработка ошибок валидации"""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ {error_msg}",
            reply_to_message_id=draft.get("bot_message_id")
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")

async def _handle_processing_error(context, draft, chat_id):
    """Обработка ошибок процесса"""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода",
            reply_to_message_id=draft.get("bot_message_id")
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")

async def process_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает шаг редактирования существующего мероприятия"""
    user_input = update.message.text.strip()
    field = draft["status"].split("_")[1].lower()  # Получаем поле из статуса (EDIT_DESCRIPTION -> description)
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    try:
        # Проверка сессии
        session_manager = SessionManager(context.bot_data["sessions_db_path"])
        if not session_manager.get_active_session(user_id, chat_id) == draft["id"]:
            raise ValueError("Неактивная сессия редактирования")

        if field == "description":
            await _update_description(context, draft, user_input, chat_id)
        elif field == "date":
            await _update_date(context, draft, user_input, chat_id)
        elif field == "time":
            await _update_time(context, draft, user_input, chat_id)
        elif field == "limit":
            await _update_limit(context, draft, user_input, chat_id)
        else:
            raise ValueError(f"Неизвестное поле для редактирования: {field}")

        # Удаляем сообщение пользователя после успешной обработки
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except ValueError as e:
        logger.warning(f"Ошибка валидации при редактировании: {str(e)}")
        await _send_validation_error(context, chat_id, draft["bot_message_id"], str(e))
    except Exception as e:
        logger.error(f"Ошибка при редактировании: {str(e)}")
        await _send_processing_error(context, chat_id, draft["bot_message_id"])
        session_manager.clear_session(user_id, chat_id)

async def _update_description(context, draft, new_description, chat_id):
    """Обновляет описание мероприятия"""
    if not new_description or len(new_description) > 500:
        raise ValueError("Описание должно быть от 1 до 500 символов")

    # Обновляем в базе данных
    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field="description",
        value=new_description
    )

    # Восстанавливаем оригинальное сообщение
    await _restore_original_message(context, draft, chat_id)

async def _update_date(context, draft, new_date, chat_id):
    """Обновляет дату мероприятия"""
    try:
        datetime.strptime(new_date, "%d.%m.%Y").date()
    except ValueError:
        raise ValueError("Неверный формат даты. Используйте ДД.ММ.ГГГГ")

    # Обновляем в базе данных
    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field="date",
        value=new_date
    )

    # Восстанавливаем оригинальное сообщение
    await _restore_original_message(context, draft, chat_id)

async def _update_time(context, draft, new_time, chat_id):
    """Обновляет время мероприятия"""
    try:
        datetime.strptime(new_time, "%H:%M").time()
    except ValueError:
        raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ")

    # Обновляем в базе данных
    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field="time",
        value=new_time
    )

    # Восстанавливаем оригинальное сообщение
    await _restore_original_message(context, draft, chat_id)

async def _update_limit(context, draft, new_limit, chat_id):
    """Обновляет лимит участников"""
    try:
        limit = int(new_limit)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")
    except ValueError:
        raise ValueError("Лимит должен быть целым числом ≥ 0")

    # Обновляем в базе данных
    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field="participant_limit",
        value=limit if limit != 0 else None
    )

    # Восстанавливаем оригинальное сообщение
    await _restore_original_message(context, draft, chat_id)

async def _restore_original_message(context, draft, chat_id):
    """Восстанавливает оригинальное сообщение мероприятия после редактирования"""
    # Обновляем сообщение мероприятия
    await send_event_message(
        event_id=draft["event_id"],
        context=context,
        chat_id=chat_id,
        message_id=draft["original_message_id"]
    )

    # Удаляем черновик
    delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    # Очищаем сессию
    SessionManager(context.bot_data["sessions_db_path"]).clear_session(draft["creator_id"], chat_id)

async def _send_validation_error(context, chat_id, reply_to_id, error_msg):
    """Отправляет сообщение об ошибке валидации"""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ {error_msg}",
            reply_to_message_id=reply_to_id
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")

async def _send_processing_error(context, chat_id, reply_to_id):
    """Отправляет сообщение об ошибке обработки"""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода",
            reply_to_message_id=reply_to_id
        )
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение об ошибке: {str(e)}")