from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from src.database.db_draft_operations import add_draft
from src.database.db_operations import (
    get_event,
    add_participant,
    remove_participant,
    add_to_declined,
    remove_from_reserve,
    is_user_in_participants,
    is_user_in_reserve,
    get_participants_count,
    add_to_reserve,
    get_reserve,
    is_user_in_declined,
    remove_from_declined
)
from src.message.send_message import send_event_message

from src.logger.logger import logger
from src.utils.user_naming import UserNamingService



async def handle_join_action(db_path, event, user_id, user_name, query):
    logger.debug(f"Event structure: {event}")
    """Обрабатывает действие 'Участвовать'"""
    display_name = UserNamingService.get_display_name(query.from_user)
    try:
        event_id = event["id"]  # Изменено с event["event_id"] на event["id"]

        if is_user_in_participants(db_path, event_id, user_id):
            await query.answer("Вы уже в списке участников!")
            return False

        if is_user_in_reserve(db_path, event_id, user_id):
            await query.answer("Вы уже в резерве!")
            return False

        if is_user_in_declined(db_path, event_id, user_id):
            remove_from_declined(db_path, event_id, user_id)

        participant_limit = event.get("participant_limit")
        if participant_limit is None or get_participants_count(db_path, event_id) < participant_limit:
            add_participant(db_path, event_id, user_id, user_name)
            await query.answer("✅ Вы теперь участвуете!")
            return True
        else:
            add_to_reserve(db_path, event_id, user_id, user_name)
            await query.answer("⏳ Вы добавлены в резерв")
            return True
    except Exception as e:
        logger.error(f"Join action error: {e}")
        await query.answer("⚠ Ошибка при обработке")
        return False

async def handle_leave_action(db_path, event, user_id, user_name, query, context):
    logger.debug(f"Event structure: {event}")
    """Обрабатывает действие 'Не участвовать'"""
    display_name = UserNamingService.get_display_name(query.from_user)
    try:
        event_id = event["id"]  # Изменено с event["event_id"] на event["id"]
        chat_id = event["chat_id"]
        changed = False

        if is_user_in_participants(db_path, event_id, user_id):
            remove_participant(db_path, event_id, user_id)
            add_to_declined(db_path, event_id, user_id, user_name)
            changed = True

            reserve = get_reserve(db_path, event_id)
            if reserve:
                new_participant = reserve[0]
                remove_from_reserve(db_path, event_id, new_participant["user_id"])
                add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎉 {new_participant['user_name']} перемещён(а) из резерва в участники!"
                )
                await query.answer(f"❌ Вы отказались. {new_participant['user_name']} теперь участвует!")
                return True

        elif is_user_in_reserve(db_path, event_id, user_id):
            remove_from_reserve(db_path, event_id, user_id)
            add_to_declined(db_path, event_id, user_id, user_name)
            changed = True
        elif is_user_in_declined(db_path, event_id, user_id):
            await query.answer("Вы уже отказались от участия")
            return False
        else:
            add_to_declined(db_path, event_id, user_id, user_name)
            changed = True

        if changed:
            await query.answer("❌ Вы отказались от участия")
            return True
        return False
    except Exception as e:
        logger.error(f"Leave action error: {e}")
        await query.answer("⚠ Ошибка при обработке")
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        action, event_id = query.data.split("|")
        event_id = int(event_id)

        if action == "join":
            await handle_participation(query, context, event_id, participate=True)
        elif action == "leave":
            await handle_participation(query, context, event_id, participate=False)
        elif action == "edit":
            await handle_edit_event(query, context, event_id)

    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса")

async def handle_edit_event(query, context, event_id):
    """Обработка нажатия кнопки редактирования"""
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Клавиатура для выбора поля редактирования
    keyboard = [
        [InlineKeyboardButton("📝 Описание", callback_data=f"edit_field|{event_id}|description")],
        [InlineKeyboardButton("📅 Дата", callback_data=f"edit_field|{event_id}|date")],
        [InlineKeyboardButton("🕒 Время", callback_data=f"edit_field|{event_id}|time")],
        [InlineKeyboardButton("👥 Лимит участников", callback_data=f"edit_field|{event_id}|limit")],
        [InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_edit|{event_id}")]
    ]

    await query.edit_message_text(
        text="Выберите поле для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_participation(query, context, event_id, participate):
    """Обработка участия/отказа от мероприятия с форматированием имен"""
    from src.database.db_operations import (
        get_event,
        add_participant,
        add_to_declined,
        add_to_reserve,
        remove_participant,
        remove_from_declined,
        get_participants_count
    )

    user = query.from_user
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Форматируем имя пользователя
    user_display_name = (
        f"{user.full_name} (@{user.username})"
        if user.username
        else f"{user.full_name} (ID: {user.id})"
    )

    if participate:
        # Логика для "Участвую"
        if event["participant_limit"] and get_participants_count(context.bot_data["db_path"], event_id) >= event["participant_limit"]:
            await query.answer("Все места заняты, вы добавлены в резерв", show_alert=True)
            add_to_reserve(context.bot_data["db_path"], event_id, user.id, user_display_name)
        else:
            remove_from_declined(context.bot_data["db_path"], event_id, user.id)
            add_participant(context.bot_data["db_path"], event_id, user.id, user_display_name)
            await query.answer("Вы добавлены в список участников")
    else:
        # Логика для "Не участвую"
        remove_participant(context.bot_data["db_path"], event_id, user.id)
        add_to_declined(context.bot_data["db_path"], event_id, user.id, user_display_name)
        await query.answer("Вы отказались от участия")

    # Обновляем сообщение мероприятия
    await update_event_message(context, event_id, query.message)


async def update_event_message(context, event_id, message):
    """Обновляет сообщение о мероприятии"""
    from src.message.send_message import send_event_message
    await send_event_message(
        event_id=event_id,
        context=context,
        chat_id=message.chat_id,
        message_id=message.message_id
    )


async def edit_field_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора конкретного поля для редактирования"""
    query = update.callback_query
    await query.answer()

    _, event_id, field = query.data.split("|")
    event_id = int(event_id)
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Создаем черновик для редактирования
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

    # Запрашиваем новое значение
    field_prompts = {
        "description": "Введите новое описание мероприятия:",
        "date": "Введите новую дату (ДД.ММ.ГГГГ):",
        "time": "Введите новое время (ЧЧ:ММ):",
        "limit": "Введите новый лимит участников (0 - без лимита):"
    }

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_input|{draft_id}")]]
    await query.edit_message_text(
        text=field_prompts[field],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cancel_edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отмены редактирования"""
    query = update.callback_query
    await query.answer()

    _, event_id = query.data.split("|")
    event_id = int(event_id)
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Возвращаем стандартное сообщение
    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")]
    ]

    # Форматируем сообщение (используйте ваш формат)
    message_text = f"📢 {event['description']}\n\nДата: {event['date']}\nВремя: {event['time']}\nЛимит: {event['participant_limit'] or '∞'}"

    await query.edit_message_text(
        text=message_text,
        reply_markup=InlineKeyboardMarkup(keyboard))


def register_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(join|leave|edit)\|"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            edit_field_handler,
            pattern=r"^edit_field\|"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            cancel_edit_handler,
            pattern=r"^cancel_edit\|"
        )
    )