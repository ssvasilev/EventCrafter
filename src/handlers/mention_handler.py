from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from telegram.error import BadRequest
import logging

from src.event.create.set_date import set_date
from src.event.create.set_description import set_description
from src.event.create.set_limit import set_limit
from src.event.create.set_time import set_time
from src.handlers.cancel_handler import cancel, cancel_input
from src.handlers.conversation_handler_states import SET_DATE, SET_TIME, SET_LIMIT, SET_DESCRIPTION
from src.database.db_draft_operations import add_draft, update_draft
from src.logger.logger import logger


async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return ConversationHandler.END

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            if not mention_text:
                # Показываем меню для пустого упоминания
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                    [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
                ]
                await update.message.reply_text(
                    "Выберите действие:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return ConversationHandler.END

            # Для упоминания с текстом - создаем черновик
            draft_id = add_draft(
                db_path=context.bot_data["drafts_db_path"],
                creator_id=user_id,
                chat_id=chat_id,
                status="AWAIT_DATE",
                description=mention_text,
                current_state="SET_DATE"
            )

            context.user_data.update({
                "draft_id": draft_id,
                "current_state": "SET_DATE"
            })

            keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            message = await update.message.reply_text(
                f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=reply_markup
            )

            context.user_data["bot_message_id"] = message.message_id

            try:
                await update.message.delete()
            except BadRequest as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

            return SET_DATE

    return ConversationHandler.END


async def handle_empty_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
        [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        sent_message = await update.message.reply_text(
            "Вы упомянули меня! Что вы хотите сделать?",
            reply_markup=reply_markup,
        )
        context.user_data["bot_message_id"] = sent_message.message_id
        await update.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при обработке пустого упоминания: {e}")

    return ConversationHandler.END


async def create_new_event_from_mention(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    try:
        # Создаем черновик
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=update.message.from_user.id,
            chat_id=update.message.chat_id,
            status="AWAIT_DATE",
            description=text,
            current_state="SET_DATE"
        )

        # Отправляем сообщение с запросом даты
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        sent_message = await update.message.reply_text(
            f"📢 {text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,
        )

        # Сохраняем контекст
        context.user_data.update({
            "draft_id": draft_id,
            "bot_message_id": sent_message.message_id,
            "current_state": "SET_DATE"
        })

        await update.message.delete()
        return SET_DATE  # Передаем управление основному ConversationHandler

    except Exception as e:
        logger.error(f"Ошибка создания мероприятия: {e}")
        await update.message.reply_text("⚠️ Ошибка при создании мероприятия")
        return ConversationHandler.END

conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],
    states={
        SET_DESCRIPTION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_description),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        SET_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        SET_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_time),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        SET_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
)

mention_only_handler = MessageHandler(
    filters.Entity("mention") & filters.TEXT,
    mention_handler
)