from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.handlers.conversation_handler_states import SET_LIMIT, SET_TIME
from src.database.db_draft_operations import update_draft, get_draft, set_user_state


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
        if 'cancel_message_sent' in context.user_data:
            del context.user_data['cancel_message_sent']

        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
            reply_markup=reply_markup,
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Сохраняем состояние перед переходом к следующему шагу
        handler = "mention_handler" if "description" in context.user_data else "create_event_handler"
        set_user_state(
            context.bot_data["drafts_db_path"],
            update.message.from_user.id,
            handler,
            SET_LIMIT,
            draft_id
        )

        # Переходим к состоянию SET_LIMIT
        return SET_LIMIT
    except ValueError:
        # Если формат времени неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        # Остаемся в состоянии SET_TIME
        return SET_TIME