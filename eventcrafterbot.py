from telegram.ext import Application, CommandHandler
from config import DB_PATH, tz, DB_DRAFT_PATH
from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.handlers.draft_handlers import register_draft_handlers
from src.handlers.start_handler import start
from src.handlers.version_handler import version
from src.handlers.mention_handler import register_mention_handler
from src.handlers.menu_button_handlers import  register_menu_button_handler
from src.handlers.button_handlers import  register_button_handler
from src.handlers.create_event_handler import register_create_handlers
from src.jobs.notification_jobs import restore_scheduled_jobs
import os
from dotenv import load_dotenv
import locale

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
load_dotenv("data/.env")
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Проверяем, что токен загружен
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле.")

def main():
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

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))

    # Регистрируем обработчики
    register_draft_handlers(application)
    register_mention_handler(application)
    register_create_handlers(application)
    register_menu_button_handler(application)
    register_button_handler(application)

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    application.run_polling()

if __name__ == "__main__":
    main()