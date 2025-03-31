from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.handlers.conversation_handler_states import SET_LIMIT, SET_TIME
from src.database.db_draft_operations import update_draft, get_draft, set_user_state
from src.logger.logger import logger

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка восстановленной сессии
    if context.user_data.get("restored"):
        del context.user_data["restored"]
    elif 'draft_id' not in context.user_data:
        await update.message.reply_text("Сессия устарела. Начните заново.")
        return ConversationHandler.END

    # Получаем текст времени
    time_text = update.message.text
    try:
        time = datetime.strptime(time_text, "%H:%M").time()
        draft_id = context.user_data["draft_id"]

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            status="AWAIT_PARTICIPANT_LIMIT",
            time=time.strftime("%H:%M")
        )

        # Обновляем состояние
        handler_type = "mention_handler" if "description" in context.user_data else "create_event_handler"
        set_user_state(
            context.bot_data["drafts_db_path"],
            update.message.from_user.id,
            handler_type,
            SET_LIMIT,
            draft_id
        )

        # Получаем обновленный черновик
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            await update.message.reply_text("Ошибка: черновик не найден.")
            return ConversationHandler.END

        # Формируем клавиатуру
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем сообщение
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

        return SET_LIMIT

    except ValueError:
        # Ошибка формата времени
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_TIME