from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from handlers.conversation_handler_states import SET_TIME, SET_LIMIT
from database.db_operations import set_user_state, get_user_state
from logger.logger import logger

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    time_text = update.message.text

    try:
        # Парсим время и проверяем корректность формата
        time = datetime.strptime(time_text, "%H:%M").time()

        # Получаем текущее состояние пользователя
        user_state = get_user_state(context.bot_data["db_path"], user_id)
        if not user_state:
            await update.message.reply_text("Ошибка: состояние пользователя не найдено.")
            return ConversationHandler.END

        # Проверяем, что message_id существует
        if "bot_message_id" not in user_state:
            await update.message.reply_text("Ошибка: ID сообщения не найдено.")
            return ConversationHandler.END

        # Логируем message_id перед редактированием
        logger.info(f"Редактируем сообщение с ID: {user_state['bot_message_id']}")

        # Обновляем состояние пользователя в базе данных
        set_user_state(
            db_path=context.bot_data["db_path"],
            user_id=user_id,
            chat_id=chat_id,
            state="SET_TIME",
            description=user_state.get("description"),
            date=user_state.get("date"),
            time=time.strftime("%H:%M"),  # Сохраняем время в формате строки
            participant_limit=user_state.get("participant_limit"),
            event_id=user_state.get("event_id"),
            bot_message_id=user_state.get("bot_message_id"),  # Сохраняем message_id
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
                text=f"📢 {user_state['description']}\n\n📅 Дата: {user_state['date']}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
                reply_markup=reply_markup,
            )
        except BadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await update.message.reply_text("Не удалось обновить сообщение. Пожалуйста, начните заново.")
            return ConversationHandler.END

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Переходим к состоянию SET_LIMIT
        return SET_LIMIT

    except ValueError:
        # Если формат времени неверный, выводим ошибку
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_state["bot_message_id"],
                text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
            )
        except BadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await update.message.reply_text("Не удалось обновить сообщение. Пожалуйста, начните заново.")
            return ConversationHandler.END

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_TIME
        return SET_TIME