from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.conversation_handler_states import SET_LIMIT
from database.db_operations import update_draft

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст времени
    time_text = update.message.text
    try:
        time = datetime.strptime(time_text, "%H:%M").time()

        # Обновляем черновик
        draft_id = context.user_data["draft_id"]
        update_draft(
            db_path=context.bot_data["db_path"],
            draft_id=draft_id,
            status="AWAIT_PATICIPANT_LIMIT",
            time=time.strftime("%H:%M")
        )

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {context.user_data['description']}\n\n📅 Дата: {context.user_data['date'].strftime('%d.%m.%Y')}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
            reply_markup=reply_markup,
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

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

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_TIME
        return SET_TIME