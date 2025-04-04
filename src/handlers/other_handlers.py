from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import get_active_draft
from src.handlers.conversation_handler_states import (
    SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT
)
from src.logger.logger import logger

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Основной обработчик текстовых сообщений.
    Автоматически восстанавливает состояние создания мероприятия.
    """
    if not update.message:
        return None

    try:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

        # Проверяем наличие активного черновика
        active_draft = get_active_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id
        )

        # Если есть черновик - восстанавливаем состояние
        if active_draft:
            return await handle_existing_draft(update, context, active_draft)

        # Если черновика нет - пропускаем сообщение
        return None

    except Exception as e:
        logger.error(f"Ошибка в text_message_handler: {e}")
        return None

async def handle_existing_draft(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает сообщение при наличии активного черновика"""
    try:
        # Сохраняем данные черновика в context
        context.user_data.update({
            "draft_id": draft["id"],
            "restored": True,  # Флаг восстановленного состояния
            "auto_restored": True  # Флаг автоматического восстановления
        })

        # Определяем текущий этап и возвращаем соответствующее состояние
        if draft["status"] == "AWAIT_DESCRIPTION":
            await update.message.reply_text(
                "Обнаружено незавершенное создание мероприятия! Продолжаем...\n\nВведите описание:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DESCRIPTION

        elif draft["status"] == "AWAIT_DATE":
            await update.message.reply_text(
                f"Обнаружено незавершенное создание мероприятия! Продолжаем...\n\n📢 {draft['description']}\n\nВведите дату в формате ДД.ММ.ГГГГ:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DATE

        elif draft["status"] == "AWAIT_TIME":
            await update.message.reply_text(
                f"Обнаружено незавершенное создание мероприятия! Продолжаем...\n\n📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\nВведите время в формате ЧЧ:ММ:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_TIME

        elif draft["status"] == "AWAIT_LIMIT":
            await update.message.reply_text(
                f"Обнаружено незавершенное создание мероприятия! Продолжаем...\n\n📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {draft['time']}\n\nВведите лимит участников (0 - без лимита):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_LIMIT

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")
        await update.message.reply_text("Произошла ошибка при восстановлении мероприятия.")
        return None

def setup_other_handlers(application):
    """Регистрирует дополнительные обработчики"""
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Entity("mention"),
        text_message_handler
    ), group=1)