import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.database.db_operations import (
    get_event,
    add_participant,
    remove_participant,
    add_to_declined,
    remove_from_reserve,
    remove_from_declined,
    is_user_in_participants,
    is_user_in_reserve,
    get_participants_count,
    add_to_reserve,
    get_reserve,
    is_user_in_declined,
    update_event_field, delete_event, get_participants
)
from src.database.db_draft_operations import add_draft, delete_draft, get_draft
from src.jobs.notification_jobs import remove_existing_notification_jobs
from src.message.send_message import send_event_message
from src.logger.logger import logger

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    #await query.answer()

    try:
        # Разбираем callback_data в зависимости от формата
        if '|' in query.data:
            parts = query.data.split('|')
            action = parts[0]

            if action == 'join':
                await handle_join(query, context, int(parts[1]))
            elif action == 'leave':
                await handle_leave(query, context, int(parts[1]))
            elif action == 'edit':
                await handle_edit_event(query, context, int(parts[1]))
            elif action == 'edit_field':
                await handle_edit_field(query, context, int(parts[1]), parts[2])
            elif action == 'confirm_delete':
                await handle_confirm_delete(query, context, int(parts[1]))
            elif action == 'delete_event':
                await handle_delete_event(query, context, int(parts[1]))
            elif action == 'cancel_delete':
                await handle_cancel_delete(query, context, int(parts[1]))
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при обработке запроса")


async def handle_join(query, context, event_id):
    """Обработка нажатия 'Участвовать'"""
    user = query.from_user
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        await query.answer("Мероприятие не найдено.")
        return

    user_id = user.id
    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

    if is_user_in_declined(db_path, event_id, user_id):
        remove_from_declined(db_path, event_id, user_id)

    if is_user_in_participants(db_path, event_id, user_id) or is_user_in_reserve(db_path, event_id, user_id):
        await query.answer("Вы уже в списке участников или резерва.")
        return

    if event["participant_limit"] is None or get_participants_count(db_path, event_id) < event["participant_limit"]:
        add_participant(db_path, event_id, user_id, user_name)
        await query.answer(f"{user_name}, вы добавлены в список участников!")
    else:
        add_to_reserve(db_path, event_id, user_id, user_name)
        await query.answer(f"{user_name}, вы добавлены в резерв.")

    await update_event_message(context, event_id, query.message)


async def handle_leave(query, context, event_id):
    """Обработка нажатия 'Не участвовать'"""
    user = query.from_user
    db_path = context.bot_data["db_path"]
    event = get_event(db_path, event_id)

    if not event:
        await query.answer("Мероприятие не найдено.")
        return

    user_id = user.id
    user_name = f"{user.first_name} (@{user.username})" if user.username else f"{user.first_name} (ID: {user.id})"

    if is_user_in_participants(db_path, event_id, user_id):
        remove_participant(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)

        reserve = get_reserve(db_path, event_id)
        if reserve:
            new_participant = reserve[0]
            remove_from_reserve(db_path, event_id, new_participant["user_id"])
            add_participant(db_path, event_id, new_participant["user_id"], new_participant["user_name"])

            await context.bot.send_message(
                chat_id=event["chat_id"],
                text=f"👋 {user_name} больше не участвует в мероприятии.\n"
                     f"🎉 {new_participant['user_name']} был(а) перемещён(а) из резерва в список участников!",
            )

            await query.answer(
                f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся. "
                f"{new_participant['user_name']} перемещён(а) из резерва в участники."
            )
        else:
            await query.answer(f"{user_name}, вы удалены из списка участников и добавлены в список отказавшихся.")

    elif is_user_in_reserve(db_path, event_id, user_id):
        remove_from_reserve(db_path, event_id, user_id)
        add_to_declined(db_path, event_id, user_id, user_name)
        await query.answer(f"{user_name}, вы удалены из резерва и добавлены в список отказавшихся.")

    elif is_user_in_declined(db_path, event_id, user_id):
        await query.answer("Вы уже в списке отказавшихся.")
        return

    else:
        add_to_declined(db_path, event_id, user_id, user_name)
        await query.answer(f"{user_name}, вы добавлены в список отказавшихся.")

    await update_event_message(context, event_id, query.message)

# Новая логика редактирования
async def handle_edit_event(query, context, event_id):
    """Обработка нажатия кнопки 'Редактировать'"""
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.answer("Мероприятие не найдено", show_alert=True)
        return

    # Проверяем, является ли пользователь автором
    if query.from_user.id != event["creator_id"]:
        await query.answer("❌ Только автор может редактировать мероприятие", show_alert=True)
        return

    # Показываем меню редактирования только автору
    keyboard = [
        [InlineKeyboardButton("📝 Описание", callback_data=f"edit_field|{event_id}|description")],
        [InlineKeyboardButton("📅 Дата", callback_data=f"edit_field|{event_id}|date")],
        [InlineKeyboardButton("🕒 Время", callback_data=f"edit_field|{event_id}|time")],
        [InlineKeyboardButton("👥 Лимит участников", callback_data=f"edit_field|{event_id}|limit")],
        [InlineKeyboardButton("🗑️ Удалить мероприятие", callback_data=f"confirm_delete|{event_id}")],
        [InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_edit|{event_id}")]
    ]

    await query.edit_message_text(
        text="Выберите поле для редактирования:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_edit_field(query, context, event_id, field):
    """Обработка выбора поля для редактирования"""
    event = get_event(context.bot_data["db_path"], event_id)
    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Проверяем авторство
    if query.from_user.id != event["creator_id"]:
        await query.answer("❌ Только автор может редактировать мероприятие")
        return

    # Создаем черновик с сохранением original_message_id из текущего сообщения
    draft_id = add_draft(
        db_path=context.bot_data["drafts_db_path"],
        creator_id=query.from_user.id,
        chat_id=query.message.chat_id,
        status=f"EDIT_{field}",
        event_id=event_id,
        original_message_id=query.message.message_id,  # Сохраняем ID текущего сообщения
        description=event["description"],
        date=event["date"],
        time=event["time"],
        participant_limit=event["participant_limit"]
    )

    field_prompts = {
        "description": "Введите новое описание мероприятия:",
        "date": "Введите новую дату (ДД.ММ.ГГГГ):",
        "time": "Введите новое время (ЧЧ:ММ):",
        "limit": "Введите новый лимит участников (0 - без лимита):"
    }

    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_input|{draft_id}")]]
    await query.edit_message_text(
        text=field_prompts[field],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_cancel_edit(query, context, event_id):
    """Обработка отмены редактирования"""
    event = get_event(context.bot_data["db_path"], event_id)

    if not event:
        await query.edit_message_text("Мероприятие не найдено")
        return

    # Возвращаем стандартное сообщение
    keyboard = [
        [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event_id}")],
        [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event_id}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event_id}")]
    ]

    message_text = f"📢 {event['description']}\n\nДата: {event['date']}\nВремя: {event['time']}\nЛимит: {event['participant_limit'] or '∞'}"

    await query.edit_message_text(
        text=message_text,
        reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_cancel_input(query, context, draft_id):
    """Обработка отмены ввода при редактировании"""
    try:
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if draft:
            # Редактируем текущее сообщение вместо удаления
            if draft.get("event_id"):  # Если это редактирование существующего мероприятия
                event = get_event(context.bot_data["db_path"], draft["event_id"])
                if event:
                    await send_event_message(
                        event_id=event["id"],
                        context=context,
                        chat_id=query.message.chat_id,
                        message_id=query.message.message_id  # Редактируем текущее сообщение
                    )
            else:  # Если это создание нового мероприятия
                await query.edit_message_text(
                    text="Создание мероприятия отменено",
                    reply_markup=None
                )

            delete_draft(context.bot_data["drafts_db_path"], draft_id)
    except Exception as e:
        logger.error(f"Ошибка при отмене ввода: {e}")
        await query.edit_message_text("⚠️ Не удалось отменить ввод")

async def update_event_message(context, event_id, message):
    """Обновляет сообщение о мероприятии"""
    try:
        db_path = context.bot_data["db_path"]
        event = get_event(db_path, event_id)
        if not event:
            logger.error(f"Мероприятие {event_id} не найдено")
            return

        # Используем механизм повторных попыток
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await send_event_message(
                    event_id=event_id,
                    context=context,
                    chat_id=message.chat_id,
                    message_id=event.get("message_id")
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Не удалось обновить сообщение после {max_retries} попыток: {e}")
                else:
                    logger.warning(f"Попытка {attempt + 1} не удалась, повторяем...")
                    await asyncio.sleep(1)  # Задержка между попытками
    except Exception as e:
        logger.error(f"Критическая ошибка при обновлении сообщения: {e}")


async def handle_confirm_delete(query, context, event_id):
    """Показывает подтверждение удаления с проверкой авторства"""
    try:
        event = get_event(context.bot_data["db_path"], event_id)

        if not event:
            await query.answer("Мероприятие не найдено", show_alert=True)
            return

        # Проверяем авторство
        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может удалить мероприятие", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"delete_event|{event_id}")],
            [InlineKeyboardButton("⛔ Нет, отменить", callback_data=f"cancel_delete|{event_id}")]
        ]

        await query.edit_message_text(
            text="⚠️ Вы уверены, что хотите удалить мероприятие?",
            reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка при подтверждении удаления: {e}")
        await query.answer("⚠️ Произошла ошибка", show_alert=True)


async def handle_delete_event(query, context, event_id):
    """Обработчик удаления мероприятия с двойной проверкой авторства"""
    try:
        event = get_event(context.bot_data["db_path"], event_id)

        if not event:
            await query.answer("Мероприятие не найдено", show_alert=True)
            return

        # Двойная проверка авторства (на всякий случай)
        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может удалить мероприятие", show_alert=True)
            return

        #Удаляем задачи на уведомления
        remove_existing_notification_jobs(event_id, context)

        # Удаляем мероприятие из базы данных
        delete_event(context.bot_data["db_path"], event_id)

        # Удаляем сообщение о мероприятии из чата
        try:
            await context.bot.delete_message(
                chat_id=event["chat_id"],
                message_id=event["message_id"]
            )
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Уведомляем пользователя
        await query.edit_message_text(
            text=f"✅ Мероприятие '{event['description']}' успешно удалено",
            reply_markup=None
        )

        participants = get_participants(context.bot_data["db_path"], event_id)
        for participant in participants:
            try:
                await context.bot.send_message(
                    chat_id=participant["user_id"],
                    text=f"Мероприятие '{event['description']}' было отменено"
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить участника {participant['user_id']}: {e}")

        # Логируем действие
        logger.info(f"Пользователь {query.from_user.id} удалил мероприятие {event_id}")

    except Exception as e:
        logger.error(f"Ошибка при удалении мероприятия: {e}")
        await query.answer("⚠️ Не удалось удалить мероприятие", show_alert=True)


async def handle_cancel_delete(query, context, event_id):
    """Обработчик отмены удаления мероприятия"""
    try:
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await query.answer("Мероприятие не найдено", show_alert=True)
            return

        # Возвращаем пользователя к просмотру мероприятия
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

    except Exception as e:
        logger.error(f"Ошибка при отмене удаления: {e}")
        await query.answer("⚠️ Не удалось отменить удаление", show_alert=True)

def register_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            button_handler,
            pattern=r"^(join|leave|edit|edit_field|confirm_delete|delete_event)\|"
        )
    )