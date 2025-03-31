from telegram import Update
from telegram.ext import ContextTypes
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


#Обработка нажатий на кнопки "Участвовать" и "Не участвовать"
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()  # Всегда отвечаем на callback_query

        if not query or not query.data:
            logger.warning("Пустой callback_query или callback_data")
            return

        # Безопасное разделение данных
        if "|" not in query.data:
            logger.warning(f"Некорректный формат callback_data: {query.data}")
            return

        action, event_id = query.data.split("|", 1)
        user = query.from_user
        user_id = user.id
        user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

        # Получаем данные о мероприятии
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            await query.edit_message_text("⚠ Мероприятие не найдено")
            return

        # Обработка разных действий
        if action == "join":
            await handle_join_action(db_path, event, user_id, user_name, query, context)
        elif action == "leave":
            await handle_leave_action(db_path, event, user_id, user_name, query, context)
        elif action == "edit":
            await handle_edit_action(event, query, context)
        else:
            logger.warning(f"Неизвестное действие: {action}")
            await query.edit_message_text("⚠ Неизвестная команда")

        # Обновляем сообщение мероприятия
        await update_event_message(event_id, query, context)

    except ValueError as e:
        logger.error(f"Ошибка обработки callback_data: {e}")
        await query.edit_message_text("⚠ Ошибка обработки запроса")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в button_handler: {e}")
        if 'query' in locals():
            await query.edit_message_text("⚠ Произошла непредвиденная ошибка")

async def handle_join_action(db_path, event, user_id, user_name, query, context):
    """Обработка действия 'Участвовать'"""
    event_id = event["id"]

    if is_user_in_declined(db_path, event_id, user_id):
        remove_from_declined(db_path, event_id, user_id)

    if is_user_in_participants(db_path, event_id, user_id):
        await query.answer("Вы уже в списке участников")
        return

    if is_user_in_reserve(db_path, event_id, user_id):
        await query.answer("Вы уже в резерве")
        return

    if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
        add_participant(db_path, event_id, user_id, user_name)
        await query.answer(f"✅ Вы добавлены в список участников!")
    else:
        add_to_reserve(db_path, event_id, user_id, user_name)
        await query.answer("⏳ Вы добавлены в резерв")

async def handle_leave_action(db_path, event, user_id, user_name, query, context):
    """Обработка действия 'Не участвовать'"""
    event_id = event["id"]
    chat_id = event["chat_id"]

    if is_user_in_participants(db_path, event_id, user_id):
        remove_participant(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)

        reserve = get_reserve(db_path, event_id)
        if reserve:
            new_participant = reserve[0]
            remove_from_reserve(db_path, event_id, new_participant["user_id"])
            add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])

            await context.bot.send_message(
                chat_id=chat_id,
                text=f"👋 {user_name} больше не участвует\n"
                     f"🎉 {new_participant['user_name']} перемещён(а) из резерва"
            )
            await query.answer("❌ Вы больше не участвуете (резерв перемещён)")
        else:
            await query.answer("❌ Вы больше не участвуете")

    elif is_user_in_reserve(db_path, event_id, user_id):
        remove_from_reserve(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)
        await query.answer("❌ Вы удалены из резерва")

    elif is_user_in_declined(db_path, event_id, user_id):
        await query.answer("Вы уже отказались")
    else:
        add_to_declined(db_path, event_id, user_id, user_name)
        await query.answer("❌ Вы отказались от участия")

async def handle_edit_action(event, query, context):
    """Обработка действия 'Редактировать'"""
    # Здесь должна быть логика редактирования
    await query.answer("Функция редактирования в разработке")

async def update_event_message(event_id, query, context):
    """Обновляет сообщение о мероприятии"""
    try:
        await send_event_message(
            event_id,
            context,
            query.message.chat_id,
            query.message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при обновлении сообщения: {e}")
        await query.answer("⚠ Не удалось обновить сообщение")