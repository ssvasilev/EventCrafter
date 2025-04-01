from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_draft_operations import delete_draft, get_user_drafts
from src.handlers.menu import show_main_menu
from src.logger import logger


async def cancel_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная отмена создания мероприятия"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        delete_draft(context.bot_data["drafts_db_path"], draft_id)
        await show_main_menu(context.bot, query.message.chat_id, query.from_user.id)
    except Exception as e:
        logger.error(f"Ошибка при отмене черновика: {e}")
        await show_main_menu(context.bot, query.message.chat_id, query.from_user.id)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    drafts = get_user_drafts(context.bot_data["drafts_db_path"], user_id)
    for draft in drafts:
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    await show_main_menu(context.bot, chat_id, user_id)