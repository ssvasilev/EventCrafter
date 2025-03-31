from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.handlers.conversation_handler_states import SET_TIME, SET_DATE
from src.database.db_draft_operations import update_draft, get_draft, set_user_state

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем инициализацию черновика
    if 'draft_id' not in context.user_data:
        await update.message.reply_text("Сессия устарела. Начните заново.")
        return ConversationHandler.END

    date_text = update.message.text
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=context.user_data["draft_id"],
            status="AWAIT_TIME",
            date=date.strftime("%d.%m.%Y")
        )

        # Обновляем состояние
        set_user_state(
            context.bot_data["drafts_db_path"],
            update.message.from_user.id,
            "mention_handler" if "description" in context.user_data else "create_event_handler",
            SET_TIME,
            context.user_data["draft_id"]
        )

        # Получаем данные черновика
        draft = get_draft(context.bot_data["drafts_db_path"], context.user_data["draft_id"])

        # Создаем клавиатуру
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем сообщение
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,
        )

        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_TIME

    except ValueError:
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_DATE