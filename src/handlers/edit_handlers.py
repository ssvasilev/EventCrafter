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
    """Исправленный обработчик с полной обработкой ошибок"""
    try:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
        msg_id = update.message.message_id
        drafts_db = context.bot_data["drafts_db_path"]
        main_db = context.bot_data["db_path"]

        # Получаем черновик как словарь
        draft = get_user_draft(drafts_db, user_id)
        if not draft:
            logger.error("No active draft found")
            return

        draft = dict(draft)  # Дополнительное преобразование на случай если get_user_draft вернул Row

        if not draft.get("event_id"):
            logger.error("Draft missing event_id")
            return

        # Удаление сообщения пользователя (не критично если не получится)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        # Определяем поле для редактирования
        field_config = {
            "AWAIT_DESCRIPTION": {"field": "description", "type": str},
            "AWAIT_DATE": {"field": "date", "format": "%d.%m.%Y"},
            "AWAIT_TIME": {"field": "time", "format": "%H:%M"},
            "AWAIT_LIMIT": {"field": "participant_limit", "type": int}
        }.get(draft["status"])

        if not field_config:
            await context.bot.send_message(chat_id, "⚠ Unknown edit type")
            return

        # Валидация ввода
        try:
            new_value = update.message.text.strip()
            if "format" in field_config:
                from datetime import datetime
                datetime.strptime(new_value, field_config["format"])
            elif "type" in field_config:
                new_value = field_config["type"](new_value)
        except ValueError:
            await context.bot.send_message(chat_id, "❌ Invalid format")
            return

        # Обновляем основную БД
        if not update_event_field(main_db, draft["event_id"], field_config["field"], new_value):
            await context.bot.send_message(chat_id, "⚠ Database update failed")
            return

        # Обновляем сообщение (с резервным созданием нового)
        try:
            await send_event_message(
                draft["event_id"],
                context,
                draft["chat_id"],
                draft.get("original_message_id")
            )
        except Exception as e:
            logger.error(f"Message update failed: {e}")
            try:
                new_msg = await send_event_message(
                    draft["event_id"],
                    context,
                    draft["chat_id"]
                )
                update_event_field(main_db, draft["event_id"], "message_id", new_msg.message_id)
            except Exception as e:
                logger.error(f"Fallback message creation failed: {e}")

        # Удаляем черновик
        delete_draft(drafts_db, draft["id"])

        await context.bot.send_message(
            chat_id,
            "✅ Changes saved",
            reply_to_message_id=draft.get("original_message_id")
        )

    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id,
            "⚠ An error occurred"
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