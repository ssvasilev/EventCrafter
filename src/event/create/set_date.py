from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.handlers.conversation_handler_states import SET_TIME, SET_DATE
from src.database.db_draft_operations import update_draft, get_draft
from src.logger.logger import logger

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст даты
    date_text = update.message.text
    try:
        # Проверяем, что в user_data есть draft_id
        if "draft_id" not in context.user_data:
            await update.message.reply_text("Ошибка: сессия создания мероприятия утеряна. Начните заново.")
            return ConversationHandler.END

        # Парсим дату
        datetime.strptime(date_text, "%d.%m.%Y").date()

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=context.user_data["draft_id"],
            status="AWAIT_TIME",
            date=date_text
        )

        # Получаем обновленный черновик
        draft = get_draft(context.bot_data["drafts_db_path"], context.user_data["draft_id"])
        if not draft:
            await update.message.reply_text("Ошибка: черновик мероприятия не найден.")
            return ConversationHandler.END

        # Отправляем запрос времени
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if "bot_message_id" in context.user_data:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["bot_message_id"],
                    text=f"📢 {draft['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
                    reply_markup=reply_markup,
                )
            except BadRequest:
                pass
        else:
            sent_message = await update.message.reply_text(
                f"📢 {draft['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
                reply_markup=reply_markup,
            )
            context.user_data["bot_message_id"] = sent_message.message_id

        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_TIME

    except ValueError:
        # Если формат даты неверный
        error_message = "Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ"

        # Если нет сохранённого сообщения бота - отправляем новое
        if "bot_message_id" not in context.user_data or not context.user_data["bot_message_id"]:
            sent_message = await update.message.reply_text(
                error_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
            )
            context.user_data["bot_message_id"] = sent_message.message_id
        else:
            # Иначе редактируем существующее
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["bot_message_id"],
                    text=error_message,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
                )
            except BadRequest:
                pass
            else:
                sent_message = await update.message.reply_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
                )
                context.user_data["bot_message_id"] = sent_message.message_id

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Остаемся в состоянии SET_DATE
        return SET_DATE