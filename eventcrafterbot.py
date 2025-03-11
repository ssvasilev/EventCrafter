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
from data.database import init_db, add_event, get_event, update_event, update_message_id, \
    delete_event, update_event_field, is_user_in_declined, remove_from_declined, is_user_in_participants, \
    is_user_in_reserve, add_participant, get_participants_count, add_to_reserve, remove_participant, add_to_declined, \
    remove_from_reserve, get_reserve, get_participants, get_declined, get_db_connection, add_scheduled_job, \
    get_scheduled_job_id, delete_scheduled_job, get_events_by_participant
from datetime import datetime, timedelta
import pytz  # Библиотека для работы с часовыми поясами
import locale

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')  # Для Linux

# Загружаем переменные окружения из .env
load_dotenv("data/.env")  # Указываем путь к .env

# Получаем токен бота из переменной окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Получаем часовой пояс из переменной окружения
TIMEZONE = os.getenv('TIMEZONE', 'UTC')  # По умолчанию используется UTC

# Проверяем, что токен загружен
if not BOT_TOKEN:
    raise ValueError("Токен бота не найден в .env файле.")

# Устанавливаем часовой пояс
try:
    tz = pytz.timezone(TIMEZONE)
except pytz.UnknownTimeZoneError:
    logger.error(f"Неизвестный часовой пояс: {TIMEZONE}. Используется UTC.")
    tz = pytz.UTC

# Включаем логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def time_until_event(event_date: str, event_time: str) -> str:
    """
    Вычисляет оставшееся время до мероприятия с учетом часового пояса.
    :param event_date: Дата мероприятия в формате "дд-мм-гггг".
    :param event_time: Время мероприятия в формате "чч:мм".
    :return: Строка с оставшимся временем в формате "X дней, Y часов, Z минут".
    """
    # Преобразуем дату и время мероприятия в объект datetime
    event_datetime = datetime.strptime(f"{event_date} {event_time}", "%d-%m-%Y %H:%M")
    event_datetime = tz.localize(event_datetime)  # Устанавливаем часовой пояс

    # Получаем текущее время с учетом часового пояса
    now = datetime.now(tz)

    # Если мероприятие уже прошло, возвращаем соответствующее сообщение
    if event_datetime <= now:
        return "Мероприятие уже прошло."

    # Вычисляем разницу между текущим временем и временем мероприятия
    delta = event_datetime - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    return f"{days} дней, {hours} часов, {minutes} минут"


def format_date_with_weekday(date_str):
    """
    Форматирует дату в формате "дд-мм-гггг" в строку с днем недели.
    :param date_str: Дата в формате "дд-мм-гггг".
    :return: Строка в формате "дд.мм.гггг (ДеньНедели)".
    """
    date_obj = datetime.strptime(date_str, "%d-%m-%Y")
    return date_obj.strftime("%d.%m.%Y (%A)")  # %A — полное название дня недели


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
    # Создаем клавиатуру с кнопками
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
        [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с клавиатурой
    sent_message = await update.message.reply_text(
        "Привет! Я бот для организации мероприятий. Выберите действие:",
        reply_markup=reply_markup,
    )

    # Сохраняем ID сообщения бота в context.user_data
    context.user_data["bot_message_id"] = sent_message.message_id
    context.user_data["chat_id"] = update.message.chat_id


# Обработка упоминания бота
async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return

    # Проверяем, упомянут ли бот
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[
                                        entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            # Получаем текст сообщения после упоминания
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            # Если текст после упоминания не пустой, сохраняем его как описание
            if mention_text:
                context.user_data["description"] = mention_text

                # Создаем клавиатуру с кнопкой "Отмена"
                keyboard = [
                    [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем сообщение с запросом даты
                sent_message = await update.message.reply_text(
                    f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                    reply_markup=reply_markup,
                )

                # Сохраняем ID сообщения бота и chat_id
                context.user_data["bot_message_id"] = sent_message.message_id
                context.user_data["chat_id"] = update.message.chat_id

                # Удаляем сообщение пользователя
                await update.message.delete()

                # Переходим к состоянию SET_DATE
                return SET_DATE
            else:
                # Если текст после упоминания пустой, предлагаем создать мероприятие
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                    [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем сообщение с клавиатурой
                sent_message = await update.message.reply_text(
                    "Вы упомянули меня! Хотите создать мероприятие? Нажмите кнопку ниже.",
                    reply_markup=reply_markup,
                )

                # Сохраняем ID сообщения бота
                context.user_data["bot_message_id"] = sent_message.message_id
                context.user_data["chat_id"] = update.message.chat_id
                break

#Обработка нажатия на кнопку "Мои мероприятия"
async def my_events_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    db_path = context.bot_data["db_path"]

    # Получаем мероприятия, в которых участвует пользователь
    events = get_events_by_participant(db_path, user_id)

    if not events:
        await query.edit_message_text("Вы не участвуете ни в одном мероприятии.")
        return

    # Группируем мероприятия по чатам
    events_by_chat = {}
    for event in events:
        chat_id = event["chat_id"]
        if chat_id not in events_by_chat:
            events_by_chat[chat_id] = []
        events_by_chat[chat_id].append(event)

    # Формируем сообщение с группировкой по чатам
    message_text = "📋 Мероприятия, в которых вы участвуете:\n\n"
    for chat_id, events_in_chat in events_by_chat.items():
        # Получаем информацию о чате
        try:
            chat = await context.bot.get_chat(chat_id)
            chat_name = chat.title or chat.username or f"Чат {chat_id}"
            chat_link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else f"Чат {chat_id}"
        except Exception as e:
            logger.error(f"Ошибка при получении информации о чате {chat_id}: {e}")
            chat_name = f"Чат {chat_id}"
            chat_link = f"Чат {chat_id}"

        message_text += f"💬 <b>{chat_name}</b> ({chat_link}):\n"
        for event in events_in_chat:
            event_link = f"https://t.me/c/{str(chat_id).replace('-100', '')}/{event['message_id']}"
            message_text += f"  - <a href='{event_link}'>📅 {event['description']}</a> ({event['date']} {event['time']})\n"
        message_text += "\n"

    # Отправляем сообщение в личный чат с пользователем
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await query.edit_message_text("Список мероприятий отправлен вам в личные сообщения.")
    except error.Forbidden:
        await query.edit_message_text("Не удалось отправить сообщение. Пожалуйста, начните чат с ботом.")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await query.edit_message_text("Произошла ошибка при отправке списка мероприятий.")


# Обработка нажатия на кнопку "Создать мероприятие"
async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию SET_DESCRIPTION
    return SET_DESCRIPTION


# Обработка ввода описания мероприятия
async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем описание мероприятия
    description = update.message.text
    context.user_data["description"] = description

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
        reply_markup=reply_markup,
    )

    # Удаляем сообщение пользователя
    await update.message.delete()

    # Переходим к состоянию SET_DATE
    return SET_DATE


# Обработка ввода даты мероприятия
async def set_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем дату мероприятия
    date_text = update.message.text
    try:
        date = datetime.strptime(date_text, "%d.%m.%Y").date()
        context.user_data["date"] = date

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {context.user_data['description']}\n\n📅 Дата: {date_text}\n\nВведите время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Переходим к состоянию SET_TIME
        return SET_TIME
    except ValueError:
        # Если формат даты неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_DATE
        return SET_DATE


# Обработка ввода времени мероприятия
async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем время мероприятия
    time_text = update.message.text
    try:
        time = datetime.strptime(time_text, "%H:%M").time()
        context.user_data["time"] = time

        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Редактируем существующее сообщение бота
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=f"📢 {context.user_data['description']}\n\n📅 Дата: {context.user_data['date'].strftime('%d.%m.%Y')}\n\n🕒 Время: {time_text}\n\nВведите количество участников (0 - неограниченное):",
            reply_markup=reply_markup,
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Переходим к состоянию SET_LIMIT
        return SET_LIMIT
    except ValueError:
        # Если формат времени неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_TIME
        return SET_TIME


# Обработка ввода лимита участников
async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем текст сообщения с лимитом участников
    limit_text = update.message.text
    try:
        # Преобразуем введённый текст в число
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Получаем данные мероприятия из context.user_data
        description = context.user_data.get("description")
        date = context.user_data.get("date")
        time = context.user_data.get("time")
        creator_id = update.message.from_user.id
        chat_id = update.message.chat_id

        # Проверяем, что все необходимые данные есть
        if not all([description, date, time, creator_id, chat_id]):
            await update.message.reply_text("Ошибка: недостаточно данных для создания мероприятия.")
            return ConversationHandler.END

        # Создаём мероприятие в базе данных
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=description,
            date=date.strftime("%d-%m-%Y"),  # Преобразуем дату в строку
            time=time.strftime("%H:%M"),     # Преобразуем время в строку
            limit=limit if limit != 0 else None,  # Лимит участников (0 -> None)
            creator_id=creator_id,
            chat_id=chat_id,
            message_id=None  # message_id будет обновлён после отправки сообщения
        )

        # Проверяем, что мероприятие успешно создано
        if not event_id:
            await update.message.reply_text("Ошибка при создании мероприятия.")
            return ConversationHandler.END

        # Сохраняем event_id в context.user_data для дальнейшего использования
        context.user_data["event_id"] = event_id

        # Удаляем последнее сообщение бота с параметрами мероприятия
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, chat_id)

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Планируем задачи для уведомлений и удаления мероприятия
        event_datetime = datetime.strptime(f"{date.strftime('%d-%m-%Y')} {time.strftime('%H:%M')}", "%d-%m-%Y %H:%M")
        event_datetime = tz.localize(event_datetime)  # Устанавливаем часовой пояс

        # Уведомление за день до мероприятия
        context.job_queue.run_once(
            send_notification,
            when=event_datetime - timedelta(days=1),
            data={"event_id": event_id, "time_until": "1 день"},
        )

        # Уведомление за 15 минут до мероприятия
        context.job_queue.run_once(
            send_notification,
            when=event_datetime - timedelta(minutes=15),
            data={"event_id": event_id, "time_until": "15 минут"},
        )

        # Задача для открепления и удаления мероприятия после его завершения
        context.job_queue.run_once(
            unpin_and_delete_event,
            when=event_datetime,
            data={"event_id": event_id, "chat_id": chat_id},
        )

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError as e:
        # Если введённый текст не является числом или лимит отрицательный
        error_message = (
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )

        # Редактируем существующее сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=error_message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]),
            parse_mode="HTML"
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии SET_LIMIT
        return SET_LIMIT


# Отправка сообщения с информацией о мероприятии
async def send_event_message(event_id, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int = None):
    if not chat_id:
        logger.error("chat_id не найден в send_event_message()")
        return

    db_path = context.bot_data.get("db_path", DB_PATH)
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    # Получаем участников, резерв и отказавшихся
    participants = get_participants(db_path, event_id)
    reserve = get_reserve(db_path, event_id)
    declined = get_declined(db_path, event_id)

    # Используем отформатированную дату с днём недели
    formatted_date = context.user_data.get("formatted_date", event['date'])

    # Форматируем списки
    participants_text = (
        "\n".join([p["user_name"] for p in participants])
        if participants
        else "Ещё никто не участвует."
    )
    reserve_text = (
        "\n".join([p["user_name"] for p in reserve])
        if reserve
        else "Резерв пуст."
    )
    declined_text = (
        "\n".join([p["user_name"] for p in declined])
        if declined
        else "Отказавшихся нет."
    )

    # Лимит участников
    limit_text = "∞ (бесконечный)" if event["limit"] is None else str(event["limit"])

    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Текст сообщения
    time_until = time_until_event(event['date'], event['time'])
    message_text = (
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {formatted_date}\n"  # Используем отформатированную дату
        f"🕒 <i>Время: </i> {event['time']}\n"
        f"⏳ <i>До мероприятия: </i> {time_until}\n"
        f"👥 <i>Лимит участников: </i> {limit_text}\n\n"
        f"✅ <i>Участники: </i>\n{participants_text}\n\n"
        f"⏳ <i>Резерв: </i>\n{reserve_text}\n\n"
        f"❌ <i>Отказавшиеся: </i>\n{declined_text}"
    )

    if message_id:
        # Редактируем существующее сообщение
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        # Отправляем новое сообщение
        message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        # Сохраняем message_id в базе данных
        update_message_id(db_path, event_id, message.message_id)
        message_id = message.message_id

        # Пытаемся закрепить сообщение
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Сообщение {message_id} закреплено в чате {chat_id}.")
        except error.BadRequest as e:
            logger.error(f"Ошибка при закреплении сообщения: {e}")
        except error.Forbidden as e:
            logger.error(f"Бот не имеет прав на закрепление сообщений: {e}")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при закреплении сообщения: {e}")

    return message_id


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
    user_id = user.id
    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

    # Обработка действия "Участвовать"
    if action == "join":
        # Если пользователь в списке "Отказавшиеся", удаляем его оттуда
        if is_user_in_declined(db_path, event_id, user_id):
            remove_from_declined(db_path, event_id, user_id)

        # Если пользователь уже в списке участников или резерва
        if is_user_in_participants(db_path, event_id, user_id) or is_user_in_reserve(db_path, event_id, user_id):
            await query.answer("Вы уже в списке участников или резерва.")
        else:
            # Если есть свободные места, добавляем в участники
            if event["limit"] is None or get_participants_count(db_path, event_id) < event["limit"]:
                add_participant(db_path, event_id, user_id, user_name)
                await query.answer(f"{user_name}, вы добавлены в список участников!")
            else:
                # Если мест нет, добавляем в резерв
                add_to_reserve(db_path, event_id, user_id, user_name)
                await query.answer(f"{user_name}, вы добавлены в резерв.")

    # Обработка действия "Не участвовать"
    elif action == "leave":
        # Если пользователь в списке участников
        if is_user_in_participants(db_path, event_id, user_id):
            # Удаляем пользователя из участников
            remove_participant(db_path, event_id, user_id)
            # Добавляем его в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)

            # Если в резерве есть пользователи, перемещаем первого из резерва в участники
            reserve = get_reserve(db_path, event_id)
            if reserve:
                new_participant = reserve[0]
                remove_from_reserve(db_path, event_id, new_participant["user_id"])
                add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])
                await query.answer(
                    f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся. "
                    f"{new_participant['user_name']} перемещён из резерва в участники."
                )
            else:
                await query.answer(f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся.")

        # Если пользователь в резерве
        elif is_user_in_reserve(db_path, event_id, user_id):
            # Удаляем пользователя из резерва
            remove_from_reserve(db_path, event_id, user_id)
            # Добавляем его в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы удалены из резерва и добавлены в список отказавшихся.")

        # Если пользователь уже в списке "Отказавшиеся"
        elif is_user_in_declined(db_path, event_id, user_id):
            await query.answer("Вы уже в списке отказавшихся.")

        # Если пользователя нет ни в одном из списков
        else:
            # Добавляем пользователя в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы добавлены в список отказавшихся.")

    # Редактируем существующее сообщение
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    await send_event_message(event_id, context, chat_id, message_id)


# Обработка нажатия на кнопку "Редактировать"
async def edit_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    # Сохраняем event_id в context.user_data
    event_id = query.data.split("|")[1]
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    # Проверяем, является ли пользователь создателем
    if event["creator_id"] != query.from_user.id:
        # Если пользователь не создатель, показываем уведомление
        await query.answer("Вы не можете редактировать это мероприятие.")
        return  # Завершаем выполнение функции

    # Сохраняем исходное сообщение
    context.user_data["original_message_id"] = query.message.message_id  # ID исходного сообщения
    context.user_data["original_message_text"] = query.message.text  # Текст исходного сообщения
    context.user_data["original_reply_markup"] = query.message.reply_markup  # Клавиатура исходного сообщения

    context.user_data["event_id"] = event_id

    # Создаем клавиатуру для выбора параметра редактирования
    keyboard = [
        [
            InlineKeyboardButton("📝 Описание", callback_data=f"edit_description|{event_id}"),
            InlineKeyboardButton("👥 Лимит участников", callback_data=f"edit_limit|{event_id}")

        ],
        [
            InlineKeyboardButton("📅 Дата", callback_data=f"edit_date|{event_id}"),
            InlineKeyboardButton("🕒 Время", callback_data=f"edit_time|{event_id}")
        ],
        [
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete|{event_id}"),
            InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.answer()

    await query.edit_message_text(
        "Что вы хотите изменить?",
        reply_markup=reply_markup,
    )
    return EDIT_EVENT


async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Определяем, какое действие выбрал пользователь
    data = query.data
    if data == "cancel_input":  # Если нажата кнопка "Отмена"
        await cancel_input(update, context)
        return ConversationHandler.END

    action, event_id = data.split("|")
    context.user_data["event_id"] = event_id

    # Получаем данные о мероприятии
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено.")
        return ConversationHandler.END

    # Открепляем сообщение, если оно закреплено
    try:
        await context.bot.unpin_chat_message(
            chat_id=query.message.chat_id,
            message_id=event["message_id"]
        )
        logger.info(f"Сообщение {event['message_id']} откреплено.")
    except error.BadRequest as e:
        logger.error(f"Ошибка при откреплении сообщения: {e}")
    except error.Forbidden as e:
        logger.error(f"Бот не имеет прав на открепление сообщений: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при откреплении сообщения: {e}")

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if action == "edit_description":
        await query.edit_message_text(
            "Введите новое описание мероприятия:",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_DESCRIPTION
    elif action == "edit_date":
        await query.edit_message_text(
            "Введите новую дату мероприятия в формате ДД.ММ.ГГГГ",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_DATE
    elif action == "edit_time":
        await query.edit_message_text(
            "Введите новое время мероприятия в формате ЧЧ:ММ",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_TIME
    elif action == "edit_limit":
        await query.edit_message_text(
            "Введите новый лимит участников (0 - неограниченное):",
            reply_markup=reply_markup,  # Добавляем кнопку "Отмена"
        )
        return EDIT_LIMIT
    elif action == "delete":
        # Проверяем, является ли пользователь создателем
        if event["creator_id"] != query.from_user.id:
            await query.answer("Вы не можете удалить это мероприятие.")
            return

        # Удаляем мероприятие
        delete_event(db_path, event_id)  # функция для удаления
        await query.edit_message_text("Мероприятие удалено.")
        return ConversationHandler.END
    else:
        # Если действие не распознано, возвращаемся к выбору
        await query.edit_message_text("Неизвестное действие.")
        return EDIT_EVENT


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Восстанавливаем исходное сообщение
    original_message_id = context.user_data.get("original_message_id")
    original_message_text = context.user_data.get("original_message_text")
    original_reply_markup = context.user_data.get("original_reply_markup")

    if original_message_id and original_message_text:
        try:
            await query.edit_message_text(
                text=original_message_text,
                reply_markup=original_reply_markup,
                parse_mode="HTML"  # Если используется HTML-разметка
            )
        except Exception as e:
            logger.error(f"Ошибка при восстановлении сообщения: {e}")
            await query.edit_message_text("Операция отменена.")
    else:
        await query.edit_message_text("Операция отменена.")

    return ConversationHandler.END


# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END


# Обработка редактирования описания
async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите новое описание мероприятия:",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию EDIT_DESCRIPTION
    return EDIT_DESCRIPTION


# Обработка ввода нового описания
async def save_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_description = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    # Обновляем описание в базе данных
    update_event_field(db_path, event_id, "description", new_description)

    # Удаляем последнее сообщение бота с запросом нового описания
    await context.bot.delete_message(
        chat_id=update.message.chat_id,
        message_id=context.user_data["bot_message_id"]
    )

    # Отправляем новое сообщение с информацией о мероприятии
    await send_event_message(event_id, context, update.message.chat_id)

    # Удаляем сообщение пользователя
    await update.message.delete()

    # Завершаем диалог
    return ConversationHandler.END


# Обработка редактирования даты
async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите новую дату мероприятия в формате ДД.ММ.ГГГГ",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию EDIT_DATE
    return EDIT_DATE


# Обработка ввода новой даты
async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем новую дату
    date_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        # Преобразуем введённую дату
        date = datetime.strptime(date_text, "%d.%m.%Y").date()

        # Форматируем дату с днём недели
        formatted_date = date.strftime("%d.%m.%Y (%A)")

        # Обновляем дату в базе данных
        update_event_field(db_path, event_id, "date", date.strftime("%d-%m-%Y"))

        # Сохраняем отформатированную дату в context.user_data
        context.user_data["formatted_date"] = formatted_date

        # Удаляем последнее сообщение бота с запросом новой даты
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, update.message.chat_id)

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError:
        # Если формат даты неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат даты. Попробуйте снова в формате ДД.ММ.ГГГГ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии EDIT_DATE
        return EDIT_DATE


# Обработка редактирования времени
async def edit_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите новое время мероприятия в формате ЧЧ:ММ",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию EDIT_TIME
    return EDIT_TIME


# Обработка ввода нового времени
async def save_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем новое время
    time_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        # Преобразуем введённое время
        time = datetime.strptime(time_text, "%H:%M").time()

        # Обновляем время в базе данных
        update_event_field(db_path, event_id, "time", time.strftime("%H:%M"))

        # Удаляем последнее сообщение бота с запросом нового времени
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, update.message.chat_id)

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError:
        # Если формат времени неверный, редактируем сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text="Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии EDIT_TIME
        return EDIT_TIME


# Обработка редактирования лимита участников
async def edit_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [
        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text="Введите новый лимит участников (0 - неограниченное):",
        reply_markup=reply_markup,
    )

    # Переходим к состоянию EDIT_LIMIT
    return EDIT_LIMIT


# Обработка ввода нового лимита
async def save_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем новый лимит
    limit_text = update.message.text
    event_id = context.user_data.get("event_id")
    db_path = context.bot_data["db_path"]

    try:
        # Преобразуем введённый текст в число
        limit = int(limit_text)

        # Проверяем, что лимит не отрицательный
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным.")

        # Обновляем лимит в базе данных
        update_event_field(db_path, event_id, "participant_limit", limit if limit != 0 else None)

        # Удаляем последнее сообщение бота с запросом нового лимита
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"]
        )

        # Отправляем новое сообщение с информацией о мероприятии
        await send_event_message(event_id, context, update.message.chat_id)

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Завершаем диалог
        return ConversationHandler.END

    except ValueError:
        # Если введённый текст не является числом или лимит отрицательный
        error_message = (
            "Неверный формат лимита. Введите положительное число или 0 для неограниченного числа участников:"
        )

        # Редактируем существующее сообщение бота с ошибкой
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=context.user_data["bot_message_id"],
            text=error_message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]])
        )

        # Удаляем сообщение пользователя
        await update.message.delete()

        # Остаемся в состоянии EDIT_LIMIT
        return EDIT_LIMIT


async def send_notification(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет уведомление участникам мероприятия с учетом часового пояса."""
    event_id = context.job.data["event_id"]
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    participants = event["participants"]
    if not participants:
        return

    # Преобразуем дату и время мероприятия с учетом часового пояса
    event_datetime = datetime.strptime(f"{event['date']} {event['time']}", "%d-%m-%Y %H:%M")
    event_datetime = tz.localize(event_datetime)

    message = (
        f"⏰ Напоминание о мероприятии:\n"
        f"📢 <b>{event['description']}</b>\n"
        f"📅 <i>Дата: </i> {event_datetime.strftime('%d-%m-%Y')}\n"
        f"🕒 <i>Время: </i> {event_datetime.strftime('%H:%M')} ({TIMEZONE})\n"
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


async def unpin_and_delete_event(context: ContextTypes.DEFAULT_TYPE):
    """
    Открепляет сообщение мероприятия и удаляет его из базы данных.
    """
    event_id = context.job.data["event_id"]
    chat_id = context.job.data["chat_id"]
    db_path = context.bot_data["db_path"]

    # Получаем данные о мероприятии
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Мероприятие с ID {event_id} не найдено.")
        return

    # Открепляем сообщение
    try:
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=event["message_id"])
        logger.info(f"Сообщение {event['message_id']} откреплено в чате {chat_id}.")
    except error.BadRequest as e:
        logger.error(f"Ошибка при откреплении сообщения: {e}")
    except error.Forbidden as e:
        logger.error(f"Бот не имеет прав на открепление сообщений: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при откреплении сообщения: {e}")

    # Удаляем мероприятие из базы данных
    delete_event(db_path, event_id)
    logger.info(f"Мероприятие с ID {event_id} удалено из базы данных.")

    # Удаляем задачу из базы данных
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scheduled_jobs WHERE event_id = ?", (event_id,))
        conn.commit()
        logger.info(f"Задача для мероприятия с ID {event_id} удалена из базы данных.")

async def schedule_notifications(event_id: int, context: ContextTypes.DEFAULT_TYPE, event_datetime: datetime, chat_id: int):
    """
    Создаёт задачи для уведомлений за сутки и за 15 минут до мероприятия.
    :param event_id: ID мероприятия.
    :param context: Контекст бота.
    :param event_datetime: Дата и время мероприятия.
    :param chat_id: ID чата, в котором создано мероприятие.
    """
    db_path = context.bot_data["db_path"]

    # Уведомление за сутки
    job_day = context.job_queue.run_once(
        send_notification,
        when=event_datetime - timedelta(days=1),
        data={"event_id": event_id, "time_until": "1 день"},
        name=f"notification_{event_id}_day"
    )

    # Уведомление за 15 минут
    job_minutes = context.job_queue.run_once(
        send_notification,
        when=event_datetime - timedelta(minutes=15),
        data={"event_id": event_id, "time_until": "15 минут"},
        name=f"notification_{event_id}_minutes"
    )

    # Сохраняем задачи в базу данных
    add_scheduled_job(db_path, event_id, job_day.id, chat_id, event_datetime.isoformat(), job_type="notification_day")
    add_scheduled_job(db_path, event_id, job_minutes.id, chat_id, event_datetime.isoformat(), job_type="notification_minutes")

    logger.info(f"Созданы новые задачи напоминания для мероприятия {event_id}.")

async def schedule_unpin_and_delete(event_id: int, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Создаёт новую задачу на открепление и удаление мероприятия."""
    db_path = context.bot_data["db_path"]

    # Получаем обновлённые дату и время из базы
    event = get_event(db_path, event_id)
    if not event:
        logger.error(f"Ошибка: мероприятие {event_id} не найдено в базе!")
        return

    # Преобразуем дату и время мероприятия
    event_datetime = datetime.strptime(f"{event['date']} {event['time']}", "%d-%m-%Y %H:%M")
    event_datetime = tz.localize(event_datetime)  # Устанавливаем часовой пояс

    # Создаём новую задачу
    job = context.job_queue.run_once(
        unpin_and_delete_event,
        when=event_datetime,
        data={"event_id": event_id, "chat_id": chat_id},
        name=str(event_id)  # Имя задачи — ID мероприятия
    )

    # Сохраняем новую задачу в базу
    add_scheduled_job(db_path, event_id, job.id, chat_id, event_datetime.isoformat(), job_type="unpin_delete")

    logger.info(f"Создана новая задача {job.id} для мероприятия {event_id} на {event_datetime}")



async def restore_scheduled_jobs(application: Application):
    """
    Восстанавливает запланированные задачи из базы данных при запуске бота.
    """
    db_path = application.bot_data["db_path"]
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_jobs")
        jobs = cursor.fetchall()

        for job in jobs:
            event_id = job["event_id"]
            chat_id = job["chat_id"]
            execute_at = datetime.fromisoformat(job["execute_at"])

            # Проверяем, не истекло ли время выполнения задачи
            if execute_at > datetime.now(tz):
                # Создаем задачу
                application.job_queue.run_once(
                    unpin_and_delete_event,
                    when=execute_at,
                    data={"event_id": event_id, "chat_id": chat_id},
                )
                logger.info(f"Восстановлена задача для мероприятия с ID: {event_id}")
            else:
                # Если время выполнения задачи истекло, удаляем её из базы данных
                cursor.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job["id"],))
                conn.commit()
                logger.info(f"Удалена устаревшая задача для мероприятия с ID: {event_id}")

def remove_existing_job(event_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет существующую задачу для мероприятия, если она есть."""
    db_path = context.bot_data["db_path"]

    # Получаем ID старой задачи из базы
    job_id = get_scheduled_job_id(db_path, event_id)
    if job_id:
        # Удаляем задачу из JobQueue
        jobs = context.job_queue.get_jobs_by_name(str(event_id))
        if jobs:
            for job in jobs:
                job.schedule_removal()
                logger.info(f"Удалена старая задача {job.id} для мероприятия {event_id}")

        # Удаляем запись из базы
        delete_scheduled_job(db_path, event_id)
        logger.info(f"Задача для мероприятия {event_id} удалена из базы данных.")
    else:
        logger.warning(f"Задача для мероприятия {event_id} не найдена в базе данных.")

def remove_existing_notification_jobs(event_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Удаляет существующие задачи напоминания для мероприятия.
    """
    db_path = context.bot_data["db_path"]

    # Удаляем задачи из JobQueue
    jobs = context.job_queue.get_jobs_by_name(f"notification_{event_id}")
    for job in jobs:
        job.schedule_removal()
        logger.info(f"Удалена задача напоминания {job.id} для мероприятия {event_id}")

    # Удаляем задачи из базы данных
    delete_scheduled_job(db_path, event_id, job_type="notification")

# Основная функция
def main():
    # Создаём приложение и передаём токен
    application = Application.builder().token(BOT_TOKEN).build()
    job_queue = application.job_queue

    # Сохраняем путь к базе данных в context.bot_data
    application.bot_data["db_path"] = DB_PATH

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    #Обработчик для кнопки Мои мероприятия
    application.add_handler(CallbackQueryHandler(my_events_button, pattern="^my_events$"))

    # ConversationHandler для создания мероприятия
    conv_handler_create = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_event_button, pattern="^create_event$")],  # Кнопка "Создать
        # мероприятие"
        states={
            SET_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_description),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
            SET_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
            SET_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_time),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
            SET_LIMIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_create)

    # ConversationHandler для создания мероприятия по упоминанию
    conv_handler_create_mention = ConversationHandler(
        entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],  # Упоминание бота
        states={
            SET_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
            SET_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_time),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
            SET_LIMIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),  # Обработчик отмены
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_create_mention)

    # ConversationHandler для редактирования мероприятия
    conv_handler_edit_event = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_event_button, pattern="^edit\\|")],
        states={
            EDIT_EVENT: [
                CallbackQueryHandler(handle_edit_choice),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
            ],  # Ожидание выбора пользователя
            EDIT_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_description),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
            ],
            EDIT_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_date),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
            ],
            EDIT_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_time),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
            ],
            EDIT_LIMIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_limit),
                CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler_edit_event)

    # Регистрируем обработчик нажатий на кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    application.run_polling()

    # Восстанавливаем запланированные задачи
    application.run_polling(post_init=restore_scheduled_jobs)


if __name__ == "__main__":
    main()
