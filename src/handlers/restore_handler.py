from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_state, get_draft, clear_user_state, get_db_connection, \
    get_active_user_state
from src.handlers.conversation_handler_states import *

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.db_draft_operations import get_draft, clear_user_state
from src.handlers.conversation_handler_states import *
from src.logger.logger import logger

async def restore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Пропускаем команды и не текстовые сообщения
        if not update.message or not update.message.text or update.message.text.startswith('/'):
            return None

        user_id = update.message.from_user.id
        db_path = context.bot_data["drafts_db_path"]

        # Получаем активное состояние пользователя
        user_state = get_active_user_state(db_path, user_id)
        if not user_state:
            return None

        # Получаем черновик
        draft = get_draft(db_path, user_state["draft_id"])
        if not draft:
            clear_user_state(db_path, user_id)
            return None

        # Преобразуем в dict если нужно
        draft = dict(draft) if hasattr(draft, 'keys') else draft

        # Подготавливаем контекст
        context.user_data.update({
            "draft_id": draft["id"],
            "description": draft.get("description"),
            "date": draft.get("date"),
            "time": draft.get("time"),
            "restored": True  # Флаг восстановленной сессии
        })

        # Формируем текст сообщения в зависимости от состояния
        message_text = get_restored_message_text(draft, user_state["state"])
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        )

        # Отправляем новое сообщение
        try:
            message = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=message_text,
                reply_markup=reply_markup
            )
            context.user_data["bot_message_id"] = message.message_id
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return None

        # Перенаправляем в нужный обработчик
        return await redirect_to_state_handler(update, context, user_state["handler"], user_state["state"])

    except Exception as e:
        logger.error(f"Ошибка восстановления: {e}")
        if 'db_path' in locals() and 'user_id' in locals():
            clear_user_state(db_path, user_id)
        return None





def get_restored_message_text(draft, state):
    """Генерирует текст сообщения для восстановленной сессии"""
    base_text = f"📢 {draft.get('description', '')}\n\n" if draft.get('description') else ""

    if state == SET_DESCRIPTION:
        return f"{base_text}Введите описание мероприятия:"
    elif state == SET_DATE:
        return f"{base_text}Введите дату мероприятия (ДД.ММ.ГГГГ):"
    elif state == SET_TIME:
        return f"{base_text}📅 Дата: {draft.get('date', '')}\n\nВведите время (ЧЧ:ММ):"
    elif state == SET_LIMIT:
        return f"{base_text}📅 Дата: {draft.get('date', '')}\n\n🕒 Время: {draft.get('time', '')}\n\nВведите лимит участников:"
    return "Восстановлена сессия создания мероприятия"


async def redirect_to_state_handler(update, context, handler_name, state):
    """Перенаправляет в соответствующий обработчик состояния"""
    try:
        if handler_name == "create_event_handler":
            if state == SET_DESCRIPTION:
                from src.event.create.set_description import set_description
                return await set_description(update, context)
            elif state == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            elif state == SET_TIME:
                from src.event.create.set_time import set_time
                return await set_time(update, context)
            elif state == SET_LIMIT:
                from src.event.create.set_limit import set_limit
                return await set_limit(update, context)

        elif handler_name == "mention_handler":
            if state == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            elif state == SET_TIME:
                from src.event.create.set_time import set_time
                return await set_time(update, context)
            elif state == SET_LIMIT:
                from src.event.create.set_limit import set_limit
                return await set_limit(update, context)

        return None
    except Exception as e:
        logger.error(f"Ошибка перенаправления: {e}")
        return None


# Добавляем этот обработчик в главный файл бота
def get_restore_handler():
    return MessageHandler(filters.TEXT & ~filters.COMMAND, restore_handler)