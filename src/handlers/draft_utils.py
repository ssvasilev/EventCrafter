from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, delete_draft, get_user_chat_draft, add_draft, get_draft
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

async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текущий шаг черновика с поддержкой восстановления сессий"""
    # Сохраняем все необходимые переменные
    user_input = update.message.text
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    # Получаем менеджер сессий
    session_manager = context.bot_data["session_manager"]

    # Ищем активную сессию (сначала в памяти, потом в БД)
    session = session_manager.get_session_for_user(user_id, chat_id)

    if not session:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Нет активного процесса создания/редактирования. Начните заново."
        )
        return

    try:
        # Получаем черновик из БД
        draft = get_draft(context.bot_data["drafts_db_path"], session.draft_id)

        if not draft:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Черновик не найден. Начните процесс заново."
            )
            session_manager.end_session(user_id, chat_id, session.bot_message_id)
            return

        # Обрабатываем ввод в зависимости от статуса
        if draft["status"].startswith("EDIT_"):
            await _process_edit_step(update, context, draft, user_input)
        else:
            if draft["status"] == "AWAIT_DESCRIPTION":
                await _process_description(update, context, draft, user_input)
            elif draft["status"] == "AWAIT_DATE":
                await _process_date(update, context, draft, user_input)
            elif draft["status"] == "AWAIT_TIME":
                await _process_time(update, context, draft, user_input)
            elif draft["status"] == "AWAIT_LIMIT":
                await _process_limit(update, context, draft, user_input)

        # Пытаемся удалить сообщение пользователя (если не в режиме редактирования)
        if not draft["status"].startswith("EDIT_"):
            try:
                await update.message.delete()
            except BadRequest as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода"
        )
        # При ошибке завершаем сессию
        session_manager.end_session(user_id, chat_id, session.bot_message_id)

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


async def _process_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: dict, user_input: str):
    """Обрабатывает ввод пользователя при редактировании конкретного поля"""
    field = draft["status"].split("_")[1]  # Извлекаем поле из статуса (EDIT_description -> description)

    try:
        if field == "description":
            await _update_event_field(context, draft, "description", user_input)
        elif field == "date":
            await _validate_and_update_date(update, context, draft, user_input)
        elif field == "time":
            await _validate_and_update_time(update, context, draft, user_input)
        elif field == "limit":
            await _update_participant_limit(update, context, draft, user_input)

        # Удаляем сообщение пользователя после успешной обработки
        try:
            await update.message.delete()
        except BadRequest:
            pass

    except ValueError as e:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"❌ Ошибка: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Ошибка редактирования: {e}")
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Произошла ошибка при редактировании"
        )


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


async def _update_event_field(context: ContextTypes.DEFAULT_TYPE, draft: dict, field: str, value: str):
    """Обновляет поле мероприятия и завершает редактирование"""
    from src.database.db_operations import update_event_field

    if update_event_field(
            db_path=context.bot_data["db_path"],
            event_id=draft["event_id"],
            field=field,
            value=value
    ):
        await _finalize_edit(context, draft)
    else:
        raise Exception("Не удалось обновить поле")

async def _validate_and_update_date(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: dict, date_input: str):
    """Проверяет формат даты перед обновлением"""
    try:
        datetime.strptime(date_input, "%d.%m.%Y")
        await _update_event_field(context, draft, "date", date_input)
    except ValueError:
        raise ValueError("Неверный формат даты. Используйте ДД.ММ.ГГГГ")

async def _validate_and_update_time(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: dict, time_input: str):
    """Проверяет формат времени перед обновлением"""
    try:
        datetime.strptime(time_input, "%H:%M")
        await _update_event_field(context, draft, "time", time_input)
    except ValueError:
        raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ")

async def _update_participant_limit(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: dict, limit_input: str):
    """Обрабатывает изменение лимита участников"""
    try:
        limit = int(limit_input)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        await _update_event_field(
            context, draft,
            "participant_limit",
            limit if limit != 0 else None  # 0 преобразуем в None (без лимита)
        )
    except ValueError:
        raise ValueError("Лимит должен быть целым числом ≥ 0")



async def _finalize_edit(context: ContextTypes.DEFAULT_TYPE, draft: dict):
    """Финализирует процесс редактирования"""
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

    # Завершаем сессию
    context.bot_data["session_manager"].end_session(
        creator_id=draft["creator_id"],
        chat_id=draft["chat_id"],
        bot_message_id=draft["bot_message_id"]
    )

    # Удаляем черновик
    delete_draft(context.bot_data["drafts_db_path"], draft["id"])