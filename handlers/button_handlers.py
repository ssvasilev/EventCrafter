from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

#from data.database import is_user_in_declined
from database.db_operations import (
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
from message.send_message import send_event_message


#Обработка нажатий на кнопки "Участвовать" и "Не участвовать"
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    # Разделяем action и event_id
    action, event_id = data.split("|")

    # Получаем путь к базе данных
    db_path = context.bot_data["db_path"]

    # Получаем данные о мероприятии
    event = get_event(db_path, event_id)

    if not event:
        await query.answer("Мероприятие не найдено.")
        return

    # Формируем имя пользователя
    user_id = user.id
    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

    # Обработка действия "Участвовать"
    if action == "join":
        # Если пользователь в списке "Отказавшиеся", удаляем его оттуда
        if is_user_in_declined(db_path, event_id, user_id):
            remove_from_declined(db_path, event_id, user_id)

        # Если пользователь уже в списке участников или резерва
        if is_user_in_participants(db_path, event_id, user_id) or is_user_in_reserve(db_path, event_id, user_id):
            await query.answer("Вы уже в списке участников или резерва.")
            return  # Прекращаем выполнение, так как данные не изменились

        # Если есть свободные места, добавляем в участники
        if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
            add_participant(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы добавлены в список участников!")
        else:
            # Если мест нет, добавляем в резерв
            add_to_reserve(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы добавлены в резерв.")

    # Обработка действия "Не участвовать"
    elif action == "leave":
        # Если пользователь в списке участников
        if is_user_in_participants(db_path, event_id, user_id):
            # Удаляем пользователя из участников
            remove_participant(db_path, event_id, user_id)
            # Добавляем его в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)

            # Если в резерве есть пользователи, перемещаем первого из резерва в участники
            reserve = get_reserve(db_path, event_id)
            if reserve:
                new_participant = reserve[0]
                remove_from_reserve(db_path, event_id, new_participant["user_id"])
                add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])

                # Отправляем сообщение в чат с упоминанием пользователей
                await context.bot.send_message(
                    chat_id=event["chat_id"],
                    text=f"👋 {user_name} больше не участвует в мероприятии.\n"
                         f"🎉 {new_participant['user_name']} был(а) перемещён(а) из резерва в список участников!",
                )

                await query.answer(
                    f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся. "
                    f"{new_participant['user_name']} перемещён(а) из резерва в участники."
                )
            else:
                await query.answer(f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся.")

        # Если пользователь в резерве
        elif is_user_in_reserve(db_path, event_id, user_id):
            # Удаляем пользователя из резерва
            remove_from_reserve(db_path, event_id, user_id)
            # Добавляем его в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы удалены из резерва и добавлены в список отказавшихся.")

        # Если пользователь уже в списке "Отказавшиеся"
        elif is_user_in_declined(db_path, event_id, user_id):
            await query.answer("Вы уже в списке отказавшихся.")
            return  # Прекращаем выполнение, так как данные не изменились

        # Если пользователя нет ни в одном из списков
        else:
            # Добавляем пользователя в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы добавлены в список отказавшихся.")

    # Редактируем сообщение только если данные изменились
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    await send_event_message(event_id, context, chat_id, message_id)