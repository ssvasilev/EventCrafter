from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters, ContextTypes,
)
from src.handlers.draft_handlers import handle_draft_message
from src.handlers.cancel_handler import cancel_draft, cancel
from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft


async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Создать мероприятие'"""
    query = update.callback_query
    await query.answer()

    creator_id = query.from_user.id
    chat_id = query.message.chat_id

    # Проверяем, есть ли уже активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)

    if draft:
        # Если черновик уже есть, отправляем текущее состояние
        return await handle_draft_message(update, context, draft)

    # Создаем новый черновик
    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=creator_id,
        chat_id=chat_id,
        status="AWAIT_DESCRIPTION"
    )

    if not draft_id:
        await query.edit_message_text("Ошибка при создании черновика мероприятия.")
        return

    # Отправляем сообщение с запросом описания
    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await query.message.reply_text(
        "Введите описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Сохраняем ID сообщения бота в черновик
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft_id,
        bot_message_id=sent_message.message_id
    )

# Обработчики для создания мероприятия
conv_handler_create = MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    lambda update, context: handle_draft_message(update, context)
)

# Добавляем обработчик отмены
cancel_handler = CallbackQueryHandler(cancel_draft, pattern="^cancel_draft\|")