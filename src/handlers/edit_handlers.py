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
    """Сохранение изменённого поля с полной проверкой"""
    try:
        user_id = update.message.from_user.id
        drafts_db = context.bot_data["drafts_db_path"]
        main_db = context.bot_data["db_path"]

        # Получаем активный черновик
        draft = get_user_draft(drafts_db, user_id)
        if not draft:
            await update.message.reply_text("🚫 Сессия редактирования устарела")
            return

        logger.info(f"Обработка черновика {draft['id']}, статус: {draft['status']}")

        # Определяем поле для редактирования
        field_map = {
            "EDIT_DESCRIPTION": ("description", str),
            "EDIT_DATE": ("date", "%d.%m.%Y"),
            "EDIT_TIME": ("time", "%H:%M"),
            "EDIT_LIMIT": ("participant_limit", int)
        }

        field, validation = field_map.get(draft["status"], (None, None))
        if not field:
            await update.message.reply_text("⚠ Неизвестный тип редактирования")
            return

        # Валидация и преобразование значения
        try:
            new_value = update.message.text.strip()
            if isinstance(validation, str):  # Проверка формата даты/времени
                from datetime import datetime
                datetime.strptime(new_value, validation)
            elif callable(validation):  # Преобразование типа (например, int)
                new_value = validation(new_value)
        except ValueError:
            await update.message.reply_text(f"❌ Неверный формат. Ожидается: {validation}")
            return

        # Обновляем черновик (для сохранения истории)
        if not update_draft(drafts_db, draft["id"], **{field: new_value}):
            await update.message.reply_text("⚠ Ошибка сохранения черновика")
            return

        # Обновляем основное мероприятие
        if not update_event_field(main_db, draft["event_id"], field, new_value):
            await update.message.reply_text("⚠ Ошибка обновления мероприятия")
            return

        # Для даты/времени - пересоздаем уведомления
        if field in ("date", "time"):
            event = get_event(main_db, draft["event_id"])
            if event:
                remove_scheduled_jobs(context, event["id"])
                schedule_notifications(context, event)

        # Обновляем сообщение
        try:
            await send_event_message(
                draft["event_id"],
                context,
                draft["chat_id"],
                draft["original_message_id"]
            )
        except Exception as e:
            logger.error(f"Ошибка обновления сообщения: {e}")
            # Создаем новое сообщение при ошибке
            new_msg = await send_event_message(
                draft["event_id"],
                context,
                draft["chat_id"]
            )
            update_event_field(main_db, draft["event_id"], "message_id", new_msg.message_id)

        # Удаляем черновик
        delete_draft(drafts_db, draft["id"])
        await context.bot.send_message(
            update.message.chat_id,
            "✅ Изменения сохранены",
            reply_to_message_id=draft.get("original_message_id")
        )

    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}", exc_info=True)
        await update.message.reply_text("⚠ Критическая ошибка при сохранении")

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