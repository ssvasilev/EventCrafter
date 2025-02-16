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

# Загружаем переменные окружения из .env
load_dotenv("data/.env")

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
init_db(DB_PATH)

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

# Обработка нажатия на кнопку "Создать мероприятие"
async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["chat_id"] = query.message.chat_id

    await query.edit_message_text("Введите описание мероприятия:")
    return SET_DESCRIPTION

# Обработка ввода описания мероприятия
async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_action")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Введите дату мероприятия в формате ДД.ММ.ГГГГ:", reply_markup=reply_markup)
    return SET_DATE

# Обработка ввода даты мероприятия
async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()
        context.user_data["date"] = date

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_action")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Введите время мероприятия в формате ЧЧ:ММ:", reply_markup=reply_markup)
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

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_action")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Введите количество участников (0 - неограниченное):", reply_markup=reply_markup)
        return SET_LIMIT
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ:")
        return SET_TIME

# Обработка ввода лимита участников
async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit_text = update.message.text
    try:
        participants_limit = int(limit_text)
        if participants_limit < 0:
            raise ValueError

        db_path = context.bot_data["db_path"]

        event_id = add_event(
            db_path=db_path,
            description=context.user_data["description"],
            date=context.user_data["date"].strftime("%d-%m-%Y"),
            time=context.user_data["time"].strftime("%H:%M"),
            participants_limit=participants_limit if participants_limit != 0 else None,
            participants="",
            reserve=""
        )

        await update.message.reply_text("Мероприятие создано!")

        chat_id = update.message.chat_id
        await send_event_message(event_id, context, chat_id)

        return ConversationHandler.END
    except ValueError:
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_action")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:",
            reply_markup=reply_markup,
        )
        return SET_LIMIT

# Обработчик для кнопки "Редактировать"
async def edit_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, event_id = query.data.split("|")
    context.user_data["event_id"] = event_id

    keyboard = [
        [InlineKeyboardButton("✏️ Описание", callback_data="edit_description")],
        [InlineKeyboardButton("📅 Дата", callback_data="edit_date")],
        [InlineKeyboardButton("🕒 Время", callback_data="edit_time")],
        [InlineKeyboardButton("👥 Лимит участников", callback_data="edit_limit")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_edit")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Что вы хотите отредактировать?",
        reply_markup=reply_markup,
    )

# Обработчик для выбора поля редактирования
async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data
    event_id = context.user_data["event_id"]

    if action == "edit_description":
        await query.edit_message_text("Введите новое описание мероприятия:")
        return EDIT_DESCRIPTION
    elif action == "edit_date":
        await query.edit_message_text("Введите новую дату мероприятия в формате ДД.ММ.ГГГГ:")
        return EDIT_DATE
    elif action == "edit_time":
        await query.edit_message_text("Введите новое время мероприятия в формате ЧЧ:ММ:")
        return EDIT_TIME
    elif action == "edit_limit":
        await query.edit_message_text("Введите новый лимит участников (0 - неограниченное):")
        return EDIT_LIMIT
    elif action == "cancel_edit":
        await query.edit_message_text("Редактирование отменено.")
        return ConversationHandler.END

# Обработчики для состояний редактирования
async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text
    event_id = context.user_data["event_id"]
    db_path = context.bot_data["db_path"]

    update_event(db_path, event_id, description=new_description)

    await update.message.reply_text("Описание мероприятия обновлено!")
    await send_event_message(event_id, context, update.message.chat_id)
    return ConversationHandler.END

async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_date_text = update.message.text
    try:
        new_date = datetime.strptime(new_date_text, "%d.%m.%Y").date()
        event_id = context.user_data["event_id"]
        db_path = context.bot_data["db_path"]

        update_event(db_path, event_id, date=new_date.strftime("%d-%m-%Y"))

        await update.message.reply_text("Дата мероприятия обновлена!")
        await send_event_message(event_id, context, update.message.chat_id)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ:")
        return EDIT_DATE

async def edit_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_time_text = update.message.text
    try:
        new_time = datetime.strptime(new_time_text, "%H:%M").time()
        event_id = context.user_data["event_id"]
        db_path = context.bot_data["db_path"]

        update_event(db_path, event_id, time=new_time.strftime("%H:%M"))

        await update.message.reply_text("Время мероприятия обновлено!")
        await send_event_message(event_id, context, update.message.chat_id)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ:")
        return EDIT_TIME

async def edit_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_limit_text = update.message.text
    try:
        new_limit = int(new_limit_text)
        if new_limit < 0:
            raise ValueError

        event_id = context.user_data["event_id"]
        db_path = context.bot_data["db_path"]

        update_event(db_path, event_id, participants_limit=new_limit if new_limit != 0 else None)

        await update.message.reply_text("Лимит участников обновлен!")
        await send_event_message(event_id, context, update.message.chat_id)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:")
        return EDIT_LIMIT

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
    participants_limit_text = "∞ (бесконечный)" if event["participants_limit"] is None else str(event["participants_limit"])

    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата:</i> {event['date']}\n"
        f"🕒 <i>Время:</i> {event['time']}\n"
        f"👥 <i>Лимит участников:</i> {participants_limit_text}\n\n"
        f"✅ <i>Участники:</i>\n{participants}\n\n"
        f"⏳ <i>Резерв:</i>\n{reserve}"
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

        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            logger.info(f"Сообщение {message.message_id} закреплено в чате {chat_id}.")
        except error.BadRequest as e:
            logger.error(f"Ошибка при закреплении сообщения: {e}")
        except error.Forbidden as e:
            logger.error(f"Бот не имеет прав на закрепление сообщений: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при закреплении сообщения: {e}")

# Обработка нажатий на кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if "|" in data:
        action, event_id = data.split("|")
    else:
        action = data
        event_id = None

    if action in ["join", "leave", "edit"]:
        if not event_id:
            await query.answer("Ошибка: мероприятие не найдено.")
            return

        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)
        if not event:
            await query.answer("Мероприятие не найдено.")
            return

        user = query.from_user
        user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

        if action == "join":
            if user_name in event["participants"] or user_name in event["reserve"]:
                await query.answer("Вы уже в списке участников или резерва.")
            else:
                if event["participants_limit"] is None or len(event["participants"]) < event["participants_limit"]:
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
                    await query.answer(f"{user_name}, вы удалены из списка участников. {new_participant} добавлен из резерва.")
                else:
                    await query.answer(f"{user_name}, вы удалены из списка участников.")
            elif user_name in event["reserve"]:
                event["reserve"].remove(user_name)
                await query.answer(f"{user_name}, вы удалены из резерва.")
            else:
                await query.answer("Вас нет в списке участников или резерва.")

        update_event(db_path, event_id, event["participants"], event["reserve"])

        chat_id = query.message.chat_id
        await send_event_message(event_id, context, chat_id)

    elif action == "cancel_action":
        await query.edit_message_text("Действие отменено.")
        return ConversationHandler.END

# Обработчик для кнопки "Отмена"
async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Действие отменено.")
    return ConversationHandler.END

# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END

# Основная функция
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Сохраняем путь к базе данных в context.bot_data
    application.bot_data["db_path"] = DB_PATH

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))

    # ConversationHandler для создания и редактирования мероприятия
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_event_button, pattern="^create_event$")],
        states={
            SET_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_description)],
            SET_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_date)],
            SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_time)],
            SET_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit)],
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_description)],
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_date)],
            EDIT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_time)],
            EDIT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_limit)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_action, pattern="^cancel_action$")],
    )
    application.add_handler(conv_handler)

    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()