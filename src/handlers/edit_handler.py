from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.database.db_operations import get_event
from src.handlers.cancel_handler import cancel_input
from src.handlers.conversation_handler_states import (
    EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT
)
from src.logger.logger import logger

async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора параметра для редактирования.
    Определяет, какое поле нужно изменить, и переводит в соответствующее состояние.
    """
    query = update.callback_query
    await query.answer()

    try:
        data = query.data

        # Обработка отмены
        if data == "cancel_input":
            return await cancel_input(update, context)

        # Разбираем callback_data: action|event_id
        action, event_id_str = data.split("|")
        event_id = int(event_id_str)

        # Проверяем существование мероприятия
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await query.edit_message_text("Мероприятие не найдено.")
            return ConversationHandler.END

        # Проверяем права пользователя
        if event["creator_id"] != query.from_user.id:
            await query.answer("Только автор может редактировать мероприятие.", show_alert=True)
            return ConversationHandler.END

        # Сохраняем event_id в context
        context.user_data["event_id"] = event_id

        # Создаем клавиатуру с кнопкой отмены
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Определяем, какое поле редактируем
        if action == "edit_description":
            await query.edit_message_text(
                "Введите новое описание мероприятия:",
                reply_markup=reply_markup
            )
            return EDIT_DESCRIPTION

        elif action == "edit_date":
            await query.edit_message_text(
                "Введите новую дату в формате ДД.ММ.ГГГГ:",
                reply_markup=reply_markup
            )
            return EDIT_DATE

        elif action == "edit_time":
            await query.edit_message_text(
                "Введите новое время в формате ЧЧ:ММ:",
                reply_markup=reply_markup
            )
            return EDIT_TIME

        elif action == "edit_limit":
            await query.edit_message_text(
                "Введите новый лимит участников (0 - неограниченный):",
                reply_markup=reply_markup
            )
            return EDIT_LIMIT

        elif action == "delete":
            # Удаление мероприятия обрабатывается в buttons.py
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка в handle_edit_choice: {e}")
        await query.edit_message_text("Произошла ошибка. Пожалуйста, попробуйте снова.")
        return ConversationHandler.END