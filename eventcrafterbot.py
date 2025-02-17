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
from data.database import init_db, add_event, get_event, update_event, update_message_id

# ToDo убрать это
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
EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT = range(4, 8)

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
        if entity.type == "mention" and update.message.text[
                                        entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
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


# Отправка сообщения с информацией о мероприятии
async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
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
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Добавляем временную метку
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата:</i> {event['date']}\n"
        f"🕒 <i>Время:</i> {event['time']}\n"
        f"👥 <i>Лимит участников:</i> {limit_text}\n\n"
        f"✅ <i>Участники:</i>\n{participants}\n\n"
        f"⏳ <i>Резерв:</i>\n{reserve}\n\n"
        f"<i><small>Обновлено: {timestamp}</small></i>"  # Временная метка
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
    chat_id = query.message.chat_id  # Получаем chat_id из query.message

    user = query.from_user
    data = query.data

    action, event_id = data.split("|")
    # action, event_id = data.split("|", maxsplit=1)

    # Получаем путь к базе данных
    db_path = context.bot_data["db_path"]

    # Получаем данные о мероприятии
    event = get_event(db_path, event_id)  # Передаём db_path и event_id

    if not event:
        await query.answer("Мероприятие не найдено.")
        return

    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

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
    elif action == "edit":
        event_id = query.data.split("|")[1]
        context.user_data["event_id"] = event_id
        keyboard = [
            [InlineKeyboardButton("Описание", callback_data=f"edit_description|{event_id}")],
            [InlineKeyboardButton("Дата", callback_data=f"edit_date|{event_id}")],
            [InlineKeyboardButton("Время", callback_data=f"edit_time|{event_id}")],
            [InlineKeyboardButton("Лимит", callback_data=f"edit_limit|{event_id}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Что вы хотите изменить?", reply_markup=reply_markup)

    # Обновляем мероприятие в базе данных
    update_event(db_path, event_id, event["participants"], event["reserve"])

    # Отправляем или редактируем сообщение
    chat_id = query.message.chat_id  # Берем chat_id из сообщения
    await send_event_message(event_id, context, chat_id)


async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("|")[1]
    context.user_data["event_id"] = event_id
    await query.message.reply_text("Введите новое описание мероприятия:")
    return EDIT_DESCRIPTION


async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("|")[1]
    context.user_data["event_id"] = event_id
    await query.message.reply_text("Введите новую дату мероприятия в формате ДД.ММ.ГГГГ:")
    return EDIT_DATE


async def edit_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("|")[1]
    context.user_data["event_id"] = event_id
    await query.message.reply_text("Введите новое время мероприятия в формате ЧЧ:ММ:")
    return EDIT_TIME


async def edit_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    event_id = query.data.split("|")[1]
    context.user_data["event_id"] = event_id
    await query.message.reply_text("Введите новый лимит участников (0 - неограниченное):")
    return EDIT_LIMIT

async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text
    event_id = context.user_data["event_id"]
    db_path = context.bot_data["db_path"]
    update_event(db_path, event_id, description=new_description)
    await update.message.reply_text("Описание мероприятия обновлено!")
    await send_event_message(event_id, context, update.message.chat_id)
    return ConversationHandler.END

async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_date_text = update.message.text
    try:
        new_date = datetime.strptime(new_date_text, "%d.%m.%Y").date()
        event_id = context.user_data["event_id"]
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)
        event["date"] = new_date.strftime("%d-%m-%Y")
        update_event(db_path, event_id, event["participants"], event["reserve"], date=new_date.strftime("%d-%m-%Y"))
        await update.message.reply_text("Дата мероприятия обновлена!")
        await send_event_message(event_id, context, update.message.chat_id)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ:")
        return EDIT_DATE

async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_time_text = update.message.text
    try:
        new_time = datetime.strptime(new_time_text, "%H:%M").time()
        event_id = context.user_data["event_id"]
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)
        event["time"] = new_time.strftime("%H:%M")
        update_event(db_path, event_id, event["participants"], event["reserve"], time=new_time.strftime("%H:%M"))
        await update.message.reply_text("Время мероприятия обновлено!")
        await send_event_message(event_id, context, update.message.chat_id)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ:")
        return EDIT_TIME

async def save_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_limit_text = update.message.text
    try:
        new_limit = int(new_limit_text)
        if new_limit < 0:
            raise ValueError
        event_id = context.user_data["event_id"]
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)
        event["limit"] = new_limit if new_limit != 0 else None
        update_event(db_path, event_id, event["participants"], event["reserve"], limit=new_limit if new_limit != 0 else None)
        await update.message.reply_text("Лимит участников обновлен!")
        await send_event_message(event_id, context, update.message.chat_id)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:")
        return EDIT_LIMIT


# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
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
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_event_button, pattern="^create_event$")],
        states={
            SET_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_description)],
            SET_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_date)],
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_time)],
            SET_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit)],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_description)],
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_date)],
            EDIT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_time)],
            EDIT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_limit)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)

    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    main()
