from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_user_state, get_draft, clear_user_state
from src.handlers.conversation_handler_states import *
from src.logger.logger import logger


async def restore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Пропускаем команды и не текстовые сообщения
        if not update.message or not update.message.text or update.message.text.startswith('/'):
            return None

        user_id = update.message.from_user.id
        db_path = context.bot_data["drafts_db_path"]

        # Получаем состояние пользователя
        user_state = get_user_state(db_path, user_id)
        if not user_state:
            return None

        # Получаем черновик
        draft = get_draft(db_path, user_state["draft_id"])
        if not draft:
            clear_user_state(db_path, user_id)
            return None

        draft = dict(draft) if hasattr(draft, 'keys') else draft

        # Восстанавливаем контекст
        context.user_data.update({
            "draft_id": draft["id"],
            "description": draft.get("description"),
            "date": draft.get("date"),
            "time": draft.get("time")
        })

        # Создаем новое сообщение вместо редактирования старого
        try:
            message = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=get_restored_message_text(draft, user_state["state"]),
                reply_markup=get_restored_reply_markup()
            )
            context.user_data["bot_message_id"] = message.message_id
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return None

        # Перенаправляем в нужный обработчик
        handler = user_state["handler"]
        state = user_state["state"]

        if handler == "create_event_handler":
            if state == SET_DESCRIPTION:
                from src.event.create.set_description import set_description
                return await set_description(update, context)
            # ... другие состояния

        elif handler == "mention_handler":
            if state == SET_DATE:
                from src.event.create.set_date import set_date
                return await set_date(update, context)
            # ... другие состояния

        return None

    except Exception as e:
        logger.error(f"Ошибка восстановления: {e}")
        clear_user_state(db_path, user_id)
        return None


def get_restored_message_text(draft, state):
    """Формирует текст сообщения в зависимости от состояния"""
    if state == SET_DESCRIPTION:
        return "Восстановлена сессия создания мероприятия\n\nВведите описание:"
    elif state == SET_DATE:
        return f"📢 {draft['description']}\n\nВведите дату в формате ДД.ММ.ГГГГ:"
    elif state == SET_TIME:
        return f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\nВведите время:"
    elif state == SET_LIMIT:
        return f"📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {draft['time']}\n\nВведите лимит участников:"
    return "Восстановлена сессия создания мероприятия"


def get_restored_reply_markup():
    """Возвращает клавиатуру для восстановленного сообщения"""
    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
    return InlineKeyboardMarkup(keyboard)


# Добавляем этот обработчик в главный файл бота
def get_restore_handler():
    return MessageHandler(filters.TEXT & ~filters.COMMAND, restore_handler)