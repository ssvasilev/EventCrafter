import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.database.db_operations import get_event, get_user_templates
from src.logger import logger


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


async def save_as_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    event_id = int(query.data.split('|')[1])

    event = get_event(context.bot_data["db_path"], event_id)

    # Сохраняем в базу
    with sqlite3.connect(context.bot_data["db_path"]) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO event_templates 
            (user_id, name, description, time, participant_limit, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (query.from_user.id,
             f"Шаблон {datetime.now().strftime('%d.%m')}",
             event['description'],
             event['time'],
             event['participant_limit'],
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    await query.answer("Шаблон сохранён!", show_alert=True)

async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(context.bot_data["db_path"]) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name FROM event_templates WHERE user_id = ?",
            (update.effective_user.id,)
        )
        templates = cursor.fetchall()

    keyboard = [
        [InlineKeyboardButton(t[1], callback_data=f"use_template|{t[0]}")]
        for t in templates
    ]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    await update.message.reply_text(
        "Ваши шаблоны мероприятий:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def use_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    template_id = int(query.data.split('|')[1])

    # Получаем шаблон из БД
    with sqlite3.connect(context.bot_data["db_path"]) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM event_templates WHERE id = ? AND user_id = ?",
            (template_id, query.from_user.id)
        )
        template = cursor.fetchone()

    # Создаём черновик на основе шаблона
    context.user_data['draft'] = {
        'description': template['description'],
        'time': template['time'],
        'limit': template['participant_limit']
    }

    await query.edit_message_text(
        f"Шаблон применён!\n\nОписание: {template['description']}\n"
        f"Время: {template['time']}\nЛимит: {template['participant_limit'] or 'нет'}"
    )

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