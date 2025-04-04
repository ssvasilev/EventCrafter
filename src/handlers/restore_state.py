from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from src.database.db_draft_operations import get_active_draft
from src.handlers.conversation_handler_states import (
    SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT
)
from src.logger.logger import logger

async def restore_and_get_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Восстанавливает состояние и возвращает следующее ожидаемое действие"""
    try:
        # Проверяем, не восстановлено ли состояние уже
        if context.user_data.get('state_restored'):
            return None

        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

        draft = get_active_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id
        )

        if not draft:
            return None

        # Помечаем состояние как восстановленное
        context.user_data.update({
            'draft_id': draft['id'],
            'state_restored': True,
            'expecting_input': True  # Флаг ожидания ввода
        })

        # Определяем какое поле ожидается
        if draft['status'] == 'AWAIT_DESCRIPTION':
            await update.message.reply_text(
                "Восстановлено незавершенное создание мероприятия. Пожалуйста, введите описание:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DESCRIPTION

        elif draft['status'] == 'AWAIT_DATE':
            await update.message.reply_text(
                f"Восстановлено создание мероприятия:\n{draft['description']}\n\nВведите дату (ДД.ММ.ГГГГ)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DATE

        elif draft['status'] == 'AWAIT_TIME':
            await update.message.reply_text(
                f"Восстановлено создание мероприятия:\n{draft['description']}\n\nВведите время (ЧЧ:ММ)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DATE

        elif draft['status'] == 'AWAIT_LIMIT':
            await update.message.reply_text(
                f"Восстановлено создание мероприятия:\n{draft['description']}\n\nВведите количество участников (0 - без ограничений)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_LIMIT


    except Exception as e:
        logger.error(f"Ошибка восстановления состояния: {e}")
        return None