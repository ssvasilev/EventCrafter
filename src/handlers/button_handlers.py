from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    update_event_field
)
from src.database.db_draft_operations import add_draft, delete_draft, get_draft, get_user_chat_draft
from src.message.send_message import send_event_message
from src.logger.logger import logger

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        data = query.data
        if not data or '|' not in data:
            logger.error(f"Неверный формат callback_data: {data}")
            return

        parts = data.split('|')
        action = parts[0]

        # Унифицированная обработка всех типов отмены
        if action in ['cancel_edit', 'cancel_input', 'menu_cancel_draft', 'cancel_draft']:
            await handle_cancel_action(query, context, action, parts[1])
            return

        if action in ['join', 'leave', 'edit'] and len(parts) >= 2:
            await handle_basic_actions(query, context, action, parts[1])
        elif action == 'edit_field' and len(parts) >= 3:
            await handle_edit_field(query, context, parts[1], parts[2])
        else:
            logger.error(f"Неизвестный action или формат: {data}")
            await query.edit_message_text("⚠️ Ошибка: неверный формат запроса")

    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}", exc_info=True)
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса")

async def handle_basic_actions(query, context, action, event_id_str):
    """Обработка основных действий: join, leave, edit, cancel_edit"""
    try:
        event_id = int(event_id_str)
    except ValueError:
        logger.error(f"Неверный ID мероприятия: {event_id_str}")
        await query.edit_message_text("⚠️ Ошибка: неверный ID мероприятия")
        return

    handlers = {
        'join': handle_join,
        'leave': handle_leave,
        'edit': handle_edit_event,
        'cancel_edit': handle_cancel_edit
    }

    if action in handlers:
        await handlers[action](query, context, event_id)

async def handle_join(query, context, event_id):
    """Обработка участия в мероприятии"""
    user = query.from_user
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    user_id = user.id
    user_name = f"{user.full_name} (@{user.username})" if user.username else f"{user.full_name} (ID: {user.id})"

    if is_user_in_declined(db_path, event_id, user_id):
        remove_from_declined(db_path, event_id, user_id)

    if is_user_in_participants(db_path, event_id, user_id) or is_user_in_reserve(db_path, event_id, user_id):
        await query.answer("Вы уже в списке участников или резерва.")
        return

    if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
        add_participant(db_path, event_id, user_id, user_name)
        await query.answer(f"✅ Вы добавлены в список участников!")
    else:
        add_to_reserve(db_path, event_id, user_id, user_name)
        await query.answer("⏳ Вы добавлены в резерв", show_alert=True)

    await update_event_message(context, event_id, query.message)

async def handle_leave(query, context, event_id):
    """Обработка отказа от участия"""
    user = query.from_user
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    user_id = user.id
    user_name = f"{user.full_name} (@{user.username})" if user.username else f"{user.full_name} (ID: {user.id})"

    if is_user_in_participants(db_path, event_id, user_id):
        remove_participant(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)

        reserve = get_reserve(db_path, event_id)
        if reserve:
            new_participant = reserve[0]
            remove_from_reserve(db_path, event_id, new_participant["user_id"])
            add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])

            await context.bot.send_message(
                chat_id=event["chat_id"],
                text=f"👋 {user_name} больше не участвует\n"
                     f"🎉 {new_participant['user_name']} перемещён(а) из резерва!"
            )

    elif is_user_in_reserve(db_path, event_id, user_id):
        remove_from_reserve(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)
    elif is_user_in_declined(db_path, event_id, user_id):
        await query.answer("Вы уже в списке отказавшихся")
        return
    else:
        add_to_declined(db_path, event_id, user_id, user_name)

    await query.answer("Вы отказались от участия")
    await update_event_message(context, event_id, query.message)

async def handle_edit_event(query, context, event_id):
    """Показ меню редактирования"""
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    keyboard = [
        [InlineKeyboardButton("📝 Описание", callback_data=f"edit_field|{event_id}|description")],
        [InlineKeyboardButton("📅 Дата", callback_data=f"edit_field|{event_id}|date")],
        [InlineKeyboardButton("🕒 Время", callback_data=f"edit_field|{event_id}|time")],
        [InlineKeyboardButton("👥 Лимит", callback_data=f"edit_field|{event_id}|limit")],
        [InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_edit|{event_id}")]
    ]

    await query.edit_message_text(
        text="✏️ Выберите поле для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_edit_field(query, context, event_id_str, field):
    """Обработка выбора поля для редактирования"""
    try:
        event_id = int(event_id_str)
    except ValueError:
        logger.error(f"Неверный ID мероприятия: {event_id_str}")
        await query.edit_message_text("⚠️ Ошибка: неверный ID мероприятия")
        return

    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=query.from_user.id,
        chat_id=query.message.chat_id,
        status=f"EDIT_{field}",
        event_id=event_id,
        original_message_id=query.message.message_id,
        description=event["description"],
        date=event["date"],
        time=event["time"],
        participant_limit=event["participant_limit"]
    )

    prompts = {
        "description": "📝 Введите новое описание:",
        "date": "📅 Введите новую дату (ДД.ММ.ГГГГ):",
        "time": "🕒 Введите новое время (ЧЧ:ММ):",
        "limit": "👥 Введите лимит участников (0 - без лимита):"
    }

    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_input|{draft_id}")]]
    await query.edit_message_text(
        text=prompts[field],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_cancel_edit(query, context, event_id):
    """Отмена редактирования и возврат к просмотру"""
    event = get_event(context.bot_data["db_path"], event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    await update_event_message(context, event_id, query.message)
    await query.answer("Редактирование отменено")

async def handle_cancel_input(query, context, draft_id_str):
    """Отмена ввода при редактировании"""
    try:
        draft_id = int(draft_id_str)
    except ValueError:
        logger.error(f"Неверный ID черновика: {draft_id_str}")
        await query.edit_message_text("⚠️ Ошибка: неверный ID черновика")
        return

    draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
    if draft:
        delete_draft(context.bot_data["drafts_db_path"], draft_id)
        await handle_cancel_edit(query, context, draft["event_id"])
    else:
        await query.edit_message_text("Сессия редактирования не найдена")


async def handle_cancel_action(query, context, action, item_id_str):
    """Универсальный обработчик всех типов отмены"""
    try:
        item_id = int(item_id_str)
    except ValueError:
        logger.error(f"Неверный ID для отмены: {item_id_str}")
        await query.edit_message_text("⚠️ Ошибка: неверный ID")
        return

    try:
        db_path = context.bot_data["db_path"]
        drafts_db_path = context.bot_data["drafts_db_path"]

        if action in ["menu_cancel_draft", "cancel_draft"]:
            # Отмена создания нового мероприятия
            draft = get_draft(drafts_db_path, item_id)
            if draft:
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение: {e}")
                finally:
                    delete_draft(drafts_db_path, item_id)
            return

        # Для остальных типов отмены (cancel_edit, cancel_input)
        draft = get_draft(drafts_db_path, item_id) if action == "cancel_input" else None

        if not draft and action == "cancel_input":
            draft = get_user_chat_draft(
                drafts_db_path,
                query.from_user.id,
                query.message.chat_id
            )
            if draft:
                item_id = draft["id"]

        if draft:
            event_id = draft.get("event_id")
            original_message_id = draft.get("original_message_id")
            delete_draft(drafts_db_path, item_id)

            if event_id and original_message_id:
                event = get_event(db_path, event_id)
                if event:
                    await send_event_message(
                        event_id,
                        context,
                        query.message.chat_id,
                        message_id=original_message_id
                    )
                    return

        # Если это cancel_edit или не нашли черновик
        if action == "cancel_edit":
            event = get_event(db_path, item_id)
            if event:
                await send_event_message(
                    item_id,
                    context,
                    query.message.chat_id,
                    message_id=query.message.message_id
                )

    except Exception as e:
        logger.error(f"Ошибка при обработке отмены: {e}")
        await query.edit_message_text("⚠️ Не удалось выполнить отмену")


async def update_event_message(context, event_id, message):
    """Обновление сообщения о мероприятии"""
    try:
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=message.chat_id,
            message_id=message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка обновления сообщения: {e}")

def register_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(join|leave|edit|edit_field|cancel_edit|cancel_input|menu_cancel_draft|cancel_draft)\|"
        )
    )