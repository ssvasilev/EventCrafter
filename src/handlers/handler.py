from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.buttons.buttons import create_event_button
from temp.set_date import set_date
from src.event.create.set_parameter import set_description
from temp.set_limit import set_limit
from temp.set_time import set_time
from src.handlers.cancel_handler import cancel_input, cancel
from src.handlers.conversation_handler_states import SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT

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
    per_message=False,
)

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    CommandHandler,
)

from temp.edit_event_button import edit_event_button
from src.database.db_operations import delete_event
import logging

from temp.date import save_date
from temp.description import save_description
from temp.limit import save_limit
from temp.time import save_time
from src.handlers.cancel_handler import cancel_input
from src.handlers.conversation_handler_states import EDIT_EVENT, EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT

logger = logging.getLogger(__name__)

# Обработка выбора параметра для редактирования
async def handle_edit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    #await query.answer()  # Подтверждаем получение callback-запроса

    # Определяем, какое действие выбрал пользователь
    data = query.data
    if data == "cancel_input":  # Если нажата кнопка "Отмена"
        await cancel_input(update, context)
        return ConversationHandler.END

    try:
        # Разделяем данные и преобразуем event_id в int
        action, event_id_str = data.split("|")
        event_id = int(event_id_str)  # Преобразуем строку в int
        context.user_data["event_id"] = event_id  # Сохраняем event_id в context.user_data
    except (ValueError, IndexError) as e:
        # Обрабатываем ошибки, если данные некорректны
        logger.error(f"Ошибка при обработке callback_data: {e}")
        await query.edit_message_text("Ошибка: неверные данные.")
        return ConversationHandler.END

    # Получаем данные о мероприятии
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено.")
        return ConversationHandler.END

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
            await query.answer("Вы не можете удалить это мероприятие.", show_alert=True)
            return

        # Получаем message_id мероприятия
        message_id = event.get("message_id")

        # Если message_id существует, пытаемся открепить сообщение
        if message_id:
            try:
                # Открепляем сообщение
                await context.bot.unpin_chat_message(
                    chat_id=query.message.chat_id,
                    message_id=message_id
                )
                logger.info(f"Сообщение мероприятия {event_id} откреплено.")
            except BadRequest as e:
                # Выводим ошибку, если открепление не удалось
                logger.error(f"Ошибка при откреплении сообщения: {e}")
                # Проверяем, связано ли это с отсутствием прав или с тем, что сообщение не закреплено
                if "not pinned" in str(e).lower():
                    logger.info(f"Сообщение {message_id} не было закреплено.")
                elif "not enough rights" in str(e).lower():
                    logger.error(f"Бот не имеет прав на открепление сообщений в этом чате.")
            except Exception as e:
                # Выводим любые другие ошибки
                logger.error(f"Неизвестная ошибка при откреплении сообщения: {e}")

        # Удаляем мероприятие из базы данных
        delete_event(db_path, event_id)
        logger.info(f"Мероприятие {event_id} удалено.")

        # Редактируем сообщение с подтверждением удаления
        await query.edit_message_text("Мероприятие удалено.")

        # Завершаем диалог
        return ConversationHandler.END




# ConversationHandler для редактирования мероприятия
conv_handler_edit_event = ConversationHandler(
    entry_points=[CallbackQueryHandler(edit_event_button, pattern="^edit\\|")],
    states={
        EDIT_EVENT: [
            CallbackQueryHandler(handle_edit_choice),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
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
    fallbacks=[CommandHandler("cancel_input", cancel_input)],
    per_message=False,
)

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from telegram.error import BadRequest

from temp.set_date import set_date
from temp.set_limit import set_limit
from temp.set_time import set_time
from src.handlers.cancel_handler import cancel, cancel_input
from src.handlers.conversation_handler_states import SET_DATE, SET_TIME, SET_LIMIT
from src.database.db_draft_operations import add_draft


async def mention_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.entities:
        return

    # Проверяем, упомянут ли бот
    for entity in update.message.entities:
        if entity.type == "mention" and update.message.text[entity.offset:entity.offset + entity.length] == f"@{context.bot.username}":
            # Получаем текст сообщения после упоминания
            mention_text = update.message.text[entity.offset + entity.length:].strip()

            if mention_text:
                try:
                    # Если текст после упоминания не пустой, создаем черновик мероприятия
                    creator_id = update.message.from_user.id
                    chat_id = update.message.chat_id
                    draft_id = add_draft(
                        db_path=context.bot_data["drafts_db_path"],
                        creator_id=creator_id,
                        chat_id=chat_id,
                        status="AWAIT_DATE",
                        description=mention_text
                    )

                    if not draft_id:
                        await update.message.reply_text("Ошибка при создании черновика мероприятия.")
                        return ConversationHandler.END

                    # Создаем клавиатуру с кнопкой "Отмена"
                    keyboard = [
                        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # Отправляем новое сообщение с запросом даты
                    sent_message = await update.message.reply_text(
                        f"📢 {mention_text}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                        reply_markup=reply_markup,
                    )

                    # Сохраняем ID черновика и сообщения бота
                    context.user_data.update({
                        "draft_id": draft_id,
                        "bot_message_id": sent_message.message_id,
                        "description": mention_text
                    })

                    # Пытаемся удалить сообщение пользователя (не критично, если не получится)
                    try:
                        await update.message.delete()
                    except BadRequest as e:
                        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")
                        # Просто продолжаем работу, не пытаемся редактировать сообщение пользователя

                    return SET_DATE

                except Exception as e:
                    logger.error(f"Ошибка при обработке упоминания: {e}")
                    await context.bot.send_message(
                        chat_id=update.message.chat_id,
                        text="Произошла ошибка при создании мероприятия. Пожалуйста, попробуйте снова."
                    )
                    return ConversationHandler.END

            else:
                # Если текст после упоминания пустой, предлагаем варианты
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
                    [InlineKeyboardButton("📋 Мои мероприятия", callback_data="my_events")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                try:
                    sent_message = await update.message.reply_text(
                        "Вы упомянули меня! Что вы хотите сделать?",
                        reply_markup=reply_markup,
                    )
                    context.user_data["bot_message_id"] = sent_message.message_id

                    # Пытаемся удалить оригинальное сообщение (не критично)
                    try:
                        await update.message.delete()
                    except BadRequest as e:
                        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке пустого упоминания: {e}")

                return ConversationHandler.END

# ConversationHandler для создания мероприятия по упоминанию
conv_handler_create_mention = ConversationHandler(
    entry_points=[MessageHandler(filters.Entity("mention") & filters.TEXT, mention_handler)],
    states={
        SET_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_date),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        SET_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_time),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
        SET_LIMIT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_limit),
            CallbackQueryHandler(cancel_input, pattern="^cancel_input$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    per_message=False,
)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 Создать мероприятие", callback_data="create_event")],
        [InlineKeyboardButton("📋 Мероприятия, в которых я участвую", callback_data="my_events")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await update.message.reply_text(
        "Привет! Я бот для организации мероприятий. Выберите действие:",
        reply_markup=reply_markup,
    )

    context.user_data["bot_message_id"] = sent_message.message_id
    context.user_data["chat_id"] = update.message.chat_id

from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ищем файл VERSION в текущей рабочей директории (/app в контейнере)
        version_path = Path("/app/VERSION")

        if not version_path.exists():
            await update.message.reply_text(
                f"Файл VERSION не найден по пути: {version_path}",
                reply_to_message_id=update.message.message_id
            )
            return

        with open(version_path, 'r') as f:
            version_text = f.read().strip()

        await update.message.reply_text(
            f"📌 Версия бота: {version_text}",
            reply_to_message_id=update.message.message_id
        )

    except Exception as e:
        print(f"Ошибка при чтении версии: {e}")
        await update.message.reply_text(
            f"⚠ Ошибка при чтении версии: {e}",
            reply_to_message_id=update.message.message_id
        )

from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_operations import (
    add_participant,
    remove_participant,
    add_to_declined,
    remove_from_reserve,
    get_event,
    remove_from_declined,
    is_user_in_participants,
    is_user_in_reserve,
    get_participants_count,
    add_to_reserve,
    get_reserve, is_user_in_declined,
)
from src.message.send_message import send_event_message


#Обработка нажатий на кнопки "Участвовать" и "Не участвовать"
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
            return  # Прекращаем выполнение, так как данные не изменились

        # Если есть свободные места, добавляем в участники
        if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
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

                # Отправляем сообщение в чат с упоминанием пользователей
                await context.bot.send_message(
                    chat_id=event["chat_id"],
                    text=f"👋 {user_name} больше не участвует в мероприятии.\n"
                         f"🎉 {new_participant['user_name']} был(а) перемещён(а) из резерва в список участников!",
                )

                await query.answer(
                    f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся. "
                    f"{new_participant['user_name']} перемещён(а) из резерва в участники."
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
            return  # Прекращаем выполнение, так как данные не изменились

        # Если пользователя нет ни в одном из списков
        else:
            # Добавляем пользователя в список "Отказавшиеся"
            add_to_declined(db_path, event_id, user_id, user_name)
            await query.answer(f"{user_name}, вы добавлены в список отказавшихся.")

    # Редактируем сообщение только если данные изменились
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    await send_event_message(event_id, context, chat_id, message_id)

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.logger.logger import logger


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Восстанавливаем исходное сообщение
    original_message_id = context.user_data.get("bot_message_id")
    original_text = context.user_data.get("original_text")
    original_reply_markup = context.user_data.get("original_reply_markup")

    if original_message_id and original_text:
        try:
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=original_message_id,
                text=original_text,
                reply_markup=original_reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при восстановлении сообщения: {e}")
            await query.edit_message_text("Операция отменена.")
    else:
        await query.edit_message_text("Операция отменена.")

    context.user_data.clear()  # Очищаем user_data
    return ConversationHandler.END


# Отмена создания мероприятия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание мероприятия отменено.")
    return ConversationHandler.END

# Состояния для ConversationHandler
SET_DESCRIPTION, SET_DATE, SET_TIME, SET_LIMIT = range(4)
EDIT_EVENT, DELETE_EVENT = range(5, 7)
EDIT_DESCRIPTION, EDIT_DATE, EDIT_TIME, EDIT_LIMIT = range(10, 14)
BUTTON_HANDLER = 15