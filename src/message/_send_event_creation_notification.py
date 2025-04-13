from datetime import datetime

from src.logger import logger


async def _send_event_creation_notification(context, event_id, bot_message_id):
    """Отправляет уведомление создателю о новом мероприятии, используя данные из БД"""
    try:
        # Получаем полные данные о мероприятии
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            logger.error(f"Мероприятие {event_id} не найдено для уведомления")
            return

        # Получаем информацию о чате
        chat_name = "чат"
        chat_link = ""
        try:
            chat = await context.bot.get_chat(event["chat_id"])
            chat_name = chat.title or "чат"
            if str(event["chat_id"]).startswith('-'):
                chat_link = f"https://t.me/c/{str(abs(event['chat_id']))}"
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о чате: {e}")

        # Формируем ссылку на мероприятие
        chat_id_link = str(abs(event["chat_id"])) if event.get("chat_id") else ""
        event_link = f"https://t.me/c/{chat_id_link}/{bot_message_id}" if chat_id_link else ""

        # Форматируем дату с днём недели
        date_str = ""
        if event.get("date"):
            try:
                event_date = datetime.strptime(event["date"], "%d.%m.%Y")
                date_str = event_date.strftime("%d.%m.%Y (%A)")
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка форматирования даты мероприятия {event_id}: {e}")
                date_str = event["date"]  # Используем как есть, если не удалось распарсить

        # Формируем текст сообщения
        message_parts = [
            "✅ <b>Мероприятие создано!</b>",
            "",
            f"📢 <b>Название:</b> {event.get('description', 'Без названия')}"
        ]

        if date_str:
            message_parts.append(f"📅 <b>Дата:</b> {date_str}")
        if event.get("time"):
            message_parts.append(f"🕒 <b>Время:</b> {event['time']}")

        if event.get("participant_limit") is not None:
            limit = "∞" if event["participant_limit"] is None else event["participant_limit"]
            message_parts.append(f"👥 <b>Лимит участников:</b> {limit}")

        if chat_link:
            message_parts.append(f"💬 <b>Чат:</b> <a href='{chat_link}'>{chat_name}</a>")
        else:
            message_parts.append(f"💬 <b>Чат:</b> {chat_name}")

        if event_link:
            message_parts.append(f"\n🔗 <a href='{event_link}'>Перейти к мероприятию</a>")

        message_text = "\n".join(message_parts)

        await context.bot.send_message(
            chat_id=event["creator_id"],
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Критическая ошибка уведомления о мероприятии {event_id}: {e}", exc_info=True)