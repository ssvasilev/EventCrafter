from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from src.handlers.conversation_handler_states import SET_DATE
from src.database.db_draft_operations import update_draft

async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст описания
    description = update.message.text

    # Обновляем черновик
    draft_id = context.user_data["draft_id"]
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft_id,
        status="AWAIT_DATE",
        description=description
    )

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Если нет сохранённого сообщения бота - отправляем новое
    if "bot_message_id" not in context.user_data or not context.user_data["bot_message_id"]:
        sent_message = await update.message.reply_text(
            f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,
        )
        context.user_data["bot_message_id"] = sent_message.message_id
    else:
        # Иначе редактируем существующее
        try:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=context.user_data["bot_message_id"],
                text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=reply_markup,
            )
        except BadRequest:
            pass

    try:
        await update.message.delete()
    except BadRequest:
        pass  # Продолжаем выполнение, даже если не удалось удалить сообщение

    # Переходим к состоянию SET_DATE
    return SET_DATE