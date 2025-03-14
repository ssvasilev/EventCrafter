from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CommandHandler,
)

from buttons.edit_event_button import edit_event_button
from database.db_operations import delete_event, get_event
import logging

from event.edit.date import save_date
from event.edit.description import save_description
from event.edit.limit import save_limit
from event.edit.time import save_time
from handlers.cancel_handler import cancel_input, cancel
from handlers.conversation_handler_states import EDIT_EVENT, EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT

logger = logging.getLogger(__name__)

# Обработка выбора параметра для редактирования
async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Определяем, какое действие выбрал пользователь
    data = query.data
    if data == "cancel_input":  # Если нажата кнопка "Отмена"
        await cancel_input(update, context)
        return ConversationHandler.END

    action, event_id = data.split("|")
    context.user_data["event_id"] = event_id

    # Получаем данные о мероприятии
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено.")
        return ConversationHandler.END

    """
    # Открепляем сообщение, если оно закреплено
    try:
        await context.bot.unpin_chat_message(
            chat_id=query.message.chat_id,
            message_id=event["message_id"]
        )
        logger.info(f"Сообщение {event['message_id']} откреплено.")
    except logging.error.BadRequest as e:
        logger.error(f"Ошибка при откреплении сообщения: {e}")
    except logging.error.Forbidden as e:
        logger.error(f"Бот не имеет прав на открепление сообщений: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при откреплении сообщения: {e}")
    """

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if action == "edit_description":
        await query.edit_message_text(
            "Введите новое описание мероприятия:",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_DESCRIPTION
    elif action == "edit_date":
        await query.edit_message_text(
            "Введите новую дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_DATE
    elif action == "edit_time":
        await query.edit_message_text(
            "Введите новое время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_TIME
    elif action == "edit_limit":
        await query.edit_message_text(
            "Введите новый лимит участников (0 - неограниченное):",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_LIMIT
    elif action == "delete":
        # Проверяем, является ли пользователь создателем
        if event["creator_id"] != query.from_user.id:
            await query.answer("Вы не можете удалить это мероприятие.")
            return

        # Получаем message_id мероприятия
        message_id = event.get("message_id")

        # Если message_id существует, пытаемся открепить сообщение
        if message_id:
            try:
                # Открепляем сообщение
                await context.bot.unpin_chat_message(
                    chat_id=query.message.chat_id,
                    message_id=message_id
                )
                logger.info(f"Сообщение мероприятия {event_id} откреплено.")
            except BadRequest as e:
                # Логируем ошибку, если открепление не удалось
                logger.error(f"Ошибка при откреплении сообщения: {e}")
                # Проверяем, связано ли это с отсутствием прав или с тем, что сообщение не закреплено
                if "not pinned" in str(e).lower():
                    logger.info(f"Сообщение {message_id} не было закреплено.")
                elif "not enough rights" in str(e).lower():
                    logger.error(f"Бот не имеет прав на открепление сообщений в этом чате.")
            except Exception as e:
                # Логируем любые другие ошибки
                logger.error(f"Неизвестная ошибка при откреплении сообщения: {e}")

        # Удаляем мероприятие из базы данных
        delete_event(db_path, event_id)
        logger.info(f"Мероприятие {event_id} удалено.")

        # Редактируем сообщение с подтверждением удаления
        await query.edit_message_text("Мероприятие удалено.")

        # Завершаем диалог
        return ConversationHandler.END




# ConversationHandler для редактирования мероприятия
conv_handler_edit_event = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_event_button, pattern="^edit\\|")],
    states={
        EDIT_EVENT: [
            CallbackQueryHandler(handle_edit_choice),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        EDIT_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_description),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        EDIT_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_date),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        EDIT_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_time),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        EDIT_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_limit),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
    },
    fallbacks=[CommandHandler("cancel_input", cancel_input)],
    per_message=False,
)