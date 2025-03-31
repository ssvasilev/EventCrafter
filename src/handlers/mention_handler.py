from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.error import BadRequest

from src.event.create.set_date import set_date
from src.handlers.cancel_handler import cancel_input
from src.handlers.conversation_handler_states import SET_DESCRIPTION, SET_DATE
from src.database.db_draft_operations import add_draft, get_user_draft, delete_draft
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем предыдущие данные
    context.user_data.clear()

    if not update.message or not update.message.entities:
        return ConversationHandler.END

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем и удаляем старые черновики
    active_draft = get_user_draft(context.bot_data["drafts_db_path"], user_id)
    if active_draft:
        try:
            delete_draft(context.bot_data["drafts_db_path"], active_draft["id"])
        except Exception as e:
            logger.error(f"Error deleting old draft: {e}")

    # Получаем текст после упоминания
    mention_text = None
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            mention_text = update.message.text[entity.offset + entity.length:].strip()
            break

    try:
        if mention_text:
            # Создаем новый черновик
            draft_id = add_draft(
                db_path=context.bot_data["drafts_db_path"],
                creator_id=user_id,
                chat_id=chat_id,
                status="AWAIT_DATE",
                description=mention_text
            )

            if not draft_id:
                await update.message.reply_text("Ошибка при создании мероприятия.")
                return ConversationHandler.END

            context.user_data.update({
                "draft_id": draft_id,
                "description": mention_text,
                "chat_id": chat_id
            })

            # Отправляем запрос даты
            keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
            sent_message = await update.message.reply_text(
                f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=InlineKeyboardMarkup(keyboard))

            context.user_data["bot_message_id"] = sent_message.message_id

            try:
                await update.message.delete()
            except BadRequest:
                pass

            return SET_DATE
        else:
            keyboard = [
                [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
            ]
            sent_message = await update.message.reply_text(
                "Вы упомянули меня! Что вы хотите сделать?",
                reply_markup=InlineKeyboardMarkup(keyboard))

            context.user_data["bot_message_id"] = sent_message.message_id

            try:
                await update.message.delete()
            except BadRequest:
                pass

            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in mention handler: {e}")
        await update.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return ConversationHandler.END

# ConversationHandler для создания мероприятия по упоминанию
conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],
    states={
        SET_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        # Другие состояния добавляются из других модулей
    },
    fallbacks=[CallbackQueryHandler(cancel_input, pattern="^cancel_input$")],
    per_message=False,
)