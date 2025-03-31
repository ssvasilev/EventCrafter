from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, \
    CommandHandler
from src.database.db_draft_operations import add_draft, get_user_draft, delete_draft
from src.event.create.set_date import set_date
from src.event.create.set_description import set_description
from src.event.create.set_limit import set_limit
from src.event.create.set_time import set_time
from src.handlers.cancel_handler import cancel_input, cancel
from src.handlers.conversation_handler_states import SET_DATE, SET_TIME, SET_DESCRIPTION, SET_LIMIT
from src.logger.logger import logger


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Очищаем предыдущее состояние
        if context.user_data:
            context.user_data.clear()

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        # Удаляем старые черновики пользователя
        if old_draft := get_user_draft(context.bot_data["drafts_db_path"], user_id):
            delete_draft(context.bot_data["drafts_db_path"], old_draft["id"])

        # Получаем текст после упоминания
        mention_text = update.message.text.split('@' + context.bot.username)[1].strip()

        if not mention_text:
            # Если текст пустой - показываем меню
            keyboard = [
                [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
            ]
            await update.message.reply_text(
                "Выберите действие:",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        # Создаем новый черновик
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id,
            status="AWAIT_DATE",
            description=mention_text
        )

        context.user_data.update({
            "draft_id": draft_id,
            "description": mention_text,
            "chat_id": chat_id,
            "from_mention": True  # Флаг, что создание начато через упоминание
        })

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        sent_message = await update.message.reply_text(
            f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["bot_message_id"] = sent_message.message_id

        try:
            await update.message.delete()
        except:
            pass

        return SET_DATE

    except Exception as e:
        logger.error(f"Error in mention handler: {e}")
        await update.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return ConversationHandler.END


# Отдельный обработчик для кнопки отмены
async def cancel_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if "draft_id" in context.user_data:
        delete_draft(context.bot_data["drafts_db_path"], context.user_data["draft_id"])

    context.user_data.clear()
    await query.edit_message_text("❌ Создание мероприятия отменено.")
    return ConversationHandler.END


conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, handle_mention)],
    states={
        SET_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_description),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$")
        ],
        SET_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$")
        ],
        SET_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_time),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$")
        ],
        SET_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$")
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel_input, pattern="^cancel_input$")
    ],
    per_message=False,
    name="mention_conversation"
)