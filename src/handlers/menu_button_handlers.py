from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.handlers.create_event_handler import create_event_button
from src.buttons.my_events_button import my_events_button
from src.database.db_draft_operations import delete_draft, get_draft
from src.database.db_operations import get_event
from src.message.send_message import send_event_message
from src.logger.logger import logger

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        data = query.data
        if not data or '_' not in data:
            raise ValueError("Invalid callback data format")

        prefix, action = data.split('_', 1)  # Разделяем по первому символу _

        if prefix == "menu":
            await handle_menu_action(query, context, action)
        elif prefix == "cancel":
            await handle_cancel_action(query, context, action)
        else:
            raise ValueError(f"Unknown prefix: {prefix}")

    except ValueError as e:
        logger.warning(f"Invalid menu button action: {str(e)}")
        await query.edit_message_text("⚠️ Неверный формат команды")
    except Exception as e:
        logger.error(f"Menu handler error: {str(e)}")
        await query.edit_message_text("⚠️ Ошибка обработки команды")

async def handle_menu_action(query, context, action):
    """Обработка действий из меню"""
    if action == "create_event":
        await create_event_button(query, context)
    elif action == "my_events":
        await my_events_button(query, context)
    else:
        logger.warning(f"Unknown menu action: {action}")
        await query.edit_message_text("Неизвестная команда меню")

async def handle_cancel_action(query, context, action_data):
    """Унифицированный обработчик отмены"""
    try:
        if not action_data or '|' not in action_data:
            raise ValueError("Invalid cancel action format")

        action_type, item_id = action_data.split('|', 1)
        item_id = int(item_id)

        if action_type == "draft":
            # Отмена черновика
            delete_draft(context.bot_data["drafts_db_path"], item_id)
            await query.message.delete()
        elif action_type == "input":
            # Отмена ввода при редактировании
            draft = get_draft(context.bot_data["drafts_db_path"], item_id)
            if draft and draft.get("event_id"):
                await send_event_message(
                    draft["event_id"],
                    context,
                    query.message.chat_id,
                    message_id=draft.get("original_message_id")
                )
                delete_draft(context.bot_data["drafts_db_path"], item_id)
        else:
            raise ValueError(f"Unknown cancel type: {action_type}")

    except Exception as e:
        logger.error(f"Cancel action failed: {str(e)}")
        await query.edit_message_text("⚠️ Не удалось выполнить отмену")

def register_menu_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            menu_button_handler,
            pattern=r"^(menu|cancel)_"  # Четкое разделение префиксов
        )
    )