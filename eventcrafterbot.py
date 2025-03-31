from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import DB_PATH, tz, DB_DRAFT_PATH
from src.buttons.my_events_button import my_events_button
from src.database.db_draft_operations import get_all_active_drafts
from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.handlers.button_handlers import button_handler
from src.handlers.continue_handler import continue_creation
from src.handlers.create_event_handler import conv_handler_create
from src.handlers.edit_event_handlers import conv_handler_edit_event
from src.handlers.mention_handler import conv_handler_create_mention
from src.handlers.start_handler import start
from src.handlers.version_handler import version

from src.jobs.notification_jobs import restore_scheduled_jobs
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

# Инициализация основной базы данных
init_db(DB_PATH)

# Инициализация базы данных черновиков
init_drafts_db(DB_DRAFT_PATH)

def main():
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()

    # Сохраняем пути к базам данных и часовой пояс в bot_data
    application.bot_data.update({
        "db_path": DB_PATH,
        "drafts_db_path": DB_DRAFT_PATH,
        "tz": tz
    })

    # Загружаем активные черновики при старте
    active_drafts = get_all_active_drafts(DB_DRAFT_PATH)
    application.bot_data["active_drafts"] = {draft["creator_id"]: draft for draft in active_drafts}

    # Создаем обработчик продолжения
    continue_handler = MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Entity("mention"),
        continue_creation
    )

    # Добавляем обработчики в правильном порядке:
    # 1. Сначала обработчик продолжения
    application.add_handler(continue_handler)

    # 2. Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))

    # 3. Обработчик кнопки "Мои мероприятия"
    application.add_handler(CallbackQueryHandler(my_events_button, pattern="^my_events$"))

    # 4. ConversationHandler для создания мероприятия
    application.add_handler(conv_handler_create)
    application.add_handler(conv_handler_create_mention)

    # 5. ConversationHandler для редактирования мероприятия
    application.add_handler(conv_handler_edit_event)

    # 6. Общий обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()