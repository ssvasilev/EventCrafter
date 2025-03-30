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
        return

    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем, есть ли активный черновик у пользователя
    if "active_drafts" in context.bot_data and str(user_id) in context.bot_data["active_drafts"]:
        active_draft = context.bot_data["active_drafts"][str(user_id)]
        context.user_data.update({
            "draft_id": active_draft["draft_id"],
            "bot_message_id": active_draft["bot_message_id"],
            "current_state": active_draft["current_state"]
        })
        return active_draft["current_state"]

    # Проверяем, упомянут ли бот
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            # Получаем текст сообщения после упоминания
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            if mention_text:
                try:
                    # Создаем новый черновик
                    draft_id = add_draft(
                        db_path=context.bot_data["drafts_db_path"],
                        creator_id=user_id,
                        chat_id=chat_id,
                        status="AWAIT_DATE",
                        description=mention_text,
                        current_state="SET_DATE"
                    )

                    if not draft_id:
                        await update.message.reply_text("Ошибка при создании черновика мероприятия.")
                        return ConversationHandler.END

                    # Создаем клавиатуру с кнопкой "Отмена"
                    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # Отправляем сообщение с запросом даты
                    sent_message = await update.message.reply_text(
                        f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                        reply_markup=reply_markup,
                    )

                    # Сохраняем данные в контексты
                    context.user_data.update({
                        "draft_id": draft_id,
                        "bot_message_id": sent_message.message_id,
                        "description": mention_text,
                        "current_state": "SET_DATE"
                    })

                    if "active_drafts" not in context.bot_data:
                        context.bot_data["active_drafts"] = {}
                    context.bot_data["active_drafts"][str(user_id)] = {
                        "draft_id": draft_id,
                        "bot_message_id": sent_message.message_id,
                        "current_state": "SET_DATE",
                        "chat_id": chat_id,
                        "creator_id": user_id
                    }

                    # Обновляем черновик в базе
                    update_draft(
                        db_path=context.bot_data["drafts_db_path"],
                        draft_id=draft_id,
                        bot_message_id=sent_message.message_id,
                        current_state="SET_DATE"
                    )

                    # Пытаемся удалить сообщение пользователя
                    try:
                        await update.message.delete()
                    except BadRequest as e:
                        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")
                        # Просто продолжаем работу, не пытаемся редактировать сообщение пользователя

                    return SET_DATE

                except Exception as e:
                    logger.error(f"Ошибка при обработке упоминания: {e}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Произошла ошибка при создании мероприятия. Пожалуйста, попробуйте снова."
                    )
                    return ConversationHandler.END

            else:
                # Если текст после упоминания пустой
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

                    # Пытаемся удалить оригинальное сообщение (не критично)
                    try:
                        await update.message.delete()
                    except BadRequest as e:
                        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке пустого упоминания: {e}")

                return ConversationHandler.END

# ConversationHandler для создания мероприятия по упоминанию
conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],
    states={
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