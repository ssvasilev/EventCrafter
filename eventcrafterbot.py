import pytz
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from config import DB_PATH, tz
from database.init_database import init_db
from handlers.create_event_handler import conv_handler_create
from handlers.mention_handler import conv_handler_create_mention
from handlers.start_handler import start
from handlers.edit_event_handlers import conv_handler_edit_event, logger
from handlers.button_handlers import button_handler

from jobs.notification_jobs import restore_scheduled_jobs
import os
from dotenv import load_dotenv
import locale

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')  # Для Linux

# Загружаем переменные окружения
load_dotenv("data/.env")
BOT_TOKEN = os.getenv('BOT_TOKEN')



# Проверяем, что токен загружен
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле.")


# Инициализация базы данных
init_db(DB_PATH)

def main():
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()

    # Сохраняем путь к базе данных в context.bot_data
    application.bot_data["db_path"] = DB_PATH

    # Сохраняем часовой пояс в context.bot_data
    application.bot_data["tz"] = tz

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))

    # ConversationHandler для создания мероприятия
    application.add_handler(conv_handler_create)
    application.add_handler(conv_handler_create_mention)

    # ConversationHandler для редактирования мероприятия
    application.add_handler(conv_handler_edit_event)

    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    # Восстанавливаем запланированные задачи
    application.run_polling()

if __name__ == "__main__":
    main()