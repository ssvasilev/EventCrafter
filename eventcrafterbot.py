from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    JobQueue,
)
import logging
from datetime import datetime
from dotenv import load_dotenv
import os
from data.database import init_db, add_event, get_event, update_event, update_message_id, update_event_description, \
    delete_event, update_event_participant_limit, update_event_date, update_event_time
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


def time_until_event(event_date: str, event_time: str) -> str:
    """
    Вычисляет оставшееся время до мероприятия.
    :param event_date: Дата мероприятия в формате "дд-мм-гггг".
    :param event_time: Время мероприятия в формате "чч:мм".
    :return: Строка с оставшимся временем в формате "X дней, Y часов, Z минут".
    """
    # Преобразуем дату и время мероприятия в объект datetime
    event_datetime = datetime.strptime(f"{event_date} {event_time}", "%d-%m-%Y %H:%M")
    now = datetime.now()

    # Если мероприятие уже прошло, возвращаем соответствующее сообщение
    if event_datetime <= now:
        return "Мероприятие уже прошло."

    # Вычисляем разницу между текущим временем и временем мероприятия
    delta = event_datetime - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return f"{days} дней, {hours} часов, {minutes} минут"


# Состояния для ConversationHandler
SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT = range(4)
EDIT_EVENT, DELETE_EVENT = range(5, 7)
GET_EVENT_ID, GET_NEW_DESCRIPTION = range(7, 9)
EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT = range(10, 14)  # Состояния для редактирования

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
    """
    Обрабатывает ввод лимита участников и создает мероприятие.
    """
    limit_text = update.message.text
    try:
        # Преобразуем введенный текст в число
        limit = int(limit_text)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Логируем данные перед передачей в add_event
        logger.info(
            f"Данные для создания мероприятия: "
            f"description={context.user_data['description']}, "
            f"date={context.user_data['date'].strftime('%d-%m-%Y')}, "
            f"time={context.user_data['time'].strftime('%H:%M')}, "
            f"limit={limit}, "
            f"creator_id={update.message.from_user.id}"
        )

        # Создаём мероприятие в базе данных
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=context.user_data["description"],
            date=context.user_data["date"].strftime("%d-%m-%Y"),
            time=context.user_data["time"].strftime("%H:%M"),
            limit=limit if limit != 0 else None,  # 0 означает неограниченный лимит
            creator_id=update.message.from_user.id,
        )

        # Проверяем, что мероприятие успешно создано
        if not event_id:
            logger.error(f"Ошибка: мероприятие не было создано (event_id = None). {event_id}")
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        logger.info(f"Мероприятие успешно создано с ID: {event_id}")

        # Отправляем сообщение об успешном создании мероприятия
        await update.message.reply_text("Мероприятие создано!")

        # Отправляем сообщение с информацией о мероприятии
        chat_id = update.message.chat_id
        await send_event_message(event_id, context, chat_id)

        # Планируем уведомления (если JobQueue настроен)
        if hasattr(context, "job_queue"):
            event_datetime = datetime.strptime(
                f"{context.user_data['date'].strftime('%d-%m-%Y')} {context.user_data['time'].strftime('%H:%M')}",
                "%d-%m-%Y %H:%M"
            )

            # Уведомление за день до мероприятия
            context.job_queue.run_once(
                send_notification,
                when=event_datetime - timedelta(days=1),
                data={"event_id": event_id, "time_until": "1 день"},
            )

            # Уведомление за час до мероприятия
            context.job_queue.run_once(
                send_notification,
                when=event_datetime - timedelta(hours=1),
                data={"event_id": event_id, "time_until": "1 час"},
            )

            logger.info(f"Уведомления запланированы для мероприятия с ID: {event_id}")
        else:
            logger.warning("JobQueue не настроен. Уведомления не будут отправлены.")

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError as e:
        logger.error(f"Ошибка при обработке лимита: {e}")
        await update.message.reply_text(
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )
        return SET_LIMIT


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
        update_message_id(db_path, event_id, message.message_id)  # Сохраняем message_id в базе данных


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
    event = get_event(db_path, event_id)

    if not event:
        await query.answer("Мероприятие не найдено.")
        return

    # Формируем имя пользователя
    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

    # Обработка действия "Участвовать"
    if action == "join":
        user_id = user.id
        user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

        if user_name in event["participants"] or user_name in event["reserve"]:
            await query.answer("Вы уже в списке участников или резерва.")
        else:
            if event["limit"] is None or len(event["participants"]) < event["limit"]:
                event["participants"].append({"name": user_name, "user_id": user_id})
                await query.answer(f"{user_name}, вы добавлены в список участников!")
            else:
                event["reserve"].append({"name": user_name, "user_id": user_id})
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

    # Обработка действия "Удалить"
    elif action == "delete":
        if event["creator_id"] != query.from_user.id:
            await query.answer("Вы не можете удалить это мероприятие.")
            return

        await query.answer("Мероприятие удалено.")
        delete_event(db_path, event_id)
        await query.edit_message_text("Мероприятие удалено.")
        return ConversationHandler.END

    # Обновляем мероприятие в базе данных
    update_event(db_path, event_id, event["participants"], event["reserve"])

    # Отправляем или редактируем сообщение с обновленной информацией
    chat_id = query.message.chat_id
    await send_event_message(event_id, context, chat_id)


# Обработка нажатия на кнопку "Редактировать"
async def edit_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Сохраняем event_id в context.user_data
    event_id = query.data.split("|")[1]
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    # Проверяем, является ли пользователь создателем
    if event["creator_id"] != query.from_user.id:
        await query.answer("Вы не можете редактировать это мероприятие.")
        return

    context.user_data["event_id"] = event_id

    # Создаем клавиатуру для выбора параметра редактирования
    keyboard = [
        [InlineKeyboardButton("📝 Описание", callback_data=f"edit_description|{event_id}")],
        [InlineKeyboardButton("📅 Дата", callback_data=f"edit_date|{event_id}")],
        [InlineKeyboardButton("🕒 Время", callback_data=f"edit_time|{event_id}")],
        [InlineKeyboardButton("👥 Лимит участников", callback_data=f"edit_limit|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Что вы хотите изменить?",
        reply_markup=reply_markup,
    )
    # Возвращаем состояние EDIT_EVENT, чтобы бот ждал выбора пользователя
    return EDIT_EVENT


async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Определяем, какое действие выбрал пользователь
    action, event_id = query.data.split("|")
    context.user_data["event_id"] = event_id

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

    # Если действие не распознано, возвращаемся к выбору
    return EDIT_EVENT


# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END


# Обработка редактирования описания
async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Введите новое описание мероприятия:")
    return EDIT_DESCRIPTION


# Обработка ввода нового описания
async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    # Обновляем описание в базе данных
    update_event_description(db_path, event_id, new_description)

    # Обновляем сообщение с информацией о мероприятии
    chat_id = update.message.chat_id
    await send_event_message(event_id, context, chat_id)

    await update.message.reply_text("Описание мероприятия обновлено!")
    return ConversationHandler.END


# Обработка редактирования даты
async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Введите новую дату мероприятия в формате ДД.ММ.ГГГГ:")
    return EDIT_DATE


# Обработка ввода новой даты
async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()
        # Обновляем дату в базе данных
        update_event_date(db_path, event_id, date.strftime("%d-%m-%Y"))

        # Обновляем сообщение с информацией о мероприятии
        chat_id = update.message.chat_id
        await send_event_message(event_id, context, chat_id)

        await update.message.reply_text("Дата мероприятия обновлена!")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ:")
        return EDIT_DATE


# Обработка редактирования времени
async def edit_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Введите новое время мероприятия в формате ЧЧ:ММ:")
    return EDIT_TIME


# Обработка ввода нового времени
async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        time = datetime.strptime(time_text, "%H:%M").time()
        # Обновляем время в базе данных
        update_event_time(db_path, event_id, time.strftime("%H:%M"))

        # Обновляем сообщение с информацией о мероприятии
        chat_id = update.message.chat_id
        await send_event_message(event_id, context, chat_id)

        await update.message.reply_text("Время мероприятия обновлено!")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ:")
        return EDIT_TIME


# Обработка редактирования лимита участников
async def edit_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("Введите новый лимит участников (0 - неограниченное):")
    return EDIT_LIMIT


# Обработка ввода нового лимита
async def save_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        limit = int(limit_text)
        if limit < 0:
            raise ValueError

        # Обновляем лимит в базе данных
        update_event_participant_limit(db_path, event_id, limit if limit != 0 else None)

        # Обновляем сообщение с информацией о мероприятии
        chat_id = update.message.chat_id
        await send_event_message(event_id, context, chat_id)

        await update.message.reply_text("Лимит участников обновлен!")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )
        return EDIT_LIMIT


async def send_notification(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет уведомление участникам мероприятия."""
    event_id = context.job.data["event_id"]
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    participants = event["participants"]
    if not participants:
        return

    message = (
        f"⏰ Напоминание о мероприятии:\n"
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {event['date']}\n"
        f"🕒 <i>Время: </i> {event['time']}\n"
        f"До начала осталось: {context.job.data['time_until']}"
    )

    for participant in participants:
        try:
            await context.bot.send_message(
                chat_id=participant["user_id"],  # Нужно сохранять user_id участников
                text=message,
                parse_mode="HTML"
            )
        except error.TelegramError as e:
            logger.error(f"Ошибка при отправке уведомления участнику {participant}: {e}")


# Основная функция
def main():
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()
    job_queue = application.job_queue

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
    conv_handler_edit_event = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_event_button, pattern="^edit\\|")],
        states={
            EDIT_EVENT: [CallbackQueryHandler(handle_edit_choice)],  # Ожидание выбора пользователя
            EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_description)],
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_date)],
            EDIT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_time)],
            EDIT_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_limit)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_edit_event)

    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    application.run_polling()


if __name__ == "__main__":
    main()
