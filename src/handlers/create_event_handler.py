from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft
from src.logger.logger import logger

async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Создать мероприятие'"""
    query = update.callback_query
    await query.answer()

    creator_id = query.from_user.id
    chat_id = query.message.chat_id

    # Проверяем существующий черновик
    if get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id):
        await query.edit_message_text("У вас уже есть активное создание мероприятия")
        return

    # Создаем новый черновик БЕЗ event_id (так как это новое мероприятие)
    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=creator_id,
        chat_id=chat_id,
        status="AWAIT_DESCRIPTION"
    )

    if not draft_id:
        await query.edit_message_text("Ошибка при создании мероприятия")
        return

    # Отправляем запрос описания
    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]
    sent_message = await context.bot.send_message(
        chat_id=chat_id,
        text="✏️ Введите описание мероприятия:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Сохраняем ID сообщения бота
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft_id,
        bot_message_id=sent_message.message_id
    )

# Регистрация обработчика
def register_create_handlers(application):
    application.add_handler(CallbackQueryHandler(
        create_event_button,
        pattern="^create_event$"
    ))