from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from telegram.error import BadRequest
import logging

from src.event.create.set_date import set_date
from src.event.create.set_limit import set_limit
from src.event.create.set_time import set_time
from src.handlers.cancel_handler import cancel, cancel_input
from src.handlers.conversation_handler_states import SET_DATE, SET_TIME, SET_LIMIT
from src.database.db_draft_operations import add_draft, update_draft
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return ConversationHandler.END  # Явное завершение

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем активные черновики (только для текстовых упоминаний)
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            if mention_text:
                # Устанавливаем описание и переходим к SET_DATE
                context.user_data['description'] = mention_text
                return SET_DATE

            # Если есть активный черновик - перенаправляем в основной обработчик
            if "active_drafts" in context.bot_data and str(user_id) in context.bot_data["active_drafts"]:
                await update.message.reply_text(
                    "⚠️ У вас уже есть активное создание мероприятия. "
                    "Завершите его или отмените командой /cancel"
                )
                return ConversationHandler.END

            # Создание нового мероприятия
            return await create_new_event_from_mention(update, context, mention_text)

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

# ConversationHandler для упоминаний
conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],
    states={
        # Оставляем пустым, так как вся логика перенаправления уже в mention_handler
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel_input, pattern="^cancel_input$")
    ],
    per_message=False,
)