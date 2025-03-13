from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.conversation_handler_states import EDIT_EVENT

# Обработчик нажатия на кнопку "Редактировать"
async def edit_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Сохраняем исходное состояние сообщения
    context.user_data["original_text"] = query.message.text
    context.user_data["original_reply_markup"] = query.message.reply_markup

    # Сохраняем event_id и message_id в context.user_data
    event_id = query.data.split("|")[1]
    context.user_data["event_id"] = event_id
    context.user_data["bot_message_id"] = query.message.message_id

    # Создаем клавиатуру для выбора параметра редактирования
    keyboard = [
        [
            InlineKeyboardButton("📝 Описание", callback_data=f"edit_description|{event_id}"),
            InlineKeyboardButton("👥 Лимит участников", callback_data=f"edit_limit|{event_id}")
        ],
        [
            InlineKeyboardButton("📅 Дата", callback_data=f"edit_date|{event_id}"),
            InlineKeyboardButton("🕒 Время", callback_data=f"edit_time|{event_id}")
        ],
        [
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete|{event_id}"),
            InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем сообщение с кнопкой "Редактировать"
    await query.edit_message_text(
        "Что вы хотите изменить?",
        reply_markup=reply_markup,
    )
    return EDIT_EVENT