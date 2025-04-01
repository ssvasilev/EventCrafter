from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.database.db_operations import (
    add_participant,
    remove_participant,
    add_to_declined,
    remove_from_reserve,
    get_event,
    remove_from_declined,
    is_user_in_participants,
    is_user_in_reserve,
    get_participants_count,
    add_to_reserve,
    get_reserve,
    is_user_in_declined,
)
from src.message.send_message import send_event_message
from src.logger.logger import logger

async def handle_reserve_promotion(db_path, event_id, context):
    """Обрабатывает перемещение пользователей из резерва в участники."""
    reserve = get_reserve(db_path, event_id)
    if not reserve:
        return None

    new_participant = reserve[0]
    remove_from_reserve(db_path, event_id, new_participant["user_id"])
    add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])
    return new_participant

#Обработка нажатий на кнопки "Участвовать" и "Не участвовать"
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Всегда отвечаем на callback, чтобы убрать часы загрузки

    try:
        user = query.from_user
        data = query.data

        # Проверяем формат callback_data
        if "|" not in data:
            logger.error(f"Некорректный формат callback_data: {data}")
            return

        action, event_id = data.split("|")
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            await query.edit_message_text("Мероприятие не найдено.")
            return

        user_id = user.id
        user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"
        chat_id = event["chat_id"]

        # Обработка действия "Участвовать"
        if action == "join":
            await handle_join_action(db_path, event, user_id, user_name, query, context)

        # Обработка действия "Не участвовать"
        elif action == "leave":
            await handle_leave_action(db_path, event, user_id, user_name, query, context)

        # Обновляем сообщение мероприятия
        await send_event_message(event_id, context, query.message.chat_id, query.message.message_id)

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        await query.edit_message_text("Произошла ошибка при обработке вашего запроса.")

async def handle_join_action(db_path, event, user_id, user_name, query, context):
    """Обрабатывает действие 'Участвовать'."""
    event_id = event["event_id"]

    # Если пользователь уже в участниках или резерве
    if is_user_in_participants(db_path, event_id, user_id) or is_user_in_reserve(db_path, event_id, user_id):
        await query.answer("Вы уже в списке участников или резерва.")
        return

    # Удаляем из отказавшихся (если есть)
    if is_user_in_declined(db_path, event_id, user_id):
        remove_from_declined(db_path, event_id, user_id)

    # Проверяем наличие мест
    if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
        add_participant(db_path, event_id, user_id, user_name)
        await query.answer(f"{user_name}, вы добавлены в список участников!")
    else:
        add_to_reserve(db_path, event_id, user_id, user_name)
        await query.answer(f"{user_name}, вы добавлены в резерв.")

async def handle_leave_action(db_path, event, user_id, user_name, query, context):
    """Обрабатывает действие 'Не участвовать'."""
    event_id = event["event_id"]
    chat_id = event["chat_id"]

    # Если пользователь в участниках
    if is_user_in_participants(db_path, event_id, user_id):
        remove_participant(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)

        new_participant = await handle_reserve_promotion(db_path, event_id, context)
        if new_participant:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👋 {user_name} больше не участвует.\n"
                     f"🎉 {new_participant['user_name']} перемещён(а) из резерва в участники!",
            )
            await query.answer(f"Вы удалены из участников. {new_participant['user_name']} теперь участвует.")
        else:
            await query.answer("Вы удалены из списка участников.")

    # Если пользователь в резерве
    elif is_user_in_reserve(db_path, event_id, user_id):
        remove_from_reserve(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)
        await query.answer("Вы удалены из резерва.")

    # Если пользователь уже в отказавшихся
    elif is_user_in_declined(db_path, event_id, user_id):
        await query.answer("Вы уже в списке отказавшихся.")

    # Если пользователь не в списках
    else:
        add_to_declined(db_path, event_id, user_id, user_name)
        await query.answer("Вы добавлены в список отказавшихся.")

def register_button_handler(application):
    application.add_handler(CallbackQueryHandler(button_handler, pattern=r"^(join|leave)\|"))