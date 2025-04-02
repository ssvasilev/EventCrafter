from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler

from config import tz
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
            "edit_desc": ("описание", "description", "AWAIT_DESCRIPTION"),
            "edit_date": ("дату (ДД.ММ.ГГГГ)", "date", "AWAIT_DATE"),
            "edit_time": ("время (ЧЧ:ММ)", "time", "AWAIT_TIME"),
            "edit_limit": ("лимит участников", "participant_limit", "AWAIT_LIMIT")
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
    """Исправленный обработчик сохранения изменений"""
    try:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
        drafts_db = context.bot_data["drafts_db_path"]
        main_db = context.bot_data["db_path"]
        tz = context.bot_data.get("tz")

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Получаем активный черновик
        draft = get_user_draft(drafts_db, user_id)
        if not draft or not draft.get("event_id"):
            logger.error("Черновик не найден или отсутствует event_id")
            await context.bot.send_message(chat_id, "🚫 Активная сессия редактирования не найдена")
            return

        # Определяем поле для редактирования
        field_config = {
            "AWAIT_DESCRIPTION": {"field": "description", "type": str, "error_msg": "текстовое описание"},
            "AWAIT_DATE": {"field": "date", "format": "%d.%m.%Y", "error_msg": "дата в формате ДД.ММ.ГГГГ"},
            "AWAIT_TIME": {"field": "time", "format": "%H:%M", "error_msg": "время в формате ЧЧ:ММ"},
            "AWAIT_LIMIT": {"field": "participant_limit", "type": int, "error_msg": "число (например: 10)"}
        }.get(draft["status"])

        if not field_config:
            logger.error(f"Неизвестный статус черновика: {draft['status']}")
            await context.bot.send_message(chat_id, "⚠ Ошибка: неизвестный тип редактирования")
            return

        # Валидация и преобразование значения
        try:
            new_value = update.message.text.strip()
            if "format" in field_config:
                from datetime import datetime
                datetime.strptime(new_value, field_config["format"])
            elif "type" in field_config:
                new_value = field_config["type"](new_value)
                if field_config["field"] == "participant_limit" and new_value < 0:
                    raise ValueError("Лимит не может быть отрицательным")
        except ValueError as e:
            logger.warning(f"Неверный формат данных: {e}")
            await context.bot.send_message(
                chat_id,
                f"❌ Неверный формат. Введите {field_config['error_msg']}"
            )
            return

        # Обновляем основную БД
        if not update_event_field(main_db, draft["event_id"], field_config["field"], new_value):
            logger.error("Ошибка обновления в основной БД")
            await context.bot.send_message(chat_id, "⚠ Ошибка сохранения в базе данных")
            return

        # Для даты/времени - пересоздаем уведомления
        if field_config["field"] in ("date", "time"):
            event = get_event(main_db, draft["event_id"])
            if event:
                try:
                    event_datetime = datetime.strptime(
                        f"{event['date']} {event['time']}",
                        "%d.%m.%Y %H:%M"
                    ).replace(tzinfo=tz)
                    remove_scheduled_jobs(context, event["id"])
                    schedule_notifications(
                        event["id"],
                        context,
                        event_datetime,
                        draft["chat_id"]
                    )
                except Exception as e:
                    logger.error(f"Ошибка планирования уведомлений: {e}")

        # Обновляем сообщение мероприятия
        try:
            await send_event_message(
                draft["event_id"],
                context,
                draft["chat_id"],
                draft["original_message_id"]
            )
        except Exception as e:
            logger.error(f"Ошибка обновления сообщения: {e}")
            try:
                new_msg = await send_event_message(
                    draft["event_id"],
                    context,
                    draft["chat_id"]
                )
                update_event_field(main_db, draft["event_id"], "message_id", new_msg.message_id)
            except Exception as fallback_e:
                logger.error(f"Не удалось создать новое сообщение: {fallback_e}")

        # Удаляем черновик
        delete_draft(drafts_db, draft["id"])

        # Отправляем подтверждение
        await context.bot.send_message(
            chat_id,
            "✅ Изменения успешно сохранены",
            reply_to_message_id=draft.get("original_message_id")
        )

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        await context.bot.send_message(
            chat_id,
            "⚠ Произошла непредвиденная ошибка при сохранении"
        )

def register_edit_handlers(application):
    """Регистрация обработчиков с приоритетами"""
    # Высокий приоритет - обработчик кнопки редактирования
    application.add_handler(CallbackQueryHandler(
        handle_edit_button,
        pattern=r"^edit\|",
        block=False
    ), group=1)

    # Средний приоритет - обработчики выбора полей
    application.add_handler(CallbackQueryHandler(
        handle_field_selection,
        pattern=r"^edit_(desc|date|time|limit)\|",
        block=False
    ), group=2)

    # Низкий приоритет - обработчик ввода данных
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        save_edited_field,
        block=False
    ), group=3)