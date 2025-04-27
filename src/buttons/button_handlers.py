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
    delete_event,
    get_participants
)
from src.database.db_draft_operations import add_draft

from src.handlers.template_handlers import handle_save_template, handle_use_template, handle_delete_template, \
    handle_my_templates
from src.jobs.notification_jobs import remove_existing_notification_jobs
from src.message.send_message import send_event_message
from src.logger.logger import logger
from src.utils.private_chat import _is_private_chat


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    #await query.answer()

    try:
        if not '|' in query.data:
            # Обработка простых callback_data без разделителя
            if query.data == "close_templates":
                keyboard = [
                    [InlineKeyboardButton("📅 Создать мероприятие", callback_data="menu_create_event")],
                    [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")],
                    [InlineKeyboardButton("📁 Мои шаблоны", callback_data="menu_my_templates")]
                ]
                await query.edit_message_text(
                    "Главное меню:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            elif query.data == "noop":
                await query.answer()
                return
            return
        parts = query.data.split('|')
        action = parts[0]

        if action == 'templates_page':
            # Проверяем, что пагинацию нажимает владелец шаблонов
            if str(query.from_user.id) != str(context.user_data.get('template_owner_id')):
                await query.answer("❌ Только владелец может листать страницы", show_alert=False)
                return

            if parts[1] != 'current':
                offset = int(parts[1])
                await handle_my_templates(query, context, offset)
            return

        # Обработка callback_data с разделителем |
        parts = query.data.split('|')
        action = parts[0]

        if action == 'close_templates':
            # Проверяем, что закрывает владелец шаблонов
            if len(parts) > 1 and int(parts[1]) != query.from_user.id:
                await query.answer("❌ Только владелец шаблонов может закрыть это меню", show_alert=False)
                return

            keyboard = [
                [InlineKeyboardButton("📅 Создать мероприятие", callback_data="menu_create_event")],
                [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")],
                [InlineKeyboardButton("📁 Мои шаблоны", callback_data="menu_my_templates")]
            ]
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        elif action == 'join':
            await handle_join(query, context, int(parts[1]))
        elif action == 'leave':
            await handle_leave(query, context, int(parts[1]))
        elif action == 'edit':
            await handle_edit_event(query, context, int(parts[1]))
        elif action == 'edit_field':
            await handle_edit_field(query, context, int(parts[1]), parts[2])
        elif action == 'save_template':
            event_id = int(parts[1])
            await handle_save_template(query, context, event_id)
        elif action == 'use_template':
            template_id = int(parts[1])
            await handle_use_template(query, context, template_id)
        elif action == 'delete_template':
            template_id = int(parts[1])
            await handle_delete_template(query, context, template_id)
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
        await query.answer("Мероприятие не найдено", show_alert=False)
        return

    # Проверяем, является ли пользователь автором
    if query.from_user.id != event["creator_id"]:
        await query.answer("❌ Только автор может редактировать мероприятие", show_alert=False)
        return

    # Показываем меню редактирования только автору
    keyboard = [
        # Первая строка - редактирование основных полей
        [
            InlineKeyboardButton("📝 Описание", callback_data=f"edit_field|{event_id}|description"),
            InlineKeyboardButton("📅 Дата", callback_data=f"edit_field|{event_id}|date"),
            InlineKeyboardButton("🕒 Время", callback_data=f"edit_field|{event_id}|time"),
            InlineKeyboardButton("👥 Лимит участников", callback_data=f"edit_field|{event_id}|limit")

        ],
        # Вторая строка - лимит и действия
        [
            InlineKeyboardButton("💾 Сохранить как шаблон", callback_data=f"save_template|{event_id}")
        ],
        # Третья строка - опасные действия
        [
            InlineKeyboardButton("🗑️ Удалить мероприятие", callback_data=f"confirm_delete|{event_id}"),
            InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_edit|{event_id}")
        ]
    ]

    await query.edit_message_text(
        text="✏️ Редактирование мероприятия:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_edit_field(query, context, event_id, field):
    """Обработка выбора поля для редактирования с полной проверкой данных"""
    try:
        # Получаем полные данные о мероприятии
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            logger.error(f"Мероприятие {event_id} не найдено при редактировании")
            await query.edit_message_text("❌ Мероприятие не найдено")
            return

        # Проверяем авторство
        if query.from_user.id != event["creator_id"]:
            logger.warning(f"Попытка редактирования не автором: user={query.from_user.id}, creator={event['creator_id']}")
            await query.answer("❌ Только автор может редактировать мероприятие", show_alert=False)
            return

        # Создаем черновик с полным набором данных
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status=f"EDIT_{field}",
            event_id=event_id,
            original_message_id=query.message.message_id,
            bot_message_id=query.message.message_id,
            description=event["description"],
            date=event["date"],
            time=event["time"],
            participant_limit=event["participant_limit"],
            is_from_template=False
        )

        if not draft_id:
            logger.error("Не удалось создать черновик для редактирования")
            await query.edit_message_text("⚠️ Ошибка при создании черновика")
            return

        logger.info(f"Создан черновик редактирования ID {draft_id} для мероприятия {event_id}")

        # Подготавливаем текст запроса
        field_prompts = {
            "description": "✏️ Введите новое описание мероприятия:",
            "date": "📅 Введите новую дату (ДД.ММ.ГГГГ):",
            "time": "🕒 Введите новое время (ЧЧ:ММ):",
            "limit": "👥 Введите новый лимит участников (0 - без лимита):"
        }

        keyboard = [
            [InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_input|{draft_id}")]
        ]

        # Сохраняем draft_id в context.user_data для последующей обработки
        context.user_data['current_draft_id'] = draft_id

        try:
            await query.edit_message_text(
                text=field_prompts[field],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await query.answer()  # Важно для закрытия всплывающего окна
        except BadRequest as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            # Fallback: отправляем новое сообщение
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=field_prompts[field],
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        logger.error(f"Критическая ошибка в handle_edit_field: {e}", exc_info=True)
        try:
            await query.edit_message_text("⚠️ Произошла ошибка при начале редактирования")
        except:
            await query.answer("⚠️ Ошибка! Попробуйте ещё раз", show_alert=False)


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
                    chat_id=message.chat.id,
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
            await query.answer("Мероприятие не найдено", show_alert=False)
            return

        # Проверяем авторство
        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может удалить мероприятие", show_alert=False)
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
        await query.answer("⚠️ Произошла ошибка", show_alert=False)


async def handle_delete_event(query, context, event_id):
    """Обработчик удаления мероприятия с отправкой уведомления автору и участникам"""
    try:
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await query.answer("⚠️ Мероприятие не найдено", show_alert=False)
            return

        # Проверка авторства
        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может удалить мероприятие", show_alert=False)
            return

        # Информация об авторе
        creator = query.from_user
        creator_name = f"{creator.first_name}"
        if creator.username:
            creator_name += f" (@{creator.username})"
        else:
            creator_name += f" (ID: {creator.id})"

        # Формируем информацию о чате
        try:
            chat = await context.bot.get_chat(event["chat_id"])
            chat_name = chat.title or "Личный чат"

            # Формируем ссылку на чат (только для групп/каналов)
            if str(event["chat_id"]).startswith('-'):
                chat_link = f"https://t.me/c/{str(abs(int(event['chat_id'])))}"
            else:
                chat_link = ""
                if _is_private_chat(event["chat_id"]):
                    chat_name += " (приватный)"
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о чате: {e}")
            chat_name = "чат"
            chat_link = ""

        # Формируем ссылку на мероприятие
        event_link = ""
        if not _is_private_chat(event["chat_id"]):  # Только если не приватный чат
            try:
                if str(event["chat_id"]).startswith("-100"):
                    chat_id_for_link = str(event["chat_id"])[4:]
                    event_link = f"https://t.me/c/{chat_id_for_link}/{event['message_id']}"
                elif str(event["chat_id"]).startswith("-"):
                    chat_id_for_link = str(abs(int(event["chat_id"])))
                    event_link = f"https://t.me/c/{chat_id_for_link}/{event['message_id']}"
            except Exception as e:
                logger.warning(f"Ошибка формирования ссылки: {e}")

        # Текст уведомления для автора
        notification_text = (
            f"✅ <b>Вы успешно удалили мероприятие:</b>\n\n"
            f"📢 <b>Название:</b> {event['description']}\n"
        )
        if event.get("date"):
            notification_text += f"📅 <b>Дата:</b> {event['date']}\n"
        if event.get("time"):
            notification_text += f"🕒 <b>Время:</b> {event['time']}\n"

        # Добавляем чат с пояснением о приватности
        if chat_link:
            notification_text += f"💬 <b>Чат:</b> <a href='{chat_link}'>{chat_name}</a>\n"
        else:
            if _is_private_chat(event["chat_id"]):
                notification_text += f"💬 <b>Чат:</b> {chat_name} (приватный)\n"
            else:
                notification_text += f"💬 <b>Чат:</b> {chat_name}\n"

        # Добавляем ссылку или пояснение
        if event_link:
            notification_text += f"\n🔗 <a href='{event_link}'>Перейти к мероприятию</a>"
        elif _is_private_chat(event["chat_id"]):
            notification_text += "\n⚠️ <i>Ссылка недоступна (приватный чат)</i>"

        # Удаляем мероприятие из БД и чата
        delete_event(context.bot_data["db_path"], event_id)
        try:
            await context.bot.delete_message(chat_id=event["chat_id"], message_id=event["message_id"])
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Отправляем уведомление автору
        try:
            await context.bot.send_message(
                chat_id=creator.id,
                text=notification_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить автора: {e}")
            await query.message.reply("✅ Мероприятие удалено (не удалось отправить уведомление в ЛС)")

        # Уведомляем участников (аналогичный формат)
        participants = get_participants(context.bot_data["db_path"], event_id)
        for participant in participants:
            # Не уведомляем автора повторно
            if participant["user_id"] != creator.id:
                try:
                    participant_text = (
                        f"🚫 <b>Мероприятие отменено</b>\n\n"
                        f"📢 <b>Название:</b> {event['description']}\n"
                        f"👤 <b>Автор:</b> {creator_name}\n"
                    )
                    if chat_link:
                        participant_text += f"💬 <b>Чат:</b> <a href='{chat_link}'>{chat_name}</a>\n"
                    else:
                        if _is_private_chat(event["chat_id"]):
                            participant_text += f"💬 <b>Чат:</b> {chat_name} (приватный)\n"
                        else:
                            participant_text += f"💬 <b>Чат:</b> {chat_name}\n"

                    if event_link:
                        participant_text += f"\n🔗 <a href='{event_link}'>Перейти к мероприятию</a>"
                    else:
                        participant_text += "\n⚠️ <i>Ссылка недоступна (приватный чат)</i>"

                    await context.bot.send_message(
                        chat_id=participant["user_id"],
                        text=participant_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить участника {participant['user_id']}: {e}")

        # Удаляем сообщение с кнопкой "Удалить"
        try:
            await query.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка при удалении мероприятия: {e}")
        await query.answer("⚠️ Не удалось удалить мероприятие", show_alert=False)


async def handle_cancel_delete(query, context, event_id):
    """Обработчик отмены удаления с проверкой авторства"""
    try:
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            await query.answer("Мероприятие не найдено", show_alert=False)
            return

        # Дополнительная проверка авторства (для надежности)
        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может отменить удаление", show_alert=False)
            return

        # Возвращаем пользователя к просмотру мероприятия
        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id
        )

        # Отправляем лог о событии
        logger.info(f"Пользователь {query.from_user.id} отменил удаление мероприятия {event_id}")

    except Exception as e:
        logger.error(f"Ошибка при отмене удаления: {e}")
        await query.answer("⚠️ Не удалось отменить удаление", show_alert=False)

def register_button_handler(application):
    application.add_handler(CallbackQueryHandler(
        button_handler,
        pattern=r"^(join|leave|edit|edit_field|confirm_delete|delete_event|cancel_delete|save_template|use_template|delete_template|close_templates|templates_page)"
    ))