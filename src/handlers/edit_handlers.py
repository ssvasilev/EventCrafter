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

        # Ищем активный черновик редактирования для этого пользователя
        draft = get_user_draft(drafts_db_path, user_id)
        if not draft or not draft.get("event_id"):
            await update.message.reply_text("Нет активного редактирования.")
            return

        field_map = {
            "EDIT_DESCRIPTION": "description",
            "EDIT_DATE": "date",
            "EDIT_TIME": "time",
            "EDIT_LIMIT": "participant_limit"
        }

        field = field_map.get(draft["status"])
        if not field:
            await update.message.reply_text("Неизвестное поле для редактирования.")
            return

        new_value = update.message.text
        db_path = context.bot_data["db_path"]
        event_id = draft["event_id"]

        # Валидация ввода
        if field == "date":
            from datetime import datetime
            datetime.strptime(new_value, "%d.%m.%Y")  # Проверка формата
        elif field == "time":
            from datetime import datetime
            datetime.strptime(new_value, "%H:%M")  # Проверка формата
        elif field == "participant_limit":
            try:
                new_value = int(new_value)
                if new_value < 0:
                    raise ValueError("Лимит не может быть отрицательным")
            except ValueError:
                await update.message.reply_text("Лимит должен быть целым числом. Попробуйте снова.")
                return

        # Обновление в БД
        success = update_event_field(db_path, event_id, field, new_value)

        if success:
            # Если изменили дату или время - пересоздаём уведомления
            if field in ("date", "time"):
                event = get_event(db_path, event_id)
                remove_scheduled_jobs(context, event_id)
                schedule_notifications(context, event)

            await update.message.reply_text("✅ Изменения сохранены")
            # Обновляем сообщение о мероприятии
            await send_event_message(
                event_id,
                context,
                draft["chat_id"],
                draft["original_message_id"]
            )
        else:
            await update.message.reply_text("⚠ Ошибка сохранения")

        # Удаляем черновик после успешного сохранения
        delete_draft(drafts_db_path, draft["id"])

    except ValueError as e:
        await update.message.reply_text(f"Неверный формат: {e}. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Save edit error: {e}")
        await update.message.reply_text("⚠ Ошибка при сохранении")
        # В случае ошибки оставляем черновик для возможности повтора

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