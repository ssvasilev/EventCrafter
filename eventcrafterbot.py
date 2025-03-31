from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
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
from src.handlers.cancel_handler import cancel_input  # Добавляем импорт обработчика отмены

from src.jobs.notification_jobs import restore_scheduled_jobs
import os
from dotenv import load_dotenv
import locale
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
    try:
        active_drafts = get_all_active_drafts(DB_DRAFT_PATH)
        application.bot_data["active_drafts"] = {draft["creator_id"]: draft for draft in active_drafts}
    except Exception as e:
        logger.error(f"Ошибка при загрузке активных черновиков: {e}")
        application.bot_data["active_drafts"] = {}

    # Создаем обработчик продолжения
    continue_handler = MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Entity("mention"),
        continue_creation
    )

    # Добавляем обработчики в правильном порядке:
    # 1. Обработчик кнопки "Отмена" (должен быть первым, чтобы перехватывать cancel_input)
    application.add_handler(CallbackQueryHandler(cancel_input, pattern="^cancel_input$"))

    # 3. Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))

    # 4. Обработчик кнопки "Мои мероприятия"
    application.add_handler(CallbackQueryHandler(my_events_button, pattern="^my_events$"))

    # 5. ConversationHandler для создания мероприятия
    application.add_handler(conv_handler_create_mention)
    application.add_handler(conv_handler_create)
    # 2. Обработчик продолжения
    application.add_handler(continue_handler)


    # 6. ConversationHandler для редактирования мероприятия
    application.add_handler(conv_handler_edit_event)

    # 7. Общий обработчик кнопок (должен быть последним)
    application.add_handler(CallbackQueryHandler(button_handler))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    application.run_polling()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логируем ошибки и уведомляем пользователя."""
    logger.error(msg="Исключение при обработке обновления:", exc_info=context.error)

    if update and hasattr(update, 'effective_message'):
        text = "⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз."
        await update.effective_message.reply_text(text)

if __name__ == "__main__":
    main()