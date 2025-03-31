from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.handlers.conversation_handler_states import SET_DATE, SET_DESCRIPTION
from src.database.db_draft_operations import update_draft, get_draft
from src.logger.logger import logger

async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем наличие необходимых данных в context.user_data
    if "draft_id" not in context.user_data:
        await update.message.reply_text("⚠️ Ошибка сессии. Пожалуйста, начните создание мероприятия заново.")
        return ConversationHandler.END

    # Получаем текст описания
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text("Описание не может быть пустым. Пожалуйста, введите описание мероприятия.")
        return SET_DESCRIPTION

    try:
        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=context.user_data["draft_id"],
            status="AWAIT_DATE",
            description=description
        )

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем или редактируем сообщение
        if "bot_message_id" in context.user_data:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["bot_message_id"],
                    text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                    reply_markup=reply_markup,
                )
            except BadRequest:
                # Если не удалось редактировать, отправляем новое сообщение
                sent_message = await update.message.reply_text(
                    f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                    reply_markup=reply_markup,
                )
                context.user_data["bot_message_id"] = sent_message.message_id
        else:
            sent_message = await update.message.reply_text(
                f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=reply_markup,
            )
            context.user_data["bot_message_id"] = sent_message.message_id

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        return SET_DATE

    except Exception as e:
        logger.error(f"Ошибка при обновлении черновика: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при сохранении описания. Пожалуйста, попробуйте еще раз.")
        return ConversationHandler.END