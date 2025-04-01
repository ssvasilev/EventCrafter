from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.handlers.edit_event_handlers import logger


async def show_main_menu(bot, chat_id, user_id):
    """Показывает главное меню"""
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
        [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await bot.send_message(
            chat_id=chat_id,
            text="Главное меню:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при показе меню: {e}")