from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.handlers.create_event_handler import create_event_button
from src.buttons.my_events_button import my_events_button
from src.handlers.cancel_handler import cancel_draft
from src.logger.logger import logger


async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    try:
        if query.data.startswith("cancel_draft|"):
            await cancel_draft(update, context)
        elif data == "create_event":
            await create_event_button(update, context)
        elif data == "my_events":
            await my_events_button(update, context)
        elif data.startswith("cancel_draft|"):
            await cancel_draft(update, context)
        elif "|" in data:
            action, event_id = data.split("|", 1)
            # Здесь можно добавить обработку других действий
            logger.warning(f"Unhandled button action: {action} for event {event_id}")
        else:
            logger.warning(f"Unknown button data: {data}")
            await query.edit_message_text("Неизвестная команда.")
    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок: {e}")
        # Вместо попытки редактирования сообщения, отправляем новое
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Произошла ошибка при обработке команды"
        )


def register_menu_button_handler(application):
    application.add_handler(CallbackQueryHandler(menu_button_handler))