import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, TypeHandler
from config import DB_PATH, tz, DB_DRAFT_PATH
from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.handlers.cancel_handler import register_cancel_handlers
from src.handlers.draft_handlers import register_draft_handlers

from src.handlers.message_handler import register_message_handlers
from src.handlers.start_handler import start
from src.handlers.template_handlers import save_user_middleware
from src.handlers.version_handler import version
from src.handlers.mention_handler import register_mention_handler
from src.buttons.menu_button_handlers import  register_menu_button_handler
from src.buttons.button_handlers import  register_button_handler
from src.buttons.create_event_button import register_create_handlers
from src.jobs.notification_jobs import restore_scheduled_jobs
import os
from dotenv import load_dotenv
import locale

from src.utils.pin_message import pin_message_safe

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
load_dotenv("data/.env")
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Проверяем, что токен загружен
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле.")

def main():
    # Добавьте в начало main()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()

    # Инициализация баз данных
    init_db(DB_PATH)
    init_drafts_db(DB_DRAFT_PATH)

    # Сохраняем данные в context.bot_data
    application.bot_data.update({
        "db_path": DB_PATH,
        "drafts_db_path": DB_DRAFT_PATH,
        "tz": tz
    })

    async def test_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("Тестовое сообщение для закрепления")
        success = await pin_message_safe(context, update.effective_chat.id, msg.message_id)
        await msg.reply_text(f"Результат закрепления: {success}")

    # Регистрируем обработчики
    register_message_handlers(application)
    register_draft_handlers(application)
    register_mention_handler(application)
    register_create_handlers(application)
    register_menu_button_handler(application)  # Обрабатывает menu_* и cancel_*
    register_button_handler(application)  # Обрабатывает join|*, leave|*, edit|*
    application.add_handler(TypeHandler(Update, save_user_middleware), group=-1)

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))
    application.add_handler(CommandHandler("test_pin", test_pin))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    #Обработчики отмены
    register_cancel_handlers(application)

    application.run_polling()

if __name__ == "__main__":
    main()