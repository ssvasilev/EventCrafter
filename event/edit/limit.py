from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from database.db_operations import update_event_field
from handlers.conversation_handler_states import EDIT_LIMIT
from logger.logger import logger
from message.send_message import send_event_message

# Обработка редактирования лимита участников
async def edit_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите новый лимит участников (0 - неограниченное):",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию EDIT_LIMIT
    return EDIT_LIMIT

# Обработка ввода нового лимита
async def save_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем новый лимит
    limit_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        # Преобразуем введённый текст в число
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Обновляем лимит в базе данных
        update_event_field(db_path, event_id, "participant_limit", limit if limit != 0 else None)

        # Удаляем последнее сообщение бота с запросом нового лимита
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, update.message.chat_id)

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END
    except ValueError:
        # Если введённый текст не является числом или лимит отрицательный
        error_message = (
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )

        # Редактируем существующее сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=error_message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии EDIT_LIMIT
        return EDIT_LIMIT
    except BadRequest as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при обновлении лимита.")
        return ConversationHandler.END