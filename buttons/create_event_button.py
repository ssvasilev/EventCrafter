from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.conversation_handler_states import SET_DESCRIPTION
from database.db_operations import set_user_state  # Импорт функции для работы с базой данных

async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем новое сообщение и сохраняем его message_id
    sent_message = await query.message.reply_text(
        text="Введите описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Сохраняем message_id в базу данных
    set_user_state(
        db_path=context.bot_data["db_path"],
        user_id=user_id,
        chat_id=chat_id,
        state="SET_DESCRIPTION",
        bot_message_id=sent_message.message_id,  # Сохраняем message_id
    )

    # Переходим к состоянию SET_DESCRIPTION
    return SET_DESCRIPTION