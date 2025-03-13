from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    JobQueue,
)

from buttons.create_event_button import create_event_button
from event.create.set_date import set_date
from event.create.set_description import set_description
from event.create.set_limit import set_limit
from event.create.set_time import set_time
from handlers.cancel_handler import cancel_input, cancel
from handlers.conversation_handler_states import SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT

# ConversationHandler для создания мероприятия
conv_handler_create = ConversationHandler(
    entry_points=[CallbackQueryHandler(create_event_button, pattern="^create_event$")],  # Кнопка "Создать
    # мероприятие"
    states={
        SET_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_description),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
        ],
        SET_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
        ],
        SET_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_time),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
        ],
        SET_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=True,
)

