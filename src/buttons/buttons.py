from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from src.database.db_draft_operations import (
    add_draft,
    get_active_draft,
    delete_draft
)
from src.database.db_operations import get_event, get_events_by_participant, delete_event, delete_scheduled_job
from src.handlers.conversation_handler_states import (
    SET_DESCRIPTION,
    SET_DATE,
    SET_TIME,
    SET_LIMIT,
    EDIT_EVENT
)
from src.logger.logger import logger


async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатия кнопки 'Создать мероприятие'.
    Инициирует процесс создания мероприятия, проверяя наличие активного черновика.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    try:
        # Проверяем наличие активного черновика для этого пользователя в этом чате
        active_draft = get_active_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id
        )

        if active_draft:
            # Если есть активный черновик, продолжаем с того места, где остановились
            context.user_data.update({
                "draft_id": active_draft["id"],
                "bot_message_id": message_id
            })

            # Определяем текущий статус черновика и возвращаем соответствующее состояние
            if active_draft["status"] == "AWAIT_DESCRIPTION":
                await query.edit_message_text(
                    "Введите описание мероприятия:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                    ])
                )
                return SET_DESCRIPTION

            elif active_draft["status"] == "AWAIT_DATE":
                await query.edit_message_text(
                    f"📢 {active_draft['description']}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                    ])
                )
                return SET_DATE

            elif active_draft["status"] == "AWAIT_TIME":
                await query.edit_message_text(
                    f"📢 {active_draft['description']}\n\n📅 Дата: {active_draft['date']}\n\nВведите время мероприятия в формате ЧЧ:ММ",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                    ])
                )
                return SET_TIME

            elif active_draft["status"] == "AWAIT_LIMIT":
                await query.edit_message_text(
                    f"📢 {active_draft['description']}\n\n📅 Дата: {active_draft['date']}\n\n🕒 Время: {active_draft['time']}\n\nВведите количество участников (0 - неограниченное):",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
                    ])
                )
                return SET_LIMIT

        # Если активного черновика нет, создаем новый
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=user_id,
            chat_id=chat_id,
            status="AWAIT_DESCRIPTION",
            bot_message_id=message_id
        )

        if not draft_id:
            await query.edit_message_text("Ошибка при создании черновика мероприятия.")
            return ConversationHandler.END

        # Сохраняем данные черновика в context.user_data
        context.user_data.update({
            "draft_id": draft_id,
            "bot_message_id": message_id
        })

        # Редактируем сообщение с запросом описания
        await query.edit_message_text(
            "Введите описание мероприятия:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]
            ])
        )

        return SET_DESCRIPTION

    except Exception as e:
        logger.error(f"Ошибка в create_event_button: {e}")
        await query.edit_message_text("Произошла ошибка. Пожалуйста, попробуйте снова.")
        return ConversationHandler.END


async def edit_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатия кнопки 'Редактировать'.
    Показывает меню выбора параметров для редактирования.
    """
    query = update.callback_query
    await query.answer()

    try:
        # Получаем ID мероприятия из callback_data
        _, event_id = query.data.split("|")
        event_id = int(event_id)

        # Получаем данные о мероприятии
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await query.answer("Мероприятие не найдено.", show_alert=True)
            return ConversationHandler.END

        # Проверяем, является ли пользователь автором мероприятия
        if event["creator_id"] != query.from_user.id:
            await query.answer("Только автор может редактировать мероприятие.", show_alert=True)
            return ConversationHandler.END

        # Сохраняем данные в context.user_data
        context.user_data.update({
            "event_id": event_id,
            "original_text": query.message.text,
            "original_reply_markup": query.message.reply_markup,
            "bot_message_id": query.message.message_id
        })

        # Создаем клавиатуру для выбора параметра редактирования
        keyboard = [
            [
                InlineKeyboardButton("📝 Описание", callback_data=f"edit_description|{event_id}"),
                InlineKeyboardButton("👥 Лимит", callback_data=f"edit_limit|{event_id}")
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

        # Редактируем сообщение с меню редактирования
        await query.edit_message_text(
            "Что вы хотите изменить?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return EDIT_EVENT

    except Exception as e:
        logger.error(f"Ошибка в edit_event_button: {e}")
        await query.edit_message_text("Произошла ошибка. Пожалуйста, попробуйте снова.")
        return ConversationHandler.END


async def my_events_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик нажатия кнопки 'Мои мероприятия'.
    Показывает список мероприятий, в которых участвует пользователь.
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    db_path = context.bot_data["db_path"]

    try:
        # Получаем список мероприятий пользователя
        events = get_events_by_participant(db_path, user_id)

        if not events:
            await query.edit_message_text("Вы не участвуете ни в одном мероприятии.")
            return ConversationHandler.END

        # Формируем текст сообщения
        message_text = "📋 Ваши мероприятия:\n\n"
        for event in events:
            # Формируем ссылку на сообщение мероприятия
            chat_id = event["chat_id"]
            if str(chat_id).startswith("-100"):  # Для супергрупп
                chat_id_link = int(str(chat_id)[4:])
            else:
                chat_id_link = chat_id

            event_link = f"https://t.me/c/{chat_id_link}/{event['message_id']}"
            message_text += f"📅 <a href='{event_link}'>{event['description']}</a> ({event['date']} {event['time']})\n"

        # Пытаемся отправить сообщение в личку
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await query.edit_message_text("Список ваших мероприятий отправлен в личные сообщения.")
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение: {e}")
            await query.edit_message_text("Не удалось отправить список. Пожалуйста, начните чат с ботом.")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка в my_events_button: {e}")
        await query.edit_message_text("Произошла ошибка при получении списка мероприятий.")
        return ConversationHandler.END


async def handle_delete_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик удаления мероприятия (вызывается из edit_event_button)
    """
    query = update.callback_query
    await query.answer()

    try:
        # Получаем ID мероприятия
        _, event_id = query.data.split("|")
        event_id = int(event_id)

        # Получаем данные о мероприятии
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await query.answer("Мероприятие не найдено.", show_alert=True)
            return ConversationHandler.END

        # Проверяем права пользователя
        if event["creator_id"] != query.from_user.id:
            await query.answer("Только автор может удалить мероприятие.", show_alert=True)
            return ConversationHandler.END

        # Удаляем мероприятие из базы данных
        delete_event(context.bot_data["db_path"], event_id)

        # Пытаемся открепить сообщение
        try:
            await context.bot.unpin_chat_message(
                chat_id=query.message.chat_id,
                message_id=event["message_id"]
            )
        except BadRequest as e:
            logger.warning(f"Не удалось открепить сообщение: {e}")

        # Удаляем запланированные уведомления
        delete_scheduled_job(context.bot_data["db_path"], event_id)

        # Редактируем сообщение с подтверждением удаления
        await query.edit_message_text("Мероприятие успешно удалено.")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Ошибка при удалении мероприятия: {e}")
        await query.edit_message_text("Произошла ошибка при удалении мероприятия.")
        return ConversationHandler.END