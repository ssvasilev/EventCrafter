from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
        [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await update.message.reply_text(
        "Привет! Я бот для организации мероприятий. Выберите действие:",
        reply_markup=reply_markup,
    )

    context.user_data["bot_message_id"] = sent_message.message_id
    context.user_data["chat_id"] = update.message.chat_id