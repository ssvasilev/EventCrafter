from datetime import datetime

from src.logger import logger


async def _send_event_creation_notification(context, draft, bot_message_id):
    """Отправляет уведомление создателю о новом мероприятии с проверкой данных"""
    try:
        # Проверяем обязательные поля
        if not draft or not bot_message_id:
            logger.error("Недостаточно данных для уведомления")
            return

        # Получаем информацию о чате
        chat_name = "чат"
        chat_link = ""
        try:
            chat = await context.bot.get_chat(draft["chat_id"])
            chat_name = chat.title or "чат"
            if str(draft["chat_id"]).startswith('-'):
                chat_link = f"https://t.me/c/{str(abs(draft['chat_id']))}"
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о чате: {e}")

        # Формируем ссылку на мероприятие
        chat_id_link = str(abs(draft["chat_id"])) if draft.get("chat_id") else ""
        event_link = f"https://t.me/c/{chat_id_link}/{bot_message_id}" if chat_id_link else ""

        # Обрабатываем дату мероприятия
        date_str = ""
        if draft.get("date"):
            try:
                event_date = datetime.strptime(draft["date"], "%d.%m.%Y")
                date_str = event_date.strftime("%d.%m.%Y (%A)")
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка форматирования даты: {e}")
                date_str = draft["date"]  # Используем как есть, если не удалось распарсить

        # Формируем текст сообщения
        message_parts = [
            "✅ <b>Мероприятие создано!</b>",
            "",
            f"📢 <b>Название:</b> {draft.get('description', 'Без названия')}"
        ]

        if date_str:
            message_parts.append(f"📅 <b>Дата:</b> {date_str}")
        if draft.get("time"):
            message_parts.append(f"🕒 <b>Время:</b> {draft['time']}")

        if chat_link:
            message_parts.append(f"💬 <b>Чат:</b> <a href='{chat_link}'>{chat_name}</a>")
        else:
            message_parts.append(f"💬 <b>Чат:</b> {chat_name}")

        if event_link:
            message_parts.append(f"\n🔗 <a href='{event_link}'>Перейти к мероприятию</a>")

        message_text = "\n".join(message_parts)

        await context.bot.send_message(
            chat_id=draft["creator_id"],
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Критическая ошибка уведомления создателя: {e}", exc_info=True)