from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
import logging
from datetime import datetime
from dotenv import load_dotenv
import os
from data.database import init_db, add_event, get_event, update_event, update_message_id, update_event_description, delete_event
from datetime import datetime, timedelta

# Загружаем переменные окружения из .env
load_dotenv("data/.env")  # Указываем путь к .env

# Получаем токен бота из переменной окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Проверяем, что токен загружен
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле.")

# Включаем логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT = range(4)
EDIT_EVENT, DELETE_EVENT = range(5, 7)
GET_EVENT_ID, GET_NEW_DESCRIPTION = range(7, 9)  # Новые состояния для команды /edit_event

# Глобальная переменная для пути к базе данных
DB_PATH = "../data/events.db"

# Инициализация базы данных
init_db(DB_PATH)  # Указываем путь к базе данных

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Привет! Я бот для организации мероприятий. Нажми кнопку ниже, чтобы создать мероприятие.",
        reply_markup=reply_markup,
    )

# Обработка упоминания бота
async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return

    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            keyboard = [
                [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Вы упомянули меня! Хотите создать мероприятие? Нажмите кнопку ниже.",
                reply_markup=reply_markup,
            )
            break

# Обработка нажатия на кнопку "Создать мероприятие"
async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Сохраняем chat_id в context.user_data
    context.user_data["chat_id"] = query.message.chat_id

    await query.edit_message_text("Введите описание мероприятия:")
    return SET_DESCRIPTION

# Обработка ввода описания мероприятия
async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("Введите дату мероприятия в формате ДД.ММ.ГГГГ:")
    return SET_DATE

# Обработка ввода даты мероприятия
async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()
        context.user_data["date"] = date
        await update.message.reply_text("Введите время мероприятия в формате ЧЧ:ММ:")
        return SET_TIME
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ:")
        return SET_DATE

# Обработка ввода времени мероприятия
async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text
    try:
        time = datetime.strptime(time_text, "%H:%M").time()
        context.user_data["time"] = time
        await update.message.reply_text("Введите количество участников (0 - неограниченное):")
        return SET_LIMIT
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ:")
        return SET_TIME

# Обработка ввода лимита участников
async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit_text = update.message.text
    try:
        limit = int(limit_text)
        if limit < 0:
            raise ValueError

        # Получаем путь к базе данных (с значением по умолчанию)
        db_path = context.bot_data["db_path"]

        # Создаём мероприятие в базе данных
        event_id = add_event(
            db_path=db_path,  # Передаём путь к базе данных
            description=context.user_data["description"],
            date=context.user_data["date"].strftime("%d-%m-%Y"),
            time=context.user_data["time"].strftime("%H:%M"),
            limit=limit if limit != 0 else None,  # Если лимит равен 0, сохраняем как None (бесконечный лимит)
        )

        await update.message.reply_text("Мероприятие создано!")

        # Отправляем сообщение с информацией о мероприятии
        chat_id = update.message.chat_id
        await send_event_message(event_id, context, chat_id)

        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:")
        return SET_LIMIT

def time_until_event(event_date: str, event_time: str) -> str:
    event_datetime = datetime.strptime(f"{event_date} {event_time}", "%d-%m-%Y %H:%M")
    now = datetime.now()
    if event_datetime > now:
        delta = event_datetime - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days} дней, {hours} часов, {minutes} минут"
    else:
        return "Мероприятие уже прошло."

# Отправка сообщения с информацией о мероприятии
async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if not chat_id:
        logger.error("chat_id не найден в send_event_message()")
        return

    db_path = context.bot_data.get("db_path", DB_PATH)
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    participants = "\n".join(event["participants"]) if event["participants"] else "Пока никто не участвует."
    reserve = "\n".join(event["reserve"]) if event["reserve"] else "Резерв пуст."
    limit_text = "∞ (бесконечный)" if event["limit"] is None else str(event["limit"])

    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")],
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    time_until = time_until_event(event['date'], event['time'])
    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {event['date']}\n"
        f"🕒 <i>Время: </i> {event['time']}\n"
        f"⏳ <i>До мероприятия: </i> {time_until}\n"
        f"👥 <i>Лимит участников: </i> {limit_text}\n\n"
        f"✅ <i>Участники: </i>\n{participants}\n\n"
        f"⏳ <i>Резерв: </i>\n{reserve}"
    )

    if event.get("message_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=event["message_id"],
                text=message_text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            logger.info(f"Редактируем сообщение с ID {event['message_id']}")
        except error.BadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")

    else:
        logger.info("Отправляем новое сообщение.")
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        logger.info(f"Сохраняем message_id: {message.message_id} для мероприятия {event_id}")
        update_message_id(db_path, event_id, message.message_id)

        # Пытаемся закрепить сообщение
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            logger.info(f"Сообщение {message.message_id} закреплено в чате {chat_id}.")
        except error.BadRequest as e:
            logger.error(f"Ошибка при закреплении сообщения: {e}")
            logger.error(f"Проверьте, что чат {chat_id} является группой или каналом.")
        except error.Forbidden as e:
            logger.error(f"Бот не имеет прав на закрепление сообщений: {e}")
            logger.error(f"Убедитесь, что бот является администратором и имеет права на закрепление.")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при закреплении сообщения: {e}")

# Обработка нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    # Разделяем action и event_id
    action, event_id = data.split("|")

    # Получаем путь к базе данных
    db_path = context.bot_data["db_path"]

    # Получаем данные о мероприятии
    event = get_event(db_path, event_id)  # Передаём db_path и event_id

    if not event:
        await query.answer("Мероприятие не найдено.")
        return

    # Формируем имя пользователя
    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

    # Обработка действия "Участвовать"
    if action == "join":
        if user_name in event["participants"] or user_name in event["reserve"]:
            await query.answer("Вы уже в списке участников или резерва.")
        else:
            # Если лимит равен None (бесконечный) или количество участников меньше лимита
            if event["limit"] is None or len(event["participants"]) < event["limit"]:
                event["participants"].append(user_name)
                await query.answer(f"{user_name}, вы добавлены в список участников!")
            else:
                event["reserve"].append(user_name)
                await query.answer(f"{user_name}, вы добавлены в резерв.")

    # Обработка действия "Не участвовать"
    elif action == "leave":
        if user_name in event["participants"]:
            event["participants"].remove(user_name)
            if event["reserve"]:
                new_participant = event["reserve"].pop(0)
                event["participants"].append(new_participant)
                await query.answer(
                    f"{user_name}, вы удалены из списка участников. {new_participant} добавлен из резерва.")
            else:
                await query.answer(f"{user_name}, вы удалены из списка участников.")
        elif user_name in event["reserve"]:
            event["reserve"].remove(user_name)
            await query.answer(f"{user_name}, вы удалены из резерва.")
        else:
            await query.answer("Вас нет в списке участников или резерва.")

    # Обработка действия "Редактировать"
    elif action == "edit":
        await query.answer("Редактирование мероприятия.")
        context.user_data["event_id"] = event_id  # Сохраняем event_id
        await query.edit_message_text("Введите новое описание мероприятия:")
        logger.info(f"Переход в состояние EDIT_EVENT")  # Логирование
        return EDIT_EVENT  # Возвращаем состояние EDIT_EVENT

    # Обработка действия "Удалить"
    elif action == "delete":
        await query.answer("Мероприятие удалено.")
        # Удаляем мероприятие из базы данных
        delete_event(db_path, event_id)
        await query.edit_message_text("Мероприятие удалено.")
        return ConversationHandler.END  # Завершаем диалог

    # Обновляем мероприятие в базе данных (для действий "Участвовать" и "Не участвовать")
    update_event(db_path, event_id, event["participants"], event["reserve"])

    # Отправляем или редактируем сообщение с обновленной информацией
    chat_id = query.message.chat_id  # Берем chat_id из сообщения
    await send_event_message(event_id, context, chat_id)

# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END

# Редактирование мероприятия
async def edit_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event_id = context.user_data.get("event_id")
    if not event_id:
        await update.message.reply_text("Ошибка: ID мероприятия не найден.")
        return ConversationHandler.END

    new_description = update.message.text
    db_path = context.bot_data["db_path"]

    # Логирование
    logger.info(f"Редактирование мероприятия {event_id}. Новое описание: {new_description}")

    # Обновляем описание мероприятия в базе данных
    update_event_description(db_path, event_id, new_description)

    # Отправляем подтверждение
    await update.message.reply_text("Описание мероприятия обновлено!")

    # Завершаем диалог
    return ConversationHandler.END

# Команда /edit_event
async def edit_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите ID мероприятия, которое хотите отредактировать:")
    return GET_EVENT_ID

# Обработка ввода ID мероприятия
async def get_event_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event_id = update.message.text
    try:
        event_id = int(event_id)  # Преобразуем в число
        context.user_data["event_id"] = event_id
        await update.message.reply_text("Введите новое описание мероприятия:")
        return GET_NEW_DESCRIPTION
    except ValueError:
        await update.message.reply_text("Неверный формат ID. Введите число.")
        return GET_EVENT_ID

# Обработка ввода нового описания
async def get_new_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event_id = context.user_data.get("event_id")
    if not event_id:
        await update.message.reply_text("Ошибка: ID мероприятия не найден.")
        return ConversationHandler.END

    new_description = update.message.text
    db_path = context.bot_data["db_path"]

    # Логирование
    logger.info(f"Редактирование мероприятия {event_id}. Новое описание: {new_description}")

    # Обновляем описание мероприятия в базе данных
    update_event_description(db_path, event_id, new_description)

    # Отправляем подтверждение
    await update.message.reply_text("Описание мероприятия обновлено!")

    # Завершаем диалог
    return ConversationHandler.END

# Основная функция
def main():
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()

    # Сохраняем путь к базе данных в context.bot_data
    application.bot_data["db_path"] = DB_PATH

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))

    # Регистрируем обработчик упоминаний
    application.add_handler(MessageHandler(filters.Entity("mention"), mention_handler))

    # ConversationHandler для создания мероприятия
    conv_handler_create = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_event_button, pattern="^create_event$")],
        states={
            SET_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_description)],
            SET_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_date)],
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_time)],
            SET_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_create)

    # ConversationHandler для редактирования мероприятия
    conv_handler_edit = ConversationHandler(
        entry_points=[CommandHandler("edit_event", edit_event_command)],
        states={
            GET_EVENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_event_id)],
            GET_NEW_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_edit)

    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()