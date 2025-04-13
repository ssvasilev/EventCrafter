from datetime import datetime

from src.logger import logger


async def _send_event_creation_notification(context, draft, bot_message_id):
    """Отправляет уведомление создателю о новом мероприятии (общая функция)"""
    try:
        # Получаем информацию о чате
        try:
            chat = await context.bot.get_chat(draft["chat_id"])
            chat_name = chat.title
            chat_link = f"https://t.me/c/{str(abs(draft['chat_id']))}" if str(draft['chat_id']).startswith('-') else ""
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о чате: {e}")
            chat_name = "чат"
            chat_link = ""

        # Формируем ссылку на мероприятие
        chat_id_link = str(abs(draft["chat_id"]))  # Убираем "-" для supergroups
        event_link = f"https://t.me/c/{chat_id_link}/{bot_message_id}"

        # Форматируем дату с днём недели
        event_date = datetime.strptime(draft["date"], "%d.%m.%Y").strftime("%d.%m.%Y (%A)")

        # Формируем текст сообщения
        message_text = (
            f"✅ <b>Мероприятие создано!</b>\n\n"
            f"📢 <b>Название:</b> <a href='{event_link}'>{draft['description']}</a>\n"
            f"📅 <b>Дата:</b> {event_date}\n"
            f"🕒 <b>Время:</b> {draft['time']}\n"
        )

        # Добавляем информацию о чате, если удалось получить
        if chat_link:
            message_text += f"💬 <b>Чат:</b> <a href='{chat_link}'>{chat_name}</a>\n"
        else:
            message_text += f"💬 <b>Чат:</b> {chat_name}\n"

        # Добавляем ссылку на мероприятие
        message_text += f"\n🔗 <a href='{event_link}'>Перейти к мероприятию</a>"

        await context.bot.send_message(
            chat_id=draft["creator_id"],
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Ошибка уведомления создателя: {e}", exc_info=True)