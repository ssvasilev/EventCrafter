from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from config import DB_PATH, tz, DB_DRAFT_PATH
from src.buttons.buttons import my_events_button
from src.database.init_database import init_db
from src.database.init_draft_database import init_drafts_db
from src.handlers.handler import (
    conv_handler_create, conv_handler_edit_event,
    conv_handler_create_mention, button_handler,
    start, version
)
from src.handlers.restore_state import restore_and_get_state
from src.jobs.notification_jobs import restore_scheduled_jobs
from src.handlers.other_handlers import setup_other_handlers
import os
from dotenv import load_dotenv
import locale

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
load_dotenv("data/.env")

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле.")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик входящих сообщений"""
    if not update.message:
        return None

    # Проверяем, ожидаем ли мы ввод от пользователя
    if context.user_data.get('expecting_input'):
        return None  # Пропускаем, пусть ConversationHandler обрабатывает

    # Пытаемся восстановить состояние
    state = await restore_and_get_state(update, context)
    return state


def setup_handlers(application):
    """Настройка обработчиков"""
    # Обработчик восстановления состояния (высокий приоритет)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler),
        group=1
    )


def main():
    # Инициализация баз данных
    init_db(DB_PATH)
    init_drafts_db(DB_DRAFT_PATH)

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Сохраняем конфигурационные данные
    application.bot_data.update({
        "db_path": DB_PATH,
        "drafts_db_path": DB_DRAFT_PATH,
        "tz": tz
    })
    setup_other_handlers(application)  # Добавить эту строку
    # Добавляем общий обработчик сообщений первым
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler),
        group=1  # Высокий приоритет
    )

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("version", version))
    application.add_handler(CallbackQueryHandler(my_events_button, pattern="^my_events$"))
    application.add_handler(conv_handler_create, group=2)
    application.add_handler(conv_handler_create_mention)
    application.add_handler(conv_handler_edit_event)
    application.add_handler(CallbackQueryHandler(button_handler))

    # Восстанавливаем запланированные задачи
    restore_scheduled_jobs(application)

    # Восстанавливаем запланированные задачи
    application.run_polling()

if __name__ == "__main__":
    main()