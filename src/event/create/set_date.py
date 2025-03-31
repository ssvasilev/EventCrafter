from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.handlers.conversation_handler_states import SET_TIME, SET_DATE
from src.database.db_draft_operations import update_draft, get_draft
from src.logger.logger import logger

async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем наличие необходимых данных в context.user_data
    if "draft_id" not in context.user_data or "description" not in context.user_data:
        logger.error("Missing required data in user_data")
        await update.message.reply_text("⚠️ Сессия создания утеряна. Пожалуйста, начните заново.")
        return ConversationHandler.END

    date_text = update.message.text.strip()
    try:
        # Валидация формата даты
        datetime.strptime(date_text, "%d.%m.%Y").date()

        # Обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=context.user_data["draft_id"],
            status="AWAIT_TIME",
            date=date_text
        )

        # Получаем обновленные данные черновика
        draft = get_draft(context.bot_data["drafts_db_path"], context.user_data["draft_id"])
        if not draft:
            logger.error(f"Draft {context.user_data['draft_id']} not found")
            await update.message.reply_text("⚠️ Ошибка: черновик не найден")
            return ConversationHandler.END

        # Подготавливаем клавиатуру
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Формируем текст сообщения
        message_text = f"📢 {draft['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ"

        # Обработка двух сценариев:
        # 1. После перезагрузки (нет bot_message_id)
        # 2. Обычный сценарий (есть bot_message_id)
        if "bot_message_id" not in context.user_data:
            # Сценарий после перезагрузки - отправляем новое сообщение
            sent_message = await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup
            )
            context.user_data["bot_message_id"] = sent_message.message_id
        else:
            # Обычный сценарий - редактируем существующее сообщение
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["bot_message_id"],
                    text=message_text,
                    reply_markup=reply_markup
                )
            except BadRequest as e:
                logger.warning(f"Failed to edit message: {e}")
                # Если не удалось редактировать, отправляем новое сообщение
                sent_message = await update.message.reply_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
                context.user_data["bot_message_id"] = sent_message.message_id

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Failed to delete user message: {e}")

        return SET_TIME

    except ValueError:
        # Обработка неверного формата даты
        error_message = "Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ (например, 31.12.2025):"

        # Пытаемся отредактировать предыдущее сообщение бота
        if "bot_message_id" in context.user_data:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=context.user_data["bot_message_id"],
                    text=error_message,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
                )
            except BadRequest as e:
                logger.warning(f"Failed to edit error message: {e}")
                # Если не удалось редактировать, отправляем новое сообщение
                sent_message = await update.message.reply_text(
                    text=error_message,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
                )
                context.user_data["bot_message_id"] = sent_message.message_id
        else:
            # Если нет сообщения для редактирования, отправляем новое
            sent_message = await update.message.reply_text(
                text=error_message,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
            )
            context.user_data["bot_message_id"] = sent_message.message_id

        # Пытаемся удалить сообщение пользователя с неверной датой
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Failed to delete invalid date message: {e}")

        return SET_DATE

    except Exception as e:
        # Обработка всех остальных ошибок
        logger.error(f"Unexpected error in set_date: {e}")
        try:
            await update.message.reply_text("⚠️ Произошла непредвиденная ошибка. Пожалуйста, начните создание мероприятия заново.")
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

        # Полная очистка состояния при критической ошибке
        context.user_data.clear()
        return ConversationHandler.END