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

    # Проверяем упоминание бота
    bot_username = context.bot.username.lower()
    mention_text = ""

    for entity in update.message.entities:
        if entity.type == MessageEntity.MENTION:
            mentioned_text = update.message.text[entity.offset:entity.offset + entity.length].lower()
            if mentioned_text == f"@{bot_username}":
                # Получаем текст после упоминания
                mention_text = update.message.text[entity.offset + entity.length:].strip()
                break

    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем активный черновик
    draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)
    if draft:
        logger.debug(f"У пользователя {creator_id} уже есть активный черновик")
        return

    if not mention_text:
        # Если просто упоминание без текста - отправляем меню
        keyboard = [
            [InlineKeyboardButton("📅 Создать мероприятие", callback_data="menu_create_event")],
            [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")],
            [InlineKeyboardButton("📁 Мои шаблоны", callback_data="menu_my_templates")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            # Отправляем новое сообщение с меню
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text="Главное меню:",
                reply_markup=reply_markup
            )

            # Пытаемся удалить сообщение с упоминанием
            try:
                await update.message.delete()
            except BadRequest as e:
                logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

            return
        except Exception as e:
            logger.error(f"Ошибка при обработке упоминания: {e}")
            return

    # Создаем черновик
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

    # Отправляем первое сообщение формы
    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Отправляем новое сообщение с формой
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup
        )

        # Сохраняем ID этого сообщения в черновике
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            bot_message_id=sent_message.message_id
        )

        # Пытаемся удалить сообщение с упоминанием, но не критично если не получится
        try:
            await update.message.delete()
        except Exception as e:
            logger.info(f"Не удалось удалить сообщение с упоминанием: {e}")

    except Exception as e:
        logger.error(f"Ошибка при обработке упоминания: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса.")

def register_mention_handler(application):
    mention_filter = filters.Entity(MessageEntity.MENTION) & ~filters.COMMAND
    application.add_handler(MessageHandler(mention_filter, mention_handler), group=1)