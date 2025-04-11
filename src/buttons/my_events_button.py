from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.database.db_operations import get_events_by_participant
from src.logger.logger import logger

#Обработка нажатия на кнопку "Мои мероприятия"
async def my_events_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    #await query.answer()

    user_id = query.from_user.id
    db_path = context.bot_data["db_path"]

    # Получаем мероприятия, в которых участвует пользователь
    events = get_events_by_participant(db_path, user_id)

    if not events:
        await query.edit_message_text("Вы не участвуете ни в одном мероприятии.")
        return

    # Группируем мероприятия по чатам
    events_by_chat = {}
    for event in events:
        chat_id = event["chat_id"]
        if chat_id not in events_by_chat:
            events_by_chat[chat_id] = []
        events_by_chat[chat_id].append(event)

    # Формируем сообщение с группировкой по чатам
    message_text = "📋 Мероприятия, в которых вы участвуете:\n\n"
    for chat_id, events_in_chat in events_by_chat.items():
        # Получаем информацию о чате
        try:
            chat = await context.bot.get_chat(chat_id)
            chat_name = chat.title or chat.username or f"Чат {chat_id}"
            chat_link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else f"Чат {chat_id}"
        except Exception as e:
            logger.error(f"Ошибка при получении информации о чате {chat_id}: {e}")
            chat_name = f"Чат {chat_id}"
            chat_link = f"Чат {chat_id}"

        message_text += f"💬 <b>{chat_name}</b> ({chat_link}):\n"
        for event in events_in_chat:
            event_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{event['message_id']}"
            message_text += f"  - <a href='{event_link}'>📅 {event['description']}</a> ({event['date']} {event['time']})\n"
        message_text += "\n"

    # Отправляем сообщение в личный чат с пользователем
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await query.edit_message_text("Список мероприятий отправлен вам в личные сообщения.")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await query.edit_message_text("Не удалось отправить сообщение. Пожалуйста, начните чат с ботом.")

    # Завершаем диалог
    return ConversationHandler.END