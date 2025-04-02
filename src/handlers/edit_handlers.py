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
    query = update.callback_query
    await query.answer()

    try:
        action, event_id = query.data.split("|")
        field_map = {
            "edit_date": ("дату (ДД.ММ.ГГГГ)", "date", "AWAIT_DATE"),
            "edit_time": ("время (ЧЧ:ММ)", "time", "AWAIT_TIME")
        }

        if action not in field_map:
            return

        field_name, field_db, status = field_map[action]

        # Создаем черновик
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status=status,
            event_id=event_id,
            original_message_id=query.message.message_id
        )

        # Отправляем пример правильного формата
        example = "15.07.2025" if action == "edit_date" else "14:30"
        text = f"Введите новое {field_name}:\nПример: <code>{example}</code>"

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена",
                callback_data=f"cancel_edit|{draft_id}")
            ]]),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Field selection error: {e}")
        await query.answer("Ошибка выбора поля")


async def save_edited_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Улучшенный обработчик с полной валидацией"""
    try:
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
        msg_text = update.message.text.strip()
        drafts_db = context.bot_data["drafts_db_path"]
        main_db = context.bot_data["db_path"]

        # Получаем черновик
        draft = get_user_draft(drafts_db, user_id)
        if not draft:
            logger.error("No active draft found")
            return

        # Удаляем сообщение пользователя (не критично)
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")

        # Обработка разных типов полей
        if draft["status"] == "AWAIT_DATE":
            try:
                day, month, year = map(int, msg_text.split('.'))
                if not (1 <= day <= 31 and 1 <= month <= 12 and year >= 2023):
                    raise ValueError
                new_value = f"{day:02d}.{month:02d}.{year}"
            except (ValueError, AttributeError):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 15.07.2025)"
                )
                return

        elif draft["status"] == "AWAIT_TIME":
            try:
                hours, minutes = map(int, msg_text.split(':'))
                if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                    raise ValueError
                new_value = f"{hours:02d}:{minutes:02d}"
            except (ValueError, AttributeError):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Неверный формат времени. Используйте ЧЧ:ММ (например: 14:30)"
                )
                return

        # Обновляем БД и сообщения
        field = {"AWAIT_DATE": "date", "AWAIT_TIME": "time"}[draft["status"]]
        if update_event_field(main_db, draft["event_id"], field, new_value):
            try:
                await send_event_message(
                    draft["event_id"],
                    context,
                    draft["chat_id"],
                    draft.get("original_message_id")
                )
                delete_draft(drafts_db, draft["id"])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ Изменения сохранены",
                    reply_to_message_id=draft.get("original_message_id")
                )
            except Exception as e:
                logger.error(f"Error updating message: {e}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠ Сохранено в БД, но не удалось обновить сообщение"
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠ Ошибка сохранения в базе данных"
            )

    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠ Произошла непредвиденная ошибка"
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