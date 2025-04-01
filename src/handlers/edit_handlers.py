from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from src.database.db_operations import get_event, update_event_field
from src.database.db_draft_operations import add_draft
from src.logger import logger
from src.message.send_message import send_event_message


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

        # Сохраняем данные для возврата
        context.user_data["edit_context"] = {
            "event_id": event_id,
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id
        }

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
            "edit_desc": ("описание", "description"),
            "edit_date": ("дату (ДД.ММ.ГГГГ)", "date"),
            "edit_time": ("время (ЧЧ:ММ)", "time"),
            "edit_limit": ("лимит участников", "participant_limit")
        }

        if action not in field_map:
            return

        # Сохраняем выбранное поле
        context.user_data["edit_field"] = field_map[action][1]

        # Создаем черновик (из вашего кода)
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status=f"EDIT_{field_map[action][1]}",
            event_id=event_id,
            original_message_id=query.message.message_id
        )

        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_edit|{draft_id}")]]
        await query.edit_message_text(
            f"Введите новое {field_map[action][0]}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Field selection error: {e}")
        await query.answer("Ошибка выбора поля")


async def save_edited_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение изменённого поля"""
    try:
        edit_data = context.user_data.get("edit_context")
        if not edit_data or "edit_field" not in context.user_data:
            return

        field = context.user_data["edit_field"]
        new_value = update.message.text

        # Валидация ввода
        if field == "date":
            from datetime import datetime
            datetime.strptime(new_value, "%d.%m.%Y")  # Проверка формата

        # Обновление в БД
        success = update_event_field(
            context.bot_data["db_path"],
            edit_data["event_id"],
            field,
            new_value
        )

        if success:
            await update.message.reply_text("✅ Изменения сохранены")
            # Обновляем сообщение о мероприятии
            await send_event_message(
                edit_data["event_id"],
                context,
                edit_data["chat_id"],
                edit_data["message_id"]
            )
        else:
            await update.message.reply_text("⚠ Ошибка сохранения")

        # Очищаем контекст
        context.user_data.pop("edit_context", None)
        context.user_data.pop("edit_field", None)

    except ValueError:
        await update.message.reply_text("Неверный формат. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Save edit error: {e}")
        await update.message.reply_text("⚠ Ошибка при сохранении")


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