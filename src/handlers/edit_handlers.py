from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from src.database.db_operations import get_event, update_event_field
from src.database.db_draft_operations import add_draft, update_draft, delete_draft, get_draft
from src.logger import logger
from src.message.send_message import send_event_message
from src.jobs.notification_jobs import remove_existing_notification_jobs, schedule_notifications, \
    schedule_unpin_and_delete
from datetime import datetime


async def handle_edit_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки редактирования"""
    query = update.callback_query
    await query.answer()

    try:
        event_id = int(query.data.split("|")[1])  # Получаем ID мероприятия
        user_data = context.user_data

        # Создаем черновик
        draft_id = add_draft(
            context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status="EDIT_MODE",
            event_id=event_id
        )

        # Сохраняем ID черновика в user_data
        user_data['current_draft_id'] = draft_id

        # Показываем меню редактирования
        await show_edit_menu(query, event_id)

    except Exception as e:
        logger.error(f"Ошибка в handle_edit_button: {str(e)}")
        await query.edit_message_text("⚠️ Ошибка редактирования")


async def show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id: int):
    """Показывает меню редактирования"""
    query = update.callback_query

    keyboard = [
        [
            InlineKeyboardButton("📝 Описание", callback_data=f"edit_desc|{event_id}"),
            InlineKeyboardButton("👥 Лимит", callback_data=f"edit_limit|{event_id}")
        ],
        [
            InlineKeyboardButton("📅 Дата", callback_data=f"edit_date|{event_id}"),
            InlineKeyboardButton("🕒 Время", callback_data=f"edit_time|{event_id}")
        ],
        [InlineKeyboardButton("◀ Назад", callback_data=f"cancel_edit|{event_id}")]
    ]

    await query.edit_message_text(
        "Выберите параметр для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора поля для редактирования"""
    query = update.callback_query
    await query.answer()

    try:
        action, event_id = query.data.split("|")
        db_path = context.bot_data["db_path"]
        drafts_db_path = context.bot_data["drafts_db_path"]
        draft_id = context.user_data.get("edit_draft_id")

        if not draft_id:
            await query.answer("Сессия редактирования устарела. Начните заново.", show_alert=True)
            return

        field_map = {
            "edit_desc": ("описание", "description", "AWAIT_DESCRIPTION"),
            "edit_date": ("дату (ДД.ММ.ГГГГ)", "date", "AWAIT_DATE"),
            "edit_time": ("время (ЧЧ:ММ)", "time", "AWAIT_TIME"),
            "edit_limit": ("лимит участников (число или 0 для без лимита)", "participant_limit", "AWAIT_LIMIT")
        }

        if action not in field_map:
            return

        field_name, field_key, status = field_map[action]

        # Обновляем статус черновика
        update_draft(
            db_path=drafts_db_path,
            draft_id=draft_id,
            status=status
        )

        # Сохраняем поле для редактирования в user_data
        context.user_data["edit_field"] = field_key

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_input|{draft_id}")]]
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
        user_data = context.user_data
        drafts_db_path = context.bot_data["drafts_db_path"]
        db_path = context.bot_data["db_path"]

        draft_id = user_data.get("edit_draft_id")
        if not draft_id:
            return

        draft = get_draft(drafts_db_path, draft_id)
        if not draft:
            await update.message.reply_text("Сессия редактирования устарела. Начните заново.")
            return

        field = user_data.get("edit_field")
        new_value = update.message.text
        event_id = draft["event_id"]

        # Валидация ввода
        if field == "date":
            try:
                datetime.strptime(new_value, "%d.%m.%Y")  # Проверка формата
            except ValueError:
                await update.message.reply_text("Неверный формат даты. Используйте ДД.ММ.ГГГГ")
                return
        elif field == "time":
            try:
                datetime.strptime(new_value, "%H:%M")  # Проверка формата времени
            except ValueError:
                await update.message.reply_text("Неверный формат времени. Используйте ЧЧ:ММ")
                return
        elif field == "participant_limit":
            try:
                new_value = int(new_value)
                if new_value < 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Лимит должен быть положительным числом или 0")
                return

        # Обновляем поле в черновике
        update_draft(
            db_path=drafts_db_path,
            draft_id=draft_id,
            **{field: new_value}
        )

        # Обновляем поле в основном мероприятии
        success = update_event_field(
            db_path,
            event_id,
            field,
            new_value
        )

        if not success:
            await update.message.reply_text("⚠ Ошибка сохранения изменений")
            return

        # Если изменились дата или время, обновляем уведомления
        if field in ("date", "time"):
            event = get_event(db_path, event_id)
            try:
                event_datetime = datetime.strptime(
                    f"{event['date']} {event['time']}",
                    "%d.%m.%Y %H:%M"
                )
                # Удаляем старые уведомления
                remove_existing_notification_jobs(event_id, context)
                # Создаем новые уведомления
                await schedule_notifications(event_id, context, event_datetime, draft["chat_id"])
                # Обновляем задачу удаления
                await schedule_unpin_and_delete(event_id, context, draft["chat_id"])
            except Exception as e:
                logger.error(f"Error updating notifications: {e}")

        # Удаляем сообщение с вводом пользователя
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
        except Exception as e:
            logger.warning(f"Could not delete user message: {e}")

        # Обновляем сообщение с мероприятием
        await send_event_message(
            event_id,
            context,
            draft["chat_id"],
            draft["original_message_id"]
        )

        # Возвращаем меню редактирования
        await show_edit_menu(update, context, event_id)

    except Exception as e:
        logger.error(f"Save edit error: {e}")
        await update.message.reply_text("⚠ Ошибка при сохранении")


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена редактирования"""
    query = update.callback_query
    await query.answer()

    try:
        _, event_id = query.data.split("|")
        drafts_db_path = context.bot_data["drafts_db_path"]
        draft_id = context.user_data.get("edit_draft_id")

        if draft_id:
            # Удаляем черновик
            delete_draft(drafts_db_path, draft_id)
            context.user_data.pop("edit_draft_id", None)
            context.user_data.pop("edit_field", None)

        # Возвращаем оригинальное сообщение
        await send_event_message(
            event_id,
            context,
            query.message.chat_id,
            query.message.message_id
        )

    except Exception as e:
        logger.error(f"Cancel edit error: {e}")
        await query.answer("Ошибка при отмене")


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

    # Обработчик отмены редактирования
    application.add_handler(CallbackQueryHandler(
        cancel_edit,
        pattern=r"^cancel_edit\|"
    ))

    # Обработчик сохранения изменений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        save_edited_field
    ))