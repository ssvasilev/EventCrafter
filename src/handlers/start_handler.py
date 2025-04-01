from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.db_draft_operations import get_user_chat_draft
from src.handlers.draft_handlers import handle_draft_input


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем, есть ли активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)

    if draft:
        # Передаем только update и context, так как handle_draft_message сама найдет черновик
        return await handle_draft_input(update, context)

    # Создаем клавиатуру
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
        [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет! Я бот для организации мероприятий. Выберите действие:",
        reply_markup=reply_markup,
    )