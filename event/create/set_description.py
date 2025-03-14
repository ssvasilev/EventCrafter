from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest  # Импорт для обработки ошибок
from handlers.conversation_handler_states import SET_TIME, SET_DATE
from database.db_operations import set_user_state, get_user_state
from logger.logger import logger


async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    date_text = update.message.text

    try:
        # Парсим дату и проверяем корректность формата
        date = datetime.strptime(date_text, "%d.%m.%Y").date()

        # Получаем текущее состояние пользователя
        user_state = get_user_state(context.bot_data["db_path"], user_id)
        if not user_state:
            await update.message.reply_text("Ошибка: состояние пользователя не найдено.")
            return ConversationHandler.END

        # Проверяем, что message_id существует
        if "bot_message_id" not in user_state:
            await update.message.reply_text("Ошибка: ID сообщения не найдено.")
            return ConversationHandler.END

        # Обновляем состояние пользователя в базе данных
        set_user_state(
            db_path=context.bot_data["db_path"],
            user_id=user_id,
            chat_id=chat_id,
            state="SET_DATE",
            description=user_state.get("description"),
            date=date.strftime("%d.%m.%Y"),  # Сохраняем дату в формате строки
            time=user_state.get("time"),
            participant_limit=user_state.get("participant_limit"),
            event_id=user_state.get("event_id"),
            bot_message_id=user_state.get("bot_message_id"),
            original_text=user_state.get("original_text"),
            original_reply_markup=user_state.get("original_reply_markup"),
        )

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Редактируем сообщение бота
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_state["bot_message_id"],
                text=f"📢 {user_state['description']}\n\n📅 Дата: {date_text}\n\n🕒 Введите время мероприятия в формате ЧЧ:ММ",
                reply_markup=reply_markup,
            )
        except BadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await update.message.reply_text("Не удалось обновить сообщение. Пожалуйста, начните заново.")
            return ConversationHandler.END

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Переходим к состоянию SET_TIME
        return SET_TIME

    except ValueError:
        # Если формат даты неверный, выводим ошибку
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_state["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_DATE
        return SET_DATE