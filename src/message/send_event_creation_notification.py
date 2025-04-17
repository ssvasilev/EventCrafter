from datetime import datetime
from src.database.db_operations import get_event
from src.logger import logger
from telegram.error import BadRequest

async def send_event_creation_notification(context, event_id, bot_message_id):
    """Отправляет уведомление создателю о новом мероприятии, используя данные из БД"""
    try:
        if not event_id or not bot_message_id:
            logger.error("Не указаны event_id или bot_message_id для уведомления")
            return

        # Получаем данные о мероприятии
        try:
            event = get_event(context.bot_data["db_path"], event_id)
            if not event:
                logger.error(f"Мероприятие {event_id} не найдено в БД")
                return
        except Exception as e:
            logger.error(f"Ошибка получения мероприятия {event_id}: {e}")
            return

        # Получаем информацию о чате
        chat_info = await _get_chat_info(context, event.get("chat_id"))

        # Формируем сообщение
        message_text = await _format_notification_message(event, chat_info, bot_message_id)

        # Отправляем сообщение
        await context.bot.send_message(
            chat_id=event["creator_id"],
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except BadRequest as e:
        # Теперь event всегда определен (хотя может быть None)
        event = get_event(context.bot_data["db_path"], event_id)
        creator_id = event.get("creator_id") if event else "неизвестен"
        logger.error(f"Ошибка отправки сообщения creator_id {creator_id}: {e}")
    except Exception as e:
        logger.error(f"Критическая ошибка в уведомлении о мероприятии {event_id}: {e}", exc_info=True)

async def _get_chat_info(context, chat_id):
    """Получает информацию о чате"""
    if not chat_id:
        return {"name": "чат", "link": ""}

    try:
        chat = await context.bot.get_chat(chat_id)
        chat_name = chat.title or "чат"
        if str(chat_id).startswith('-100'):
            # Для супергрупп
            base_chat_id = str(chat_id)[4:]
            chat_link = f"https://t.me/c/{base_chat_id}"
        elif str(chat_id).startswith('-'):
            # Для обычных групп
            base_chat_id = str(abs(chat_id))
            chat_link = f"https://t.me/c/{base_chat_id}"
        else:
            # Для каналов
            chat_link = f"https://t.me/c/{chat_id}"
        return {"name": chat_name, "link": chat_link}
    except Exception as e:
        logger.warning(f"Не удалось получить информацию о чате {chat_id}: {e}")
        return {"name": "чат", "link": ""}

async def _format_notification_message(event, chat_info, bot_message_id):
    """Форматирует текст уведомления"""
    message_parts = [
        "✅ <b>Мероприятие создано!</b>",
        "",
        f"📢 <b>Название:</b> {event.get('description', 'Без названия')}"
    ]

    # Добавляем дату
    if event.get("date"):
        try:
            date_str = datetime.strptime(event["date"], "%d.%m.%Y").strftime("%d.%m.%Y (%A)")
            message_parts.append(f"📅 <b>Дата:</b> {date_str}")
        except ValueError:
            message_parts.append(f"📅 <b>Дата:</b> {event['date']}")

    # Добавляем время
    if event.get("time"):
        message_parts.append(f"🕒 <b>Время:</b> {event['time']}")

    # Добавляем лимит участников
    if "participant_limit" in event:
        limit = "∞" if event["participant_limit"] is None else event["participant_limit"]
        message_parts.append(f"👥 <b>Лимит участников:</b> {limit}")

    # Добавляем информацию о чате
    if chat_info["link"]:
        message_parts.append(f"💬 <b>Чат:</b> <a href='{chat_info['link']}'>{chat_info['name']}</a>")
    else:
        message_parts.append(f"💬 <b>Чат:</b> {chat_info['name']}")

    # Добавляем ссылку на мероприятие
    if event.get("chat_id") and bot_message_id:
        chat_id = event["chat_id"]
        # Формируем правильную ссылку в зависимости от типа чата
        if str(chat_id).startswith('-100'):
            # Для супергрупп (удаляем -100 и используем оставшуюся часть)
            base_chat_id = str(chat_id)[4:]
            event_link = f"https://t.me/c/{base_chat_id}/{bot_message_id}"
        elif str(chat_id).startswith('-'):
            # Для обычных групп (используем абсолютное значение без -100)
            base_chat_id = str(abs(chat_id))
            event_link = f"https://t.me/c/{base_chat_id}/{bot_message_id}"
        else:
            # Для каналов (chat_id положительный)
            event_link = f"https://t.me/c/{chat_id}/{bot_message_id}"

        message_parts.append(f"\n🔗 <a href='{event_link}'>Перейти к мероприятию</a>")

    return "\n".join(message_parts)