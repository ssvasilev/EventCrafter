from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.conversation_handler_states import SET_DATE


# Обработка ввода описания мероприятия
async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем описание мероприятия
    description = update.message.text
    context.user_data["description"] = description

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
        reply_markup=reply_markup,
    )

    # Удаляем сообщение пользователя
    await update.message.delete()

    # Переходим к состоянию SET_DATE
    return SET_DATE