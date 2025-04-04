from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.database.db_draft_operations import add_draft
from src.handlers.conversation_handler_states import SET_DESCRIPTION, SET_DATE
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик упоминания бота (@botname).
    Запускает процесс создания мероприятия или показывает меню.
    """
    if not update.message or not update.message.entities:
        return ConversationHandler.END

    try:
        # Проверяем, что бот действительно упомянут
        mention_found = False
        for entity in update.message.entities:
            if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
                mention_found = True
                mention_text = update.message.text[entity.offset + entity.length:].strip()
                break

        if not mention_found:
            return ConversationHandler.END

        # Если после упоминания есть текст - начинаем создание мероприятия
        if mention_text:
            creator_id = update.message.from_user.id
            chat_id = update.message.chat_id

            # Создаем черновик мероприятия
            draft_id = add_draft(
                db_path=context.bot_data["drafts_db_path"],
                creator_id=creator_id,
                chat_id=chat_id,
                status="AWAIT_DATE",
                description=mention_text
            )

            if not draft_id:
                await update.message.reply_text("Ошибка при создании мероприятия.")
                return ConversationHandler.END

            # Отправляем сообщение с запросом даты
            keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
            sent_message = await update.message.reply_text(
                f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            # Сохраняем данные в context
            context.user_data.update({
                "draft_id": draft_id,
                "bot_message_id": sent_message.message_id,
                "description": mention_text
            })

            # Пытаемся удалить сообщение пользователя
            try:
                await update.message.delete()
            except BadRequest as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

            return SET_DATE

        # Если после упоминания нет текста - показываем меню
        else:
            keyboard = [
                [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            sent_message = await update.message.reply_text(
                "Выберите действие:",
                reply_markup=reply_markup
            )

            # Пытаемся удалить сообщение пользователя
            try:
                await update.message.delete()
            except BadRequest as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка в mention_handler: {e}")
        await update.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте снова.")
        return ConversationHandler.END