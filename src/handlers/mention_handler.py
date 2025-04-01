from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft
from src.handlers.draft_handlers import handle_draft_message
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Логируем входящее сообщение для отладки
    logger.debug(f"Получено сообщение: {update.message.text}")

    if not update.message or not update.message.entities:
        return

    # Проверяем, упомянут ли бот
    bot_username = context.bot.username.lower()
    mention_text = ""

    for entity in update.message.entities:
        if entity.type == MessageEntity.MENTION:
            mentioned_text = update.message.text[entity.offset:entity.offset + entity.length].lower()
            if mentioned_text == f"@{bot_username}":
                # Получаем текст после упоминания
                mention_text = update.message.text[entity.offset + entity.length:].strip()
                break

    if not mention_text:
        # Если текст после упоминания пустой, показываем меню
        keyboard = [
            [InlineKeyboardButton("Создать мероприятие", callback_data="menu_create_event")],
            [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_text(
                "Вы упомянули меня! Что вы хотите сделать?",
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            logger.error(f"Ошибка при обработке пустого упоминания: {e}")
            return

    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем, есть ли уже активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)

    if draft:
        logger.debug(f"У пользователя {creator_id} уже есть активный черновик")
        return

    # Создаем новый черновик с описанием
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

    try:
        sent_message = await update.message.reply_text(
            f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,
        )

        # Обновляем черновик с ID сообщения бота
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            bot_message_id=sent_message.message_id
        )

        # Пытаемся удалить сообщение пользователя (если есть права)
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except Exception as e:
        logger.error(f"Ошибка при обработке упоминания: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса.")

def register_mention_handler(application):
    mention_filter = filters.Entity(MessageEntity.MENTION) & ~filters.COMMAND
    application.add_handler(MessageHandler(mention_filter, mention_handler), group=1)