from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.handlers.conversation_handler_states import SET_LIMIT, SET_TIME
from src.database.db_draft_operations import update_draft, get_draft

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст времени
    time_text = update.message.text
    try:
        time = datetime.strptime(time_text, "%H:%M").time()

        # Получаем ID черновика из user_data
        draft_id = context.user_data["draft_id"]

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_PARTICIPANT_LIMIT",
            time=time.strftime("%H:%M")
        )

        # Получаем данные черновика из базы данных
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик мероприятия не найден.")
            return ConversationHandler.END

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Если нет сохранённого сообщения бота - отправляем новое
        if "bot_message_id" not in context.user_data or not context.user_data["bot_message_id"]:
            sent_message = await update.message.reply_text(
                f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
                reply_markup=reply_markup,
            )
            context.user_data["bot_message_id"] = sent_message.message_id
        else:
            # Иначе редактируем существующее
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["bot_message_id"],
                    text=f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
                    reply_markup=reply_markup,
                )
            except BadRequest:
                pass

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Переходим к состоянию SET_LIMIT
        return SET_LIMIT

    except ValueError:
        # Если формат времени неверный
        error_message = "Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ"

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

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Остаемся в состоянии SET_TIME
        return SET_TIME