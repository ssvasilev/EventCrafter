from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, delete_draft, get_user_chat_draft, add_draft
from src.database.db_operations import add_event, get_event
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

async def _process_limit(update, context, draft, limit_input):
    """Обработка шага ввода лимита участников с полной обработкой ошибок"""
    try:
        # 1. Проверка и преобразование лимита
        try:
            limit = int(limit_input)
            if limit < 0:
                raise ValueError("Лимит не может быть отрицательным")
        except ValueError as e:
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text="❌ Неверный формат лимита. Введите целое число (0 - без лимита)"
            )
            return

        # 2. Получаем соединение с базой данных
        db_path = context.bot_data["db_path"]
        drafts_db_path = context.bot_data["drafts_db_path"]

        # 3. Проверяем существование мероприятия
        existing_event = None
        if draft.get("event_id"):
            existing_event = get_event(db_path, draft["event_id"])
            if existing_event and hasattr(existing_event, 'get'):
                existing_event = dict(existing_event)  # Преобразуем Row в dict

        # 4. Создаем или обновляем мероприятие
        if existing_event:
            # Обновляем существующее мероприятие
            success = update_event_field(
                db_path,
                existing_event["id"],
                "participant_limit",
                limit if limit != 0 else None
            )
            event_id = existing_event["id"]
        else:
            # Создаем новое мероприятие
            event_id = add_event(
                db_path=db_path,
                description=draft["description"],
                date=draft["date"],
                time=draft["time"],
                limit=limit if limit != 0 else None,
                creator_id=update.message.from_user.id,
                chat_id=update.message.chat_id
            )

        if not event_id:
            raise Exception("Не удалось сохранить мероприятие")

        # 5. Отправляем/обновляем сообщение о мероприятии
        try:
            message_id = await send_event_message(
                event_id,
                context,
                update.message.chat_id,
                existing_event["message_id"] if existing_event else None
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения мероприятия: {e}")
            raise

        # 6. Обновляем сообщение с формой
        try:
            if draft.get("bot_message_id"):
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=draft["bot_message_id"],
                    text="✅ Мероприятие успешно сохранено!",
                    reply_markup=None
                )
        except Exception as e:
            logger.warning(f"Не удалось обновить сообщение формы: {e}")

        # 7. Удаляем сообщение пользователя с вводом лимита
        try:
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        # 8. Удаляем черновик
        delete_draft(drafts_db_path, draft["id"])

    except Exception as e:
        logger.error(f"Критическая ошибка в _process_limit: {str(e)}")
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Произошла критическая ошибка при сохранении мероприятия"
        )
