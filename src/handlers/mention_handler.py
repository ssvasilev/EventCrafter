from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft
from src.handlers.draft_handlers import handle_draft_message
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return

    # Проверяем, упомянут ли бот
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            # Получаем текст сообщения после упоминания
            mention_text = update.message.text[entity.offset + entity.length:].strip()
            creator_id = update.message.from_user.id
            chat_id = update.message.chat_id

            # Проверяем, есть ли уже активный черновик
            draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)

            if draft:
                return await handle_draft_message(update, context, draft)

            if mention_text:
                # Создаем черновик с описанием
                draft_id = add_draft(
                    db_path=context.bot_data["drafts_db_path"],
                    creator_id=creator_id,
                    chat_id=chat_id,
                    status="AWAIT_DATE",
                    description=mention_text
                )

                if not draft_id:
                    await update.message.reply_text("Ошибка при создании черновика мероприятия.")
                    return

                # Отправляем сообщение с запросом даты
                keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                sent_message = await update.message.reply_text(
                    f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                    reply_markup=reply_markup,
                )

                # Сохраняем ID сообщения бота в черновик
                update_draft(
                    db_path=context.bot_data["drafts_db_path"],
                    draft_id=draft_id,
                    bot_message_id=sent_message.message_id
                )

                # Пытаемся удалить сообщение пользователя
                try:
                    await update.message.delete()
                except BadRequest as e:
                    logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

            else:
                # Если упоминание без текста - показываем меню
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                    [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                try:
                    await update.message.reply_text(
                        "Вы упомянули меня! Что вы хотите сделать?",
                        reply_markup=reply_markup,
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обработке пустого упоминания: {e}")

# ConversationHandler для упоминаний
conv_handler_create_mention = MessageHandler(
    filters.Entity("mention") & filters.TEXT,
    mention_handler
)