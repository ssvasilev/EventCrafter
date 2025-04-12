import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

from config import tz
from src.database.db_draft_operations import update_draft, delete_draft, get_user_chat_draft, add_draft, get_draft
from src.database.db_operations import add_event, get_event
from src.jobs.notification_jobs import schedule_notifications, schedule_unpin_and_delete, \
    remove_existing_notification_jobs, remove_existing_job
from src.message.send_message import send_event_message
from src.logger.logger import logger


async def start_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE, event_id, field_name):
    """Начинает редактирование поля мероприятия с обработкой ошибок"""
    query = update.callback_query

    try:
        await query.answer()  # Обязательно отвечаем на callback_query

        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await _show_input_error(
                update, context,
                "❌ Мероприятие не найдено"
            )
            return

        # Проверяем авторство
        if query.from_user.id != event["creator_id"]:
            await _show_input_error(
                update, context,
                "❌ Только автор может редактировать мероприятие"
            )
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
            participant_limit=event["participant_limit"],
            is_from_template=False
        )

        # Запрашиваем новое значение
        field_prompts = {
            "description": "✏️ Введите новое описание мероприятия:",
            "date": "📅 Введите новую дату (ДД.ММ.ГГГГ):",
            "time": "🕒 Введите новое время (ЧЧ:ММ):",
            "limit": "👥 Введите новый лимит участников (0 - без лимита):"
        }

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_input|{draft_id}")]]

        try:
            await query.edit_message_text(
                text=field_prompts[field_name],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except BadRequest as e:
            logger.warning(f"Не удалось обновить сообщение: {e}")
            await _show_input_error(
                update, context,
                "⚠️ Не удалось начать редактирование"
            )

    except Exception as e:
        logger.error(f"Ошибка при начале редактирования поля {field_name}: {e}")
        await _show_input_error(
            update, context,
            "⚠️ Произошла ошибка при начале редактирования"
        )

async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает текущий шаг черновика на основе его статуса"""
    user_input = update.message.text
    chat_id = update.message.chat_id

    try:
        # Обновляем current_draft_id в user_data
        context.user_data['current_draft_id'] = draft['id']
        if draft["status"].startswith("EDIT_"):
            await process_edit_step(update, context, draft)
        else:
            if draft["status"] == "AWAIT_DESCRIPTION":
                await _process_description(update, context, draft, user_input)
            elif draft.get('is_from_template') and draft['status'] == 'AWAIT_DATE':
                await _process_date(update, context, draft, user_input)
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
    try:
        # 1. Сначала обновляем черновик
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_DATE",
            description=description
        )

        # 2. Получаем ОБНОВЛЕННЫЙ черновик из базы
        updated_draft = get_draft(context.bot_data["drafts_db_path"], draft["id"])
        if not updated_draft:
            raise ValueError("Черновик не найден после обновления")

        # 3. Проверяем наличие bot_message_id
        if not updated_draft.get("bot_message_id"):
            raise ValueError("bot_message_id отсутствует в черновике")

        # 4. Подготавливаем новое содержимое
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft['id']}")]]
        new_text = f"📢 {description}\n\nВведите дату в формате ДД.ММ.ГГГГ"

        # 5. Пытаемся отредактировать сообщение
        try:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=int(updated_draft["bot_message_id"]),  # Явное преобразование в int
                text=new_text,
                reply_markup=InlineKeyboardMarkup(keyboard))

        except (BadRequest, ValueError) as e:
            logger.error(f"Ошибка редактирования: {e}. Создаем новое сообщение")
            # Создаем новое сообщение
            new_message = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=new_text,
                reply_markup=InlineKeyboardMarkup(keyboard))

            # Обновляем bot_message_id в базе
            update_draft(
                db_path=context.bot_data["drafts_db_path"],
                draft_id=draft["id"],
                bot_message_id=new_message.message_id)

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

    except Exception as e:
        logger.error(f"Ошибка обработки описания: {e}", exc_info=True)
        await _show_input_error(update, context, "⚠️ Ошибка обработки ввода")

async def _process_date(update, context, draft, date_input):
    """Обработка шага ввода даты с учётом шаблонов"""
    try:
        # Валидация даты
        datetime.strptime(date_input, "%d.%m.%Y").date()

        # Для шаблонов - особый сценарий
        if isinstance(draft, dict) and draft.get('is_from_template'):
            # Создаем мероприятие
            event_id = add_event(
                db_path=context.bot_data["db_path"],
                description=draft['description'],
                date=date_input,
                time=draft['time'],
                limit=draft['participant_limit'],
                creator_id=update.message.from_user.id,
                chat_id=update.message.chat_id,
                message_id=None
            )

            # Отправляем сообщение
            await send_event_message(
                event_id=event_id,
                context=context,
                chat_id=update.message.chat_id,
                message_id=None
            )

            # Удаляем черновик
            delete_draft(context.bot_data["drafts_db_path"], draft['id'])
            if 'current_draft_id' in context.user_data:
                del context.user_data['current_draft_id']

            # Удаляем сообщение пользователя
            try:
                await update.message.delete()
            except BadRequest:
                pass

            return

        # Обычный сценарий (не шаблон)
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft['id'],
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
        await _show_input_error(
            update, context,
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ"
        )

async def _process_time(update, context, draft, time_input):
    """Обработка шага ввода времени с всплывающими ошибками"""
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
        await _show_input_error(
            update, context,
            "❌ Неверный формат времени. Используйте ЧЧ:ММ"
        )

async def _process_limit(update, context, draft, limit_input):
    """Обработка шага ввода лимита участников"""
    try:
        limit = int(limit_input)
        if limit < 0:
            raise ValueError("Лимит не может быть отрицательным")

        # Проверяем наличие bot_message_id в черновике
        bot_message_id = draft.get("bot_message_id")
        if not bot_message_id:
            # Если нет, создаём новое сообщение
            message = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text="Создание мероприятия..."
            )
            bot_message_id = message.message_id

        # Создаем мероприятие
        event_id = add_event(
            db_path=context.bot_data["db_path"],
            description=draft["description"],
            date=draft["date"],
            time=draft["time"],
            limit=limit if limit != 0 else None,
            creator_id=update.message.from_user.id,
            chat_id=update.message.chat_id,
            message_id=bot_message_id  # Используем существующее или новое сообщение
        )

        if not event_id:
            raise Exception("Не удалось создать мероприятие")

        # Редактируем сообщение с информацией о мероприятии
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=update.message.chat_id,
            message_id=bot_message_id
        )

        # После создания мероприятия (после add_event)
        event_datetime = datetime.strptime(f"{draft['date']} {draft['time']}", "%d.%m.%Y %H:%M")
        event_datetime = event_datetime.replace(tzinfo=tz)  # Установите часовой пояс

        # Создаем задачи уведомлений
        await schedule_notifications(
            event_id=event_id,
            context=context,
            event_datetime=event_datetime,
            chat_id=update.message.chat_id
        )

        # Создаем задачу открепления
        await schedule_unpin_and_delete(
            event_id=event_id,
            context=context,
            chat_id=update.message.chat_id
        )

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

        # Удаляем сообщение пользователя с вводом лимита
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

        # Уведомляем создателя об успешном создании мероприятия
        try:
            # Преобразуем chat_id для ссылки
            chat_id = draft["chat_id"]
            if str(chat_id).startswith("-100"):  # Для супергрупп и каналов
                chat_id_link = int(str(chat_id)[4:])  # Убираем "-100" в начале
            else:
                chat_id_link = chat_id  # Для обычных групп и личных чатов

            # Формируем ссылку на мероприятие
            message_id = draft["bot_message_id"]
            event_link = f"https://t.me/c/{chat_id_link}/{message_id}"

            # Формируем текст уведомления с кликабельным названием мероприятия
            message = (
                f"✅ Мероприятие успешно создано!\n\n"
                f"📢 <a href='{event_link}'>{draft['description']}</a>\n"
                f"📅 Дата: {draft['date']}\n"
                f"🕒 Время: {draft['time']}"
            )

            # Отправляем уведомление создателю
            await context.bot.send_message(
                chat_id=draft["creator_id"],
                text=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления создателю: {e}")

    except ValueError:
        await _show_input_error(
            update, context,
            "❌ Лимит должен быть целым числом ≥ 0 (0 - без лимита)"
        )
    except Exception as e:
        logger.error(f"Ошибка создания мероприятия: {e}")
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ Произошла ошибка при создании мероприятия",
            reply_to_message_id=draft["bot_message_id"]
        )


async def process_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает шаг редактирования с унифицированным выводом ошибок"""
    user = update.message.from_user if update.message else update.callback_query.from_user

    # Проверяем авторство
    event = get_event(context.bot_data["db_path"], draft["event_id"])
    if user.id != event["creator_id"]:
        await _show_input_error(
            update, context,
            "❌ Только автор может редактировать мероприятие"
        )
        return

    field = draft["status"].split("_")[1]  # Получаем поле из статуса
    user_input = update.message.text if update.message else None

    if field == "description":
        await _update_event_field(context, draft, "description", user_input)
    elif field == "date":
        await _validate_and_update(update, context, draft, "date", user_input, "%d.%m.%Y", "ДД.ММ.ГГГГ")
    elif field == "time":
        await _validate_and_update(update, context, draft, "time", user_input, "%H:%M", "ЧЧ:ММ")
    elif field == "limit":
        await _update_participant_limit(update, context, draft, user_input)

    # Удаляем сообщение пользователя, если это текстовый ввод
    if update.message:
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")


async def _update_event_field(context, draft, field, value):
    """Обновляет поле мероприятия"""
    from src.database.db_operations import update_event_field

    # Обновляем поле в базе данных
    update_event_field(
        db_path=context.bot_data["db_path"],
        event_id=draft["event_id"],
        field=field,
        value=value
    )

    # Если обновляется дата или время, пересоздаем задачи уведомлений
    if field in ["date", "time"]:
        # Удаляем старые задачи
        remove_existing_notification_jobs(draft["event_id"], context)
        remove_existing_job(draft["event_id"], context)  # Для задачи открепления

        # Получаем новые дату и время
        event = get_event(context.bot_data["db_path"], draft["event_id"])
        if event:
            try:
                event_datetime = datetime.strptime(
                    f"{event['date']} {event['time']}",
                    "%d.%m.%Y %H:%M"
                ).replace(tzinfo=tz)

                # Создаем новые задачи
                await schedule_notifications(
                    event_id=draft["event_id"],
                    context=context,
                    event_datetime=event_datetime,
                    chat_id=draft["chat_id"]
                )

                await schedule_unpin_and_delete(
                    event_id=draft["event_id"],
                    context=context,
                    chat_id=draft["chat_id"]
                )
            except ValueError as e:
                logger.error(f"Ошибка при обработке новой даты/времени: {e}")

    await _finalize_edit(context, draft)


async def _validate_and_update(update, context, draft, field, value, fmt, error_hint):
    """Проверяет формат и обновляет поле с унифицированным выводом ошибок"""
    try:
        datetime.strptime(value, fmt)  # Валидация формата
        await _update_event_field(context, draft, field, value)
    except ValueError:
        await _show_input_error(
            update, context,
            f"❌ Неверный формат {field}. Используйте {error_hint}"
        )


async def _update_participant_limit(update, context, draft, value):
    """Обновляет лимит участников с унифицированным выводом ошибок"""
    try:
        limit = int(value)
        if limit < 0:
            raise ValueError
        await _update_event_field(
            context, draft,
            "participant_limit",
            limit if limit != 0 else None
        )
    except ValueError:
        await _show_input_error(
            update, context,
            "❌ Лимит должен быть целым числом ≥ 0 (0 - без лимита)"
        )


async def _finalize_edit(context, draft):
    """Завершает редактирование"""
    from src.message.send_message import send_event_message

    # Обновляем сообщение мероприятия
    await send_event_message(
        event_id=draft["event_id"],
        context=context,
        chat_id=draft["chat_id"],
        message_id=draft["original_message_id"]
    )

    # Удаляем черновик
    delete_draft(context.bot_data["drafts_db_path"], draft["id"])

async def _show_input_error(update, context, error_text):
    """Универсальный метод показа ошибок ввода"""
    try:
        # Сначала показываем всплывающее окно
        if update.message:
            await context.bot.answer_callback_query(
                callback_query_id=update.message.message_id,
                text=error_text,
                show_alert=False
            )
        # Затем удаляем сообщение (если это текстовый ввод)
        if update.message:
            try:
                await update.message.delete()
            except BadRequest:
                pass
    except Exception as e:
        logger.warning(f"Не удалось показать ошибку: {e}")
        # Фолбэк: отправляем временное сообщение
        try:
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text
            )
            await asyncio.sleep(5)
            await msg.delete()
        except Exception as fallback_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {fallback_error}")
