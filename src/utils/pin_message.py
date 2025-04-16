import telegram
import logging

logger = logging.getLogger(__name__)


async def pin_message_safe(context, chat_id, message_id):
    """Улучшенная функция закрепления"""
    logger.warning(f"Начинаем закреплять сообщение  {message_id} в чате {chat_id}")
    try:
        # Проверяем права бота
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)

        if bot_member.status not in ['administrator', 'creator']:
            logger.warning(f"Бот не имеет прав администратора в чате {chat_id}. Статус: {bot_member.status}")
            return False

        # Проверяем, не закреплено ли сообщение уже
        chat = await context.bot.get_chat(chat_id)
        if chat.pinned_message and chat.pinned_message.message_id == message_id:
            logger.info(f"Сообщение {message_id} уже закреплено")
            return True

        # Закрепляем с таймаутами
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=True,
            read_timeout=20,
            write_timeout=20,
            connect_timeout=20
        )
        logger.info(f"Успешно закреплено сообщение {message_id} в чате {chat_id}")
        return True

    except telegram.error.BadRequest as e:
        if "not enough rights" in str(e).lower():
            logger.warning(f"Нет прав для закрепления в чате {chat_id}")
        else:
            logger.error(f"Ошибка Telegram при закреплении: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при закреплении: {e}")

    return False