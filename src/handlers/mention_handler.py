from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft
from src.handlers.draft_handlers import handle_draft_message
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    creator_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Проверяем существующий черновик
    existing_draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)
    if existing_draft:
        logger.debug(f"Уже есть активный черновик: {existing_draft['id']}")
        return

    if not mention_text:
        # Показываем меню, если нет текста после упоминания
        keyboard = [
            [InlineKeyboardButton("✏️ Создать мероприятие", callback_data="menu_create_event")],
            [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")]
        ]
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Создаем черновик
    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=creator_id,
        chat_id=chat_id,
        status="AWAIT_DATE",  # Сразу переходим к дате
        description=mention_text[:200]  # Обрезаем слишком длинные описания
    )

    if not draft_id:
        await update.message.reply_text("⚠️ Ошибка при создании мероприятия")
        return

    # Отправляем запрос даты
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_draft|{draft_id}")]]
    try:
        sent_message = await update.message.reply_text(
             f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup(keyboard)
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
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка при создании мероприятия: {e}")
        await update.message.reply_text("⚠️ Ошибка при обработке запроса")

def register_mention_handler(application):
    mention_filter = filters.Entity(MessageEntity.MENTION) & ~filters.COMMAND
    application.add_handler(MessageHandler(mention_filter, mention_handler), group=1)