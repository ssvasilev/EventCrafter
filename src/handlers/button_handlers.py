from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.database.db_operations import (
    get_event,
    add_participant,
    remove_participant,
    add_to_declined,
    remove_from_reserve,
    remove_from_declined,
    is_user_in_participants,
    is_user_in_reserve,
    get_participants_count,
    add_to_reserve,
    get_reserve,
    is_user_in_declined,
    is_user_in_participants,
    is_user_in_reserve
)
from src.database.db_draft_operations import add_draft, get_draft, delete_draft
from src.database.session_manager import SessionManager
from src.message.send_message import send_event_message

from src.logger.logger import logger

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    session_manager = SessionManager(context.bot_data["sessions_db_path"])

    try:
        if not query.data or '|' not in query.data:
            raise ValueError("Invalid callback data format")

        parts = query.data.split('|')
        action = parts[0]

        if action == 'join':
            await handle_join(query, context, parts[1], user_id)
        elif action == 'leave':
            await handle_leave(query, context, parts[1], user_id)
        elif action == 'edit':
            await handle_edit(query, context, parts[1], user_id, chat_id, session_manager)
        elif action == 'edit_field':
            if len(parts) < 3:
                raise ValueError("Missing field for edit")
            await handle_edit_field(query, context, parts[1], parts[2], user_id, chat_id, session_manager)
        elif action == 'cancel':
            await handle_cancel(query, context, parts[1], user_id, chat_id, session_manager)
        else:
            raise ValueError(f"Unknown action: {action}")

    except ValueError as e:
        logger.warning(f"Invalid button action: {str(e)}")
        await safe_edit_message(query, "⚠️ Неверный формат команды")
    except Exception as e:
        logger.error(f"Button handler error: {str(e)}")
        await safe_edit_message(query, "⚠️ Ошибка обработки команды")

async def handle_join(query, context, event_id_str, user_id):
    """Обработка участия в мероприятии"""
    try:
        event_id = int(event_id_str)
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            raise ValueError("Event not found")

        user = query.from_user
        user_name = f"{user.full_name} (@{user.username})" if user.username else user.full_name

        if is_user_in_declined(db_path, event_id, user_id):
            remove_from_declined(db_path, event_id, user_id)

        if is_user_in_participants(db_path, event_id, user_id) or is_user_in_reserve(db_path, event_id, user_id):
            await query.answer("Вы уже участвуете в этом мероприятии")
            return

        if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
            add_participant(db_path, event_id, user_id, user_name)
            await query.answer("✅ Вы добавлены в список участников!")
        else:
            add_to_reserve(db_path, event_id, user_id, user_name)
            await query.answer("⏳ Вы добавлены в резерв", show_alert=True)

        await update_event_message(context, event_id, query.message)

    except Exception as e:
        raise ValueError(f"Join error: {str(e)}")

async def handle_leave(query, context, event_id_str, user_id):
    """Обработка отказа от участия"""
    try:
        event_id = int(event_id_str)
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            raise ValueError("Event not found")

        user = query.from_user
        user_name = f"{user.full_name} (@{user.username})" if user.username else user.full_name

        if is_user_in_participants(db_path, event_id, user_id):
            remove_participant(db_path, event_id, user_id)
            add_to_declined(db_path, event_id, user_id, user_name)

            reserve = get_reserve(db_path, event_id)
            if reserve:
                new_participant = reserve[0]
                remove_from_reserve(db_path, event_id, new_participant["user_id"])
                add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])

        elif is_user_in_reserve(db_path, event_id, user_id):
            remove_from_reserve(db_path, event_id, user_id)
            add_to_declined(db_path, event_id, user_id, user_name)
        elif is_user_in_declined(db_path, event_id, user_id):
            await query.answer("Вы уже отказались от участия")
            return
        else:
            add_to_declined(db_path, event_id, user_id, user_name)

        await query.answer("Вы отказались от участия")
        await update_event_message(context, event_id, query.message)

    except Exception as e:
        raise ValueError(f"Leave error: {str(e)}")

async def handle_edit(query, context, event_id_str, user_id, chat_id, session_manager):
    """Начало редактирования мероприятия"""
    try:
        event_id = int(event_id_str)
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            raise ValueError("Event not found")

        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id,
            status="EDIT_MENU",
            event_id=event_id,
            original_message_id=query.message.message_id,
            description=event["description"],
            date=event["date"],
            time=event["time"],
            participant_limit=event["participant_limit"]
        )

        session_manager.create_session(user_id, chat_id, draft_id)

        keyboard = [
            [InlineKeyboardButton("📝 Описание", callback_data=f"edit_field|{draft_id}|description")],
            [InlineKeyboardButton("📅 Дата", callback_data=f"edit_field|{draft_id}|date")],
            [InlineKeyboardButton("🕒 Время", callback_data=f"edit_field|{draft_id}|time")],
            [InlineKeyboardButton("👥 Лимит", callback_data=f"edit_field|{draft_id}|limit")],
            [InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft_id}")]
        ]

        await safe_edit_message(
            query,
            "✏️ Выберите поле для редактирования:",
            InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        raise ValueError(f"Edit init error: {str(e)}")

async def handle_edit_field(query, context, draft_id_str, field, user_id, chat_id, session_manager):
    """Обработка выбора поля для редактирования"""
    try:
        draft_id = int(draft_id_str)

        # Проверка сессии
        active_draft_id = session_manager.get_active_session(user_id, chat_id)
        if active_draft_id != draft_id:
            raise ValueError("Invalid session for draft")

        prompts = {
            "description": "📝 Введите новое описание:",
            "date": "📅 Введите новую дату (ДД.ММ.ГГГГ):",
            "time": "🕒 Введите новое время (ЧЧ:ММ):",
            "limit": "👥 Введите лимит участников (0 - без лимита):"
        }

        if field not in prompts:
            raise ValueError("Invalid field for editing")

        # Обновляем статус черновика
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if draft:
            draft["status"] = f"EDIT_{field.upper()}"
            session_manager.create_session(user_id, chat_id, draft_id)

        await safe_edit_message(
            query,
            prompts[field],
            InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft_id}")]
            ])
        )

    except Exception as e:
        raise ValueError(f"Edit field error: {str(e)}")


async def handle_cancel(query, context, draft_id_str, user_id, chat_id, session_manager):
    """Обработка отмены действий с защитой от ошибок"""
    try:
        draft_id = int(draft_id_str)
        db_path = context.bot_data["db_path"]
        drafts_db_path = context.bot_data["drafts_db_path"]

        # Получаем черновик как словарь
        draft = dict(get_draft(drafts_db_path, draft_id))

        if not draft:
            raise ValueError("Черновик не найден")

        # Проверяем принадлежность черновика
        if draft["creator_id"] != user_id or draft["chat_id"] != chat_id:
            raise ValueError("Черновик не принадлежит пользователю")

        # Очищаем сессию в любом случае
        session_manager.clear_session(user_id, chat_id)
        delete_draft(drafts_db_path, draft_id)

        if draft.get("event_id"):  # Редактирование существующего
            event = get_event(db_path, draft["event_id"])
            if event and "original_message_id" in draft:
                await send_event_message(
                    event["id"],
                    context,
                    chat_id,
                    message_id=draft["original_message_id"]
                )
        else:  # Создание нового
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=draft["bot_message_id"]
                )
            except BadRequest as e:
                if "Message to delete not found" not in str(e):
                    raise

        await query.answer("Действие отменено")

    except ValueError as e:
        logger.warning(f"Ошибка отмены: {str(e)}")
        await query.answer("⚠️ Не удалось отменить действие")
    except Exception as e:
        logger.error(f"Критическая ошибка при отмене: {str(e)}")
        await query.answer("⚠️ Произошла ошибка")

async def update_event_message(context, event_id, message):
    """Безопасное обновление сообщения о мероприятии"""
    try:
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=message.chat_id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.error(f"Failed to update event message: {str(e)}")

async def safe_edit_message(query, text, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Failed to edit message: {str(e)}")

def register_button_handler(application):
    """Регистрация обработчика кнопок"""
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(join|leave|edit|edit_field|cancel)\|"
        )
    )