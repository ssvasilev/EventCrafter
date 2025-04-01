from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
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

async def handle_join_action(db_path, event, user_id, user_name, query):
    """Обрабатывает действие 'Участвовать'"""
    event_id = event["event_id"]

    if is_user_in_participants(db_path, event_id, user_id):
        await query.answer("Вы уже в списке участников!")
        return False

    if is_user_in_reserve(db_path, event_id, user_id):
        await query.answer("Вы уже в резерве!")
        return False

    # Удаляем из отказавшихся (если есть)
    if is_user_in_declined(db_path, event_id, user_id):
        remove_from_declined(db_path, event_id, user_id)

    # Добавляем в участники или резерв
    if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
        add_participant(db_path, event_id, user_id, user_name)
        await query.answer("✅ Вы теперь участвуете!")
        return True
    else:
        add_to_reserve(db_path, event_id, user_id, user_name)
        await query.answer("⏳ Вы добавлены в резерв")
        return True

async def handle_leave_action(db_path, event, user_id, user_name, query, context):
    """Обрабатывает действие 'Не участвовать'"""
    event_id = event["event_id"]
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        if not query.data or "|" not in query.data:
            logger.error(f"Invalid callback data: {query.data}")
            return

        action, event_id_str = query.data.split("|", 1)
        event_id = int(event_id_str)

        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            await query.answer("Мероприятие не найдено")
            return

        user = query.from_user
        user_id = user.id
        user_name = user.first_name
        if user.username:
            user_name += f" (@{user.username})"

        if action == "join":
            await handle_join_action(db_path, event, user_id, user_name, query)
        elif action == "leave":
            await handle_leave_action(db_path, event, user_id, user_name, query, context)
        elif action == "edit":
            await query.answer("Редактирование пока не реализовано")
            return
        else:
            logger.warning(f"Unknown event action: {action}")
            await query.answer("Неизвестное действие")
            return

        # Обновляем сообщение мероприятия
        await send_event_message(event_id, context, query.message.chat_id, query.message.message_id)

    except Exception as e:
        logger.error(f"Event button handler error: {e}")
        await query.answer("⚠ Ошибка обработки")

def register_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(join|leave|edit)\|"  # Четко указываем формат кнопок мероприятий
        )
    )