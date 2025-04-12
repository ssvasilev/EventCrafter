import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.database.db_draft_operations import add_draft, update_draft
from src.database.db_operations import get_event, get_user_templates
from src.logger import logger


async def handle_my_templates(query, context):
    """Показывает список шаблонов пользователя с обработкой ошибок"""
    try:
        templates = get_user_templates(context.bot_data["db_path"], query.from_user.id)

        if not templates:
            await query.answer("У вас нет сохранённых шаблонов", show_alert=True)
            return

        # Логируем для отладки
        logger.debug(f"Найдены шаблоны: {templates}")

        keyboard = [
            [InlineKeyboardButton(
                f"{t['name']} ({t['time']})",
                callback_data=f"use_template|{t['id']}"
            )]
            for t in templates[:5]  # Ограничиваем количество
        ]

        if len(templates) > 5:
            keyboard.append([InlineKeyboardButton(
                "Показать ещё...",
                callback_data="more_templates|5"
            )])

        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close_templates")])

        await query.edit_message_text(
            "📁 Ваши шаблоны мероприятий:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка загрузки шаблонов: {str(e)}", exc_info=True)
        await query.answer("⚠️ Ошибка загрузки шаблонов", show_alert=True)


async def handle_save_template(query, context, event_id):
    try:
        event = get_event(context.bot_data["db_path"], event_id)

        if not event:
            await query.answer("Мероприятие не найдено", show_alert=True)
            return

        if query.from_user.id != event["creator_id"]:
            await query.answer("❌ Только автор может сохранять шаблоны", show_alert=True)
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
        await query.answer("⚠️ Не удалось сохранить шаблон", show_alert=True)

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
            await query.answer("Шаблон не найден", show_alert=True)
            return

        # Сначала создаем черновик без bot_message_id
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=query.from_user.id,
            chat_id=query.message.chat_id,
            status="AWAIT_DATE",
            description=template['description'],
            time=template['time'],
            participant_limit=template['participant_limit'],
            is_from_template=True
        )

        if not draft_id:
            raise Exception("Не удалось создать черновик")

        # Подготавливаем клавиатуру с полученным draft_id
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

            # Обновляем черновик с ID сообщения
            update_draft(
                db_path=context.bot_data["drafts_db_path"],
                draft_id=draft_id,
                bot_message_id=query.message.message_id
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
                #bot_message_id=message.message_id
            )

    except Exception as e:
        logger.error(f"Ошибка применения шаблона: {e}")
        await query.answer("⚠️ Не удалось применить шаблон", show_alert=True)

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