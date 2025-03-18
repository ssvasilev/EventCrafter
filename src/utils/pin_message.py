from telegram import error
import logging

logger = logging.getLogger(__name__)

async def pin_message(context, chat_id: int, message_id: int):
    """
    Закрепляет сообщение в чате.
    :param context: Контекст бота.
    :param chat_id: ID чата.
    :param message_id: ID сообщения.
    """
    try:
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=True  # Отключаем уведомление о закреплении
        )
        logger.info(f"Сообщение {message_id} закреплено в чате {chat_id}.")
    except error.BadRequest as e:
        logger.error(f"Ошибка при закреплении сообщения: {e}")
    except error.Forbidden as e:
        logger.error(f"Бот не имеет прав на закрепление сообщений: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при закреплении сообщения: {e}")
        raise e