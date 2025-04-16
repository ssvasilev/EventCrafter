import asyncio

from telegram.error import BadRequest

from src.logger import logger


async def show_input_error(update, context, error_text):
    """Универсальный метод показа ошибок ввода"""
    try:
        # Сначала показываем всплывающее окно
        if update.message:
            await context.bot.answer_callback_query(
                callback_query_id=update.message.message_id,
                text=error_text,
                show_alert=False
            )
        # Затем удаляем сообщение (если это текстовый ввод)
        if update.message:
            try:
                await update.message.delete()
            except BadRequest:
                pass
    except Exception as e:
        logger.warning(f"Не удалось показать ошибку: {e}")
        # Fallback: отправляем временное сообщение
        try:
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text
            )
            await asyncio.sleep(5)
            await msg.delete()
        except Exception as fallback_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {fallback_error}")