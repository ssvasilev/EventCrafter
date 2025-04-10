from telegram import error
import logging

logger = logging.getLogger(__name__)

async def pin_message_safe(context, chat_id, message_id):
    """Безопасное закрепление сообщения с проверкой прав"""
    try:
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status in ['administrator', 'creator']:
            await context.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=message_id,
                disable_notification=True
            )
            logger.info(f"Сообщение {message_id} закреплено в чате {chat_id}")
        else:
            logger.warning(f"Бот не имеет прав для закрепления в чате {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка закрепления сообщения: {e}")