from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft
from src.handlers.draft_handlers import handle_draft_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем, есть ли уже активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)

    if draft:
        # Если есть черновик, обрабатываем сообщение как ввод данных
        return await handle_draft_message(update, context, draft)

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