
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

from event.create.set_date import set_date
from event.create.set_limit import set_limit
from event.create.set_time import set_time
from handlers.cancel_handler import cancel_input, cancel
from handlers.conversation_handler_states import SET_DATE, SET_LIMIT, SET_TIME


# Обработка упоминания бота
async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return

    # Проверяем, упомянут ли бот
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[
                                        entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            # Получаем текст сообщения после упоминания
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            # Если текст после упоминания не пустой, сохраняем его как описание
            if mention_text:
                context.user_data["description"] = mention_text

                # Создаем клавиатуру с кнопкой "Отмена"
                keyboard = [
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем сообщение с запросом даты
                sent_message = await update.message.reply_text(
                    f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                    reply_markup=reply_markup,
                )

                # Сохраняем ID сообщения бота и chat_id
                context.user_data["bot_message_id"] = sent_message.message_id
                context.user_data["chat_id"] = update.message.chat_id

                # Удаляем сообщение пользователя
                await update.message.delete()

                # Переходим к состоянию SET_DATE
                return SET_DATE
            else:
                # Если текст после упоминания пустой, предлагаем создать мероприятие
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                    [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем сообщение с клавиатурой
                sent_message = await update.message.reply_text(
                    "Вы упомянули меня! Хотите создать мероприятие? Нажмите кнопку ниже.",
                    reply_markup=reply_markup,
                )

                # Сохраняем ID сообщения бота
                context.user_data["bot_message_id"] = sent_message.message_id
                context.user_data["chat_id"] = update.message.chat_id


# ConversationHandler для создания мероприятия по упоминанию
conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],  # Упоминание бота
    states={
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