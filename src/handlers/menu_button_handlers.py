from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.handlers.create_event_handler import create_event_button
from src.buttons.my_events_button import my_events_button
from src.handlers.cancel_handler import cancel_draft
from src.handlers.cancel_utils import cancel_input
from src.handlers.edit_handlers import cancel_edit
from src.logger.logger import logger

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        if data.startswith("menu_"):
            action = data[5:]  # Убираем префикс "menu_"

            if action == "create_event":
                await create_event_button(update, context)
            elif action == "my_events":
                await my_events_button(update, context)
            else:
                logger.warning(f"Unknown menu action: {action}")
                await query.edit_message_text("Неизвестная команда меню.")

        elif data.startswith("cancel_"):
            action = data[7:]  # Убираем префикс "cancel_"

            if action.startswith("draft|"):
                await cancel_draft(update, context)
            elif action.startswith("input|"):
                await cancel_input(update, context)
            elif action.startswith("edit|"):
                # Обработка отмены редактирования
                await cancel_edit(update, context)
            else:
                logger.warning(f"Unknown cancel action: {action}")
                await query.edit_message_text("Неизвестная команда отмены.")

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок меню: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Произошла ошибка при обработке команды меню"
        )

def register_menu_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            menu_button_handler,
            pattern=r"^(menu_|cancel_)"  # Обрабатываем только menu_* и cancel_*
        )
    )