from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.conversation_handler_states import SET_DESCRIPTION


# Обработка нажатия на кнопку "Создать мероприятие"
async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию SET_DESCRIPTION
    return SET_DESCRIPTION