from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from config import DB_PATH, tz, DB_DRAFT_PATH
from src.buttons.my_events_button import my_events_button
from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.handlers.button_handlers import button_handler
from src.handlers.cancel_handler import cancel_input, cancel
from src.handlers.create_event_handler import conv_handler_create
from src.handlers.edit_event_handlers import conv_handler_edit_event
from src.handlers.mention_handler import conv_handler_create_mention
from src.handlers.restore_handler import get_restore_handler, restore_handler
from src.handlers.start_handler import start
from src.handlers.version_handler import version

from src.jobs.notification_jobs import restore_scheduled_jobs
import os
from dotenv import load_dotenv
import locale

from src.logger.logger import logger

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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)

    if isinstance(update, Update):
        if update.callback_query:
            await update.callback_query.answer("⚠ Произошла ошибка")
        elif update.message:
            await update.message.reply_text("⚠ Произошла ошибка")

def main():
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_error_handler(error_handler)

    # Сохраняем путь к основной базе данных в context.bot_data
    application.bot_data["db_path"] = DB_PATH

    # Сохраняем путь к основной базе данных в context.bot_data
    application.bot_data["drafts_db_path"] = DB_DRAFT_PATH

    # Сохраняем часовой пояс в context.bot_data
    application.bot_data["tz"] = tz

    # 1. Обработчик восстановления (самый первый, для текстовых сообщений)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, restore_handler),
        group=0
    )

    # 2. Обработчик команды /cancel
    application.add_handler(CommandHandler("cancel", cancel))

    # 3. Обработчик кнопки отмены (должен быть перед общим обработчиком кнопок)
    application.add_handler(CallbackQueryHandler(cancel_input, pattern="^cancel_input$"))

    # 2. Обработчик упоминаний (раньше обычного создания)
    application.add_handler(conv_handler_create_mention, group=1)

    # 3. Обычный обработчик создания через кнопку
    application.add_handler(conv_handler_create, group=1)

    # 4. Остальные обработчики (команды, кнопки и т.д.)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))
    application.add_handler(CallbackQueryHandler(my_events_button, pattern="^my_events$"))
    application.add_handler(conv_handler_edit_event)
    application.add_handler(CallbackQueryHandler(button_handler))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    # Восстанавливаем запланированные задачи
    application.run_polling()

if __name__ == "__main__":
    main()