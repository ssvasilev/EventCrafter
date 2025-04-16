import sqlite3
from datetime import datetime

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.database.db_draft_operations import add_draft, update_draft
from src.database.db_operations import get_event, get_user_templates
from src.logger import logger


async def handle_my_templates(query, context, offset=0, limit=5):
    """Показывает список шаблонов пользователя с пагинацией"""
    try:
        templates = get_user_templates(context.bot_data["db_path"], query.from_user.id)

        if not templates:
            await query.answer("У вас нет сохранённых шаблонов", show_alert=False)

            # Проверяем, не находимся ли мы уже в главном меню
            if "Главное меню:" in query.message.text:
                return  # Уже в главном меню, ничего не делаем

            keyboard = [
                [InlineKeyboardButton("📅 Создать мероприятие", callback_data="menu_create_event")],
                [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")],
                [InlineKeyboardButton("📁 Мои шаблоны", callback_data="menu_my_templates")]
            ]

            try:
                await query.edit_message_text(
                    "Главное меню:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except telegram.error.BadRequest as e:
                if "not modified" in str(e):
                    # Сообщение уже содержит главное меню, игнорируем ошибку
                    pass
                else:
                    raise
            return

        total_templates = len(templates)
        max_pages = (total_templates + limit - 1) // limit
        current_page = offset // limit + 1

        page_templates = templates[offset:offset+limit]

        keyboard = []
        for t in page_templates:
            keyboard.append([
                InlineKeyboardButton(
                    f"{t['name']} ({t['time']})",
                    callback_data=f"use_template|{t['id']}"
                ),
                InlineKeyboardButton(
                    "🗑️",
                    callback_data=f"delete_template|{t['id']}"
                )
            ])

        # Добавляем пагинацию только если шаблоны принадлежат текущему пользователю
        if str(query.from_user.id) == str(context.user_data.get('template_owner_id', query.from_user.id)):
            pagination_buttons = []
            if offset > 0:
                pagination_buttons.append(
                    InlineKeyboardButton("⬅️", callback_data=f"templates_page|{offset-limit}")
                )

            pagination_buttons.append(
                InlineKeyboardButton(f"{current_page}/{max_pages}", callback_data="noop")
            )

            if offset + limit < total_templates:
                pagination_buttons.append(
                    InlineKeyboardButton("➡️", callback_data=f"templates_page|{offset+limit}")
                )

            if pagination_buttons:
                keyboard.append(pagination_buttons)

        # Сохраняем ID владельца для проверки в обработчике
        context.user_data['template_owner_id'] = query.from_user.id

        # Кнопка закрытия
        keyboard.append([
            InlineKeyboardButton(
                "❌ Закрыть",
                callback_data=f"close_templates|{query.from_user.id}"  # Добавляем ID пользователя для проверки
            )
        ])

        await query.edit_message_text(
            "📁 Ваши шаблоны мероприятий:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Ошибка загрузки шаблонов: {str(e)}", exc_info=True)
        await query.answer("⚠️ Ошибка загрузки шаблонов", show_alert=False)

        # Возвращаем в главное меню при ошибке
        keyboard = [
            [InlineKeyboardButton("📅 Создать мероприятие", callback_data="menu_create_event")],
            [InlineKeyboardButton("📋 Мои мероприятия", callback_data="menu_my_events")],
            [InlineKeyboardButton("📁 Мои шаблоны", callback_data="menu_my_templates")]
        ]

        try:
            await query.edit_message_text(
                "Главное меню:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except telegram.error.BadRequest as e:
            if "not modified" in str(e):
                pass  # Уже в главном меню
            else:
                raise

async def handle_save_template(query, context, event_id):
    try:
        event = get_event(context.bot_data["db_path"], event_id)

        if not event:
            await query.answer("Мероприятие не найдено", show_alert=False)
            return

        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может сохранять шаблоны", show_alert=False)
            return

        # Сохраняем в базу
        with sqlite3.connect(context.bot_data["db_path"]) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO event_templates 
                (user_id, name, description, date, time, participant_limit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (query.from_user.id,
                 f"{event['description'][:30]}...",  # Обрезаем длинное описание
                 event['description'],
                 event['date'],
                 event['time'],
                 event['participant_limit'],
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()

        await query.answer("✅ Шаблон сохранён!", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка сохранения шаблона: {e}")
        await query.answer("⚠️ Не удалось сохранить шаблон", show_alert=False)

async def handle_use_template(query, context, template_id):
    """Создает черновик на основе шаблона"""
    try:
        # Получаем шаблон
        with sqlite3.connect(context.bot_data["db_path"]) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM event_templates WHERE id = ? AND user_id = ?",
                (template_id, query.from_user.id)
            )
            template = cursor.fetchone()

        if not template:
            await query.answer("Шаблон не найден", show_alert=False)
            return

        # Создаем черновик СРАЗУ с bot_message_id
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status="AWAIT_DATE",
            description=template['description'],
            time=template['time'],
            participant_limit=template['participant_limit'],
            is_from_template=True,
            bot_message_id=query.message.message_id,  # <-- Передаём сразу!
            original_message_id=query.message.message_id
        )

        if not draft_id:
            raise Exception("Не удалось создать черновик")

        # Подготавливаем клавиатуру
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]

        # Пытаемся отредактировать существующее сообщение
        try:
            await query.edit_message_text(
                text=f"🔄 Шаблон применён:\n\n"
                     f"📢 {template['description']}\n"
                     f"🕒 Время: {template['time']}\n"
                     f"👥 Лимит: {template['participant_limit'] or 'нет'}\n\n"
                     f"Теперь укажите дату мероприятия:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение: {e}")
            # Если редактирование не удалось, создаем новое сообщение
            message = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"🔄 Шаблон применён:\n\n"
                     f"📢 {template['description']}\n"
                     f"🕒 Время: {template['time']}\n"
                     f"👥 Лимит: {template['participant_limit'] or 'нет'}\n\n"
                     f"Теперь укажите дату мероприятия:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            # Обновляем черновик с ID нового сообщения
            update_draft(
                db_path=context.bot_data["drafts_db_path"],
                draft_id=draft_id,
                bot_message_id=message.message_id  # <-- Только если сообщение новое!
            )

    except Exception as e:
        logger.error(f"Ошибка применения шаблона: {e}")
        await query.answer("⚠️ Не удалось применить шаблон", show_alert=False)

async def handle_delete_template(query, context, template_id):
    """Обрабатывает удаление шаблона"""
    try:
        # Проверяем, что шаблон принадлежит пользователю
        templates = get_user_templates(context.bot_data["db_path"], query.from_user.id)
        if not any(t['id'] == template_id for t in templates):
            await query.answer("❌ Шаблон не найден или нет прав", show_alert=False)
            return

        # Удаляем шаблон
        with sqlite3.connect(context.bot_data["db_path"]) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM event_templates WHERE id = ?", (template_id,))
            conn.commit()

        # Показываем уведомление
        await query.answer("✅ Шаблон удалён", show_alert=False)

        # Обновляем список шаблонов
        await handle_my_templates(query, context)

    except Exception as e:
        logger.error(f"Ошибка удаления шаблона: {str(e)}", exc_info=True)
        await query.answer("⚠️ Не удалось удалить шаблон", show_alert=False)

async def save_user_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        with sqlite3.connect(context.bot_data["db_path"]) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO users 
                (id, first_name, last_name, username, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user.id,
                 user.first_name,
                 user.last_name or "",
                 user.username or "",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()