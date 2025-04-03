from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters
from src.database.db_draft_operations import add_draft
from src.database.session_manager import SessionManager
from src.logger.logger import logger

async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик упоминаний бота с интеграцией системы сессий"""
    if not update.message or not update.message.entities:
        return

    # Проверяем активную сессию
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    session_manager = SessionManager(context.bot_data["sessions_db_path"])

    if session_manager.get_active_session(user_id, chat_id):
        logger.debug(f"Active session exists for user {user_id} in chat {chat_id}")
        return

    # Проверяем упоминание бота
    bot_username = context.bot.username.lower()
    mention_text = ""

    for entity in update.message.entities:
        if entity.type == MessageEntity.MENTION:
            mentioned_text = update.message.text[entity.offset:entity.offset+entity.length].lower()
            if mentioned_text == f"@{bot_username}":
                mention_text = update.message.text[entity.offset+entity.length:].strip()
                break

    try:
        if mention_text:  # Создание нового мероприятия
            draft_id = add_draft(
                db_path=context.bot_data["drafts_db_path"],
                creator_id=user_id,
                chat_id=chat_id,
                status="AWAIT_DATE",
                description=mention_text
            )

            # Создаем новую сессию
            session_manager.create_session(user_id, chat_id, draft_id)

            # Отправляем форму создания
            await update.message.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Отмена", callback_data=f"cancel|{draft_id}")]
                ])
            )
        else:  # Показ меню
            await show_main_menu(update, context)

    except Exception as e:
        logger.error(f"Mention handler error: {str(e)}")
        try:
            await update.message.reply_text("⚠️ Произошла ошибка при обработке запроса")
        except:
            pass

async def show_main_menu(update, context):
    """Отображение главного меню"""
    keyboard = [
        [InlineKeyboardButton("Создать мероприятие", callback_data="menu_create_event")],
        [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")]
    ]

    try:
        await update.message.delete()
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="Выберите действие:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Menu error: {str(e)}")

def register_mention_handler(application):
    """Регистрация обработчика упоминаний"""
    mention_filter = filters.Entity(MessageEntity.MENTION) & ~filters.COMMAND
    application.add_handler(MessageHandler(mention_filter, mention_handler), group=1)