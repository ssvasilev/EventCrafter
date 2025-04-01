from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler

from config import DB_PATH, tz, DB_DRAFT_PATH
from src.buttons.my_events_button import my_events_button
from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.handlers.button_handlers import button_handler
from src.handlers.cancel_handler import cancel
from src.handlers.create_event_handler import conv_handler_create, cancel_handler
from src.handlers.mention_handler import conv_handler_create_mention, mention_handler
from src.handlers.start_handler import start
from src.handlers.version_handler import version
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

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(my_events_button, pattern="^my_events$"))

    # Обработчики создания мероприятий
    application.add_handler(conv_handler_create)
    application.add_handler(conv_handler_create_mention)
    application.add_handler(cancel_handler)

    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    application.run_polling()

if __name__ == "__main__":
    main()