import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, delete_draft, get_user_chat_draft, add_draft, get_draft
from src.database.db_operations import add_event, get_event, update_event_field
from src.message.send_message import send_event_message
from src.logger.logger import logger


async def start_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id, field_name):
    """Начинает редактирование поля мероприятия"""
    query = update.callback_query
    await query.answer()

    event = get_event(context.bot_data["db_path"], event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Создаем черновик для редактирования
    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=query.from_user.id,
        chat_id=query.message.chat_id,
        status=f"EDIT_{field_name}",
        event_id=event_id,
        original_message_id=query.message.message_id,
        description=event["description"],
        date=event["date"],
        time=event["time"],
        participant_limit=event["participant_limit"]
    )

    # Запрашиваем новое значение
    field_prompts = {
        "description": "Введите новое описание мероприятия:",
        "date": "Введите новую дату (ДД.ММ.ГГГГ):",
        "time": "Введите новое время (ЧЧ:ММ):",
        "limit": "Введите новый лимит участников (0 - без лимита):"
    }

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_input|{draft_id}")]]
    await query.edit_message_text(
        text=field_prompts[field_name],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает текущий шаг черновика на основе его статуса"""
    user_input = update.message.text
    chat_id = update.message.chat_id

    try:
        if draft["status"] == "AWAIT_DESCRIPTION":
            await _process_description(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_DATE":
            await _process_date(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_TIME":
            await _process_time(update, context, draft, user_input)
        elif draft["status"] == "AWAIT_LIMIT":
            await _process_limit(update, context, draft, user_input)

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода"
        )

async def _process_description(update, context, draft, description):
    """Обработка шага ввода описания"""
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=draft["id"],
        status="AWAIT_DATE",
        description=description
    )

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=draft["bot_message_id"],
        text=f"📢 {description}\n\nВведите дату в формате ДД.ММ.ГГГГ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def _process_date(update, context, draft, date_input):
    """Обработка шага ввода даты"""
    try:
        datetime.strptime(date_input, "%d.%m.%Y").date()

        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_TIME",
            date=date_input
        )

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=draft["bot_message_id"],
            text=f"📢 {draft['description']}\n\n📅 Дата: {date_input}\n\nВведите время (ЧЧ:ММ)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ"
        )

async def _process_time(update, context, draft, time_input):
    """Обработка шага ввода времени"""
    try:
        datetime.strptime(time_input, "%H:%M").time()

        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_LIMIT",
            time=time_input
        )

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=draft["bot_message_id"],
            text=f"📢 {draft['description']}\n\n"
                 f"📅 Дата: {draft['date']}\n"
                 f"🕒 Время: {time_input}\n\n"
                 f"Введите лимит участников (0 - без лимита):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except ValueError:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Неверный формат времени. Используйте ЧЧ:ММ"
        )


async def handle_draft_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода данных для черновика"""
    try:
        # Получаем черновик из user_data
        user_data = context.user_data
        if not user_data or 'current_draft_id' not in user_data:
            await update.message.reply_text("Сессия устарела. Начните заново.")
            return

        draft_id = int(user_data['current_draft_id'])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            await update.message.reply_text("Черновик не найден")
            return

        # Обработка в зависимости от статуса черновика
        if draft['status'] == 'AWAIT_DESCRIPTION':
            await _process_description(update, context, draft, update.message.text)
        elif draft['status'] == 'AWAIT_DATE':
            await _process_date(update, context, draft, update.message.text)
        elif draft['status'] == 'AWAIT_TIME':
            await _process_time(update, context, draft, update.message.text)
        elif draft['status'] == 'AWAIT_LIMIT':
            await _process_limit(update, context, draft, update.message.text)
        elif draft['status'].startswith('EDIT_'):
            field_name = draft['status'].split('_')[1].lower()
            await _process_edit_field(update, context, draft, field_name, update.message.text)
        else:
            await update.message.reply_text("Неизвестный статус черновика")
            logger.warning(f"Неизвестный статус черновика: {draft['status']}")

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except Exception as e:
        logger.error(f"Ошибка в handle_draft_message: {str(e)}")
        await update.message.reply_text("⚠️ Произошла ошибка обработки")


async def _process_limit(update: Update, context: ContextTypes.DEFAULT_TYPE, draft, limit_input: str):
    """Обработка лимита участников"""
    try:
        # Преобразуем draft в словарь независимо от исходного типа
        draft_dict = dict(draft) if hasattr(draft, '_fields') else draft

        # Валидация ввода
        try:
            limit = int(limit_input.strip())
            if limit < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введите целое число ≥ 0 (0 - без лимита)")
            return

        # Обновление базы данных
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_dict["id"],
            participant_limit=limit if limit != 0 else None,
            status="COMPLETED"
        )

        # Получаем ID сообщения бота
        bot_message_id = draft_dict.get("bot_message_id")

        # Обработка в зависимости от типа операции (создание/редактирование)
        if draft_dict.get("event_id"):
            # Редактирование существующего мероприятия
            update_event_field(
                db_path=context.bot_data["db_path"],
                event_id=draft_dict["event_id"],
                field="participant_limit",
                value=limit if limit != 0 else None
            )

            event = get_event(context.bot_data["db_path"], draft_dict["event_id"])
            if not event:
                raise Exception("Мероприятие не найдено")

            # Редактируем сообщение
            await send_event_message(
                event_id=event["id"],
                context=context,
                chat_id=draft_dict["chat_id"],
                message_id=bot_message_id
            )
        else:
            # Создание нового мероприятия
            event_id = add_event(
                db_path=context.bot_data["db_path"],
                description=draft_dict["description"],
                date=draft_dict["date"],
                time=draft_dict["time"],
                limit=limit if limit != 0 else None,
                creator_id=draft_dict["creator_id"],
                chat_id=draft_dict["chat_id"]
            )

            if event_id:
                event = get_event(context.bot_data["db_path"], event_id)
                if not event:
                    raise Exception("Не удалось создать мероприятие")

                await send_event_message(
                    event_id=event["id"],
                    context=context,
                    chat_id=draft_dict["chat_id"]
                )

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_dict["id"])

        # Удаляем сообщение с формой ввода
        if bot_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=draft_dict["chat_id"],
                    message_id=bot_message_id
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение бота: {e}")

    except Exception as e:
        logger.error(f"Ошибка в _process_limit: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка сохранения лимита")


async def _process_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: dict, field_name: str, value: str):
    """Обработка редактирования конкретного поля мероприятия"""
    try:
        # Валидация ввода в зависимости от поля
        if field_name == 'date':
            datetime.strptime(value, "%d.%m.%Y").date()  # Проверка формата
            new_value = value
        elif field_name == 'time':
            datetime.strptime(value, "%H:%M").time()  # Проверка формата
            new_value = value
        elif field_name == 'limit':
            try:
                new_value = int(value.strip())
                if new_value < 0:
                    raise ValueError
                new_value = new_value if new_value != 0 else None
            except ValueError:
                await update.message.reply_text("❌ Введите целое число ≥ 0 (0 - без лимита)")
                return
        else:  # description и другие текстовые поля
            new_value = value

        # Обновляем поле в черновике
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            **{field_name: new_value},
            status="COMPLETED"
        )

        # Обновляем поле в основном мероприятии
        update_event_field(
            db_path=context.bot_data["db_path"],
            event_id=draft["event_id"],
            field=field_name,
            value=new_value
        )

        # Восстанавливаем оригинальное сообщение
        await send_event_message(
            event_id=draft["event_id"],
            context=context,
            chat_id=draft["chat_id"],
            message_id=draft["original_message_id"]
        )

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    except ValueError as e:
        error_messages = {
            'date': "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ",
            'time': "❌ Неверный формат времени. Используйте ЧЧ:ММ"
        }
        await update.message.reply_text(error_messages.get(field_name, "❌ Неверный формат данных"))
    except Exception as e:
        logger.error(f"Ошибка при редактировании поля {field_name}: {str(e)}")
        await update.message.reply_text("⚠️ Ошибка при обновлении данных")