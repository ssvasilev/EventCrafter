from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, CommandHandler

from src.event.create import set_date
from src.event.create.set_limit import set_limit
from src.event.create.set_time import set_time
from src.handlers.cancel_handler import cancel_input, cancel
from src.handlers.conversation_handler_states import SET_DATE, SET_TIME, SET_LIMIT
from src.database.db_draft_operations import add_draft

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return

    # Проверяем, упомянут ли бот
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            # Получаем текст сообщения после упоминания
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            if mention_text:
                # Если текст после упоминания не пустой, создаем черновик мероприятия
                creator_id = update.message.from_user.id
                chat_id = update.message.chat_id
                draft_id = add_draft(
                    db_path=context.bot_data["drafts_db_path"],
                    creator_id=creator_id,
                    chat_id=chat_id,
                    status="AWAIT_DATE",
                    description=mention_text
                )

                if not draft_id:
                    await update.message.reply_text("Ошибка при создании черновика мероприятия.")
                    return ConversationHandler.END

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

                # Сохраняем ID черновика в user_data
                context.user_data["draft_id"] = draft_id
                context.user_data["bot_message_id"] = sent_message.message_id

                # Удаляем сообщение пользователя
                await update.message.delete()

                # Переходим к состоянию SET_DATE
                return SET_DATE
            else:
                # Если текст после упоминания пустой, предлагаем создать мероприятие или показать свои мероприятия
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                    [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем сообщение с клавиатурой
                sent_message = await update.message.reply_text(
                    "Вы упомянули меня! Хотите создать мероприятие или узнать свои мероприятия? Нажмите кнопку ниже.",
                    reply_markup=reply_markup,
                )

                # Сохраняем ID сообщения бота
                context.user_data["bot_message_id"] = sent_message.message_id
                context.user_data["chat_id"] = update.message.chat_id

                # Завершаем диалог
                return ConversationHandler.END

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
    per_message=False,
)