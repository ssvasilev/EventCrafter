from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from src.database.db_draft_operations import add_draft, get_active_draft
from src.handlers.conversation_handler_states import SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик упоминания бота. Запускает создание мероприятия или показывает меню.
    Автоматически восстанавливает незавершенное создание мероприятия для пользователя.
    """
    if not update.message or not update.message.entities:
        return ConversationHandler.END

    try:
        # Проверяем, что бот упомянут
        mention_text = None
        for entity in update.message.entities:
            if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
                mention_text = update.message.text[entity.offset + entity.length:].strip()
                break

        user_id = update.message.from_user.id
        chat_id = update.message.chat_id

        # Проверяем наличие активного черновика
        active_draft = get_active_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id
        )

        # Если есть активный черновик - восстанавливаем состояние
        if active_draft:
            return await restore_draft_state(update, context, active_draft)

        # Если после упоминания есть текст - начинаем создание мероприятия
        if mention_text:
            return await start_new_event(update, context, user_id, chat_id, mention_text)

        # Если просто упоминание - показываем меню
        return await show_main_menu(update, context)

    except Exception as e:
        logger.error(f"Ошибка в mention_handler: {e}")
        await update.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте снова.")
        return ConversationHandler.END

async def restore_draft_state(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Восстанавливает состояние создания мероприятия из черновика"""
    try:
        # Сохраняем данные черновика в context
        context.user_data.update({
            "draft_id": draft["id"],
            "restored": True  # Флаг восстановленного состояния
        })

        # Определяем текущий этап создания
        if draft["status"] == "AWAIT_DESCRIPTION":
            await update.message.reply_text(
                "Продолжаем создание мероприятия! Введите описание:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DESCRIPTION

        elif draft["status"] == "AWAIT_DATE":
            await update.message.reply_text(
                f"Продолжаем создание мероприятия!\n\n📢 {draft['description']}\n\nВведите дату в формате ДД.ММ.ГГГГ:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_DATE

        elif draft["status"] == "AWAIT_TIME":
            await update.message.reply_text(
                f"Продолжаем создание мероприятия!\n\n📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\nВведите время в формате ЧЧ:ММ:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_TIME

        elif draft["status"] == "AWAIT_LIMIT":
            await update.message.reply_text(
                f"Продолжаем создание мероприятия!\n\n📢 {draft['description']}\n\n📅 Дата: {draft['date']}\n\n🕒 Время: {draft['time']}\n\nВведите лимит участников (0 - без лимита):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ])
            )
            return SET_LIMIT

    except Exception as e:
        logger.error(f"Ошибка восстановления черновика: {e}")
        raise

async def start_new_event(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, description: str):
    """Начинает процесс создания нового мероприятия"""
    try:
        # Создаем новый черновик
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id,
            status="AWAIT_DATE",
            description=description
        )

        if not draft_id:
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Отправляем запрос даты
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        sent_message = await update.message.reply_text(
            f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Сохраняем данные в context
        context.user_data.update({
            "draft_id": draft_id,
            "bot_message_id": sent_message.message_id
        })

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return SET_DATE

    except Exception as e:
        logger.error(f"Ошибка при создании мероприятия: {e}")
        raise

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню при упоминании бота"""
    try:
        keyboard = [
            [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
            [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
        ]
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка показа меню: {e}")
        raise