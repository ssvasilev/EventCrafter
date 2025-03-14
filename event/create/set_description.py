from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.conversation_handler_states import SET_DATE
from database.db_operations import set_user_state, get_user_state  # Импорт функций


# Обработка ввода описания мероприятия
async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    description = update.message.text

    # Сохраняем описание и состояние в базу данных
    set_user_state(
        db_path=context.bot_data["db_path"],
        user_id=user_id,
        chat_id=chat_id,
        state="SET_DESCRIPTION",
        description=description,
        bot_message_id=context.user_data["bot_message_id"],  # Сохраняем message_id
    )

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,
        )
    except BadRequest as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await update.message.reply_text("Не удалось обновить сообщение. Пожалуйста, начните заново.")
        return ConversationHandler.END

    # Удаляем сообщение пользователя
    await update.message.delete()

    # Переходим к состоянию SET_DATE
    return SET_DATE