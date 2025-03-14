from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from handlers.conversation_handler_states import SET_DESCRIPTION
from database.db_draft_operations import add_draft

async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем черновик мероприятия
    creator_id = query.from_user.id
    chat_id = query.message.chat_id
    draft_id = add_draft(
        db_path=context.bot_data["db_path"],
        creator_id=creator_id,
        chat_id=chat_id,
        status="AWAIT_DESCRIPTION"
    )

    if not draft_id:
        await query.edit_message_text("Ошибка при создании черновика мероприятия.")
        return ConversationHandler.END

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=query.message.message_id,
        text="Введите описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Сохраняем ID черновика в user_data
    context.user_data["draft_id"] = draft_id

    # Переходим к состоянию SET_DESCRIPTION
    return SET_DESCRIPTION