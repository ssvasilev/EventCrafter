from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from src.database.db_operations import get_event, update_event_field
from src.database.db_draft_operations import add_draft, get_draft, update_draft, delete_draft, get_user_draft, \
    get_draft_by_event_id
import logging
from src.message.send_message import send_event_message
from src.jobs.notification_jobs import schedule_notifications, remove_scheduled_jobs

logger = logging.getLogger(__name__)

async def handle_edit_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Редактировать'"""
    query = update.callback_query
    await query.answer()

    try:
        _, event_id = query.data.split("|")
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)

        if not event:
            await query.answer("Мероприятие не найдено.", show_alert=True)
            return

        if event["creator_id"] != query.from_user.id:
            await query.answer("Только автор может редактировать.", show_alert=True)
            return

        # Проверяем, есть ли уже черновик для этого мероприятия
        draft = get_draft_by_event_id(context.bot_data["drafts_db_path"], event_id)
        if draft:
            await query.answer("Редактирование уже начато.", show_alert=True)
            return

        # Клавиатура выбора поля
        keyboard = [
            [
                InlineKeyboardButton("📝 Описание", callback_data=f"edit_desc|{event_id}"),
                InlineKeyboardButton("👥 Лимит", callback_data=f"edit_limit|{event_id}")
            ],
            [
                InlineKeyboardButton("📅 Дата", callback_data=f"edit_date|{event_id}"),
                InlineKeyboardButton("🕒 Время", callback_data=f"edit_time|{event_id}")
            ],
            [InlineKeyboardButton("◀ Назад", callback_data=f"event|{event_id}")]
        ]

        await query.edit_message_text(
            "Что редактируем?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Edit button error: {e}")
        await query.answer("Ошибка редактирования")

async def handle_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора поля для редактирования"""
    query = update.callback_query
    await query.answer()

    try:
        action, event_id = query.data.split("|")
        field_map = {
            "edit_desc": ("описание", "description", "EDIT_DESCRIPTION"),
            "edit_date": ("дату (ДД.ММ.ГГГГ)", "date", "EDIT_DATE"),
            "edit_time": ("время (ЧЧ:ММ)", "time", "EDIT_TIME"),
            "edit_limit": ("лимит участников", "participant_limit", "EDIT_LIMIT")
        }

        if action not in field_map:
            return

        field_name, field_db, status = field_map[action]

        # Создаем черновик для редактирования
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status=status,
            event_id=event_id,
            original_message_id=query.message.message_id
        )

        if not draft_id:
            raise Exception("Не удалось создать черновик для редактирования")

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_edit|{draft_id}")]]
        await query.edit_message_text(
            f"Введите новое {field_name}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Field selection error: {e}")
        await query.answer("Ошибка выбора поля")


async def save_edited_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение изменённого поля"""
    try:
        user_id = update.message.from_user.id
        drafts_db_path = context.bot_data["drafts_db_path"]
        db_path = context.bot_data["db_path"]

        logger.info(f"Начало обработки редактирования от пользователя {user_id}")

        # Ищем активный черновик
        draft = get_user_draft(drafts_db_path, user_id)
        logger.info(f"Найден черновик: {draft}")

        if not draft or not draft.get("event_id"):
            logger.warning("Черновик не найден или отсутствует event_id")
            await update.message.reply_text("Нет активного редактирования.")
            return

        # Логируем перед удалением сообщения
        logger.info(f"Попытка удалить сообщение ID {update.message.message_id} в чате {update.message.chat_id}")
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
            logger.info("Сообщение успешно удалено")
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")

        field_map = {
            "EDIT_DESCRIPTION": "description",
            "EDIT_DATE": "date",
            "EDIT_TIME": "time",
            "EDIT_LIMIT": "participant_limit"
        }

        field = field_map.get(draft["status"])
        logger.info(f"Редактируем поле: {field}, статус черновика: {draft['status']}")

        if not field:
            logger.error("Неизвестный тип поля для редактирования")
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text="⚠ Ошибка: неизвестное поле"
            )
            return

        new_value = update.message.text
        event_id = draft["event_id"]

        logger.info(f"Обновляем {field} на '{new_value}' для события {event_id}")

        # Обновляем в БД
        success = update_event_field(db_path, event_id, field, new_value)
        logger.info(f"Результат обновления в БД: {success}")

        if success:
            if field in ("date", "time"):
                logger.info("Обновление даты/времени - пересоздаём уведомления")
                event = get_event(db_path, event_id)
                remove_scheduled_jobs(context, event_id)
                schedule_notifications(context, event)

            logger.info(
                f"Обновляем сообщение мероприятия: chat_id={draft['chat_id']}, message_id={draft['original_message_id']}")
            await send_event_message(
                event_id,
                context,
                draft["chat_id"],
                draft["original_message_id"]
            )

            logger.info("Удаляем черновик")
            delete_draft(drafts_db_path, draft["id"])

            logger.info("Редактирование завершено успешно")
        else:
            logger.error("Ошибка обновления в БД")
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text="⚠ Ошибка сохранения изменений"
            )

    except Exception as e:
        logger.error(f"Критическая ошибка в save_edited_field: {str(e)}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠ Произошла ошибка при сохранении"
        )

def register_edit_handlers(application):
    """Регистрация всех обработчиков редактирования"""
    # Обработчик кнопки "Редактировать"
    application.add_handler(CallbackQueryHandler(
        handle_edit_button,
        pattern=r"^edit\|"
    ))

    # Обработчики выбора полей
    application.add_handler(CallbackQueryHandler(
        handle_field_selection,
        pattern=r"^edit_(desc|date|time|limit)\|"
    ))

    # Обработчик сохранения изменений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        save_edited_field
    ))