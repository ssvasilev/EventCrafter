from _pydatetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.conversation_handler_states import SET_TIME, SET_DATE


# Обработка ввода даты мероприятия
async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем дату мероприятия
    date_text = update.message.text
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()
        context.user_data["date"] = date

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {context.user_data['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Переходим к состоянию SET_TIME
        return SET_TIME
    except ValueError:
        # Если формат даты неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_DATE
        return SET_DATE