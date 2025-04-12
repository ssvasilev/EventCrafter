from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.db_operations import get_user_templates


async def handle_my_templates(query, context):
    """Показывает список шаблонов пользователя"""
    templates = get_user_templates(context.bot_data["db_path"], query.from_user.id)

    if not templates:
        await query.answer("У вас нет сохранённых шаблонов", show_alert=True)
        return

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
        reply_markup=InlineKeyboardMarkup(keyboard)
    )