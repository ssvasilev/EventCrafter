from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from src.handlers.conversation_handler_states import SET_DATE
from src.database.db_draft_operations import update_draft, set_user_state, add_draft


async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Инициализация черновика если его нет
    # Для восстановленных сессий пропускаем создание черновика
    if not context.user_data.get("restored"):
        if 'draft_id' not in context.user_data:
            draft_id = add_draft(
                context.bot_data["drafts_db_path"],
                update.message.from_user.id,
                update.message.chat_id,
                "AWAIT_DATE"
            )
            context.user_data["draft_id"] = draft_id
        set_user_state(
            context.bot_data["drafts_db_path"],
            update.message.from_user.id,
            "create_event_handler",
            SET_DATE,
            draft_id
        )

    # Получаем текст описания
    description = update.message.text

    # Обновляем черновик
    update_draft(
        db_path=context.bot_data["drafts_db_path"],
        draft_id=context.user_data["draft_id"],
        status="AWAIT_DATE",
        description=description
    )

    # Обновляем состояние
    set_user_state(
        context.bot_data["drafts_db_path"],
        update.message.from_user.id,
        "create_event_handler",
        SET_DATE,
        context.user_data["draft_id"]
    )

    # Создаем клавиатуру с кнопкой "Отмена"
    keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data="cancel_input")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Редактируем существующее сообщение бота
    await context.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=context.user_data["bot_message_id"],
        text=f"📢 {description}\n\nВведите дату мероприятия в формате ДД.ММ.ГГГГ",
        reply_markup=reply_markup,
    )

    # Пытаемся удалить сообщение пользователя
    try:
        await update.message.delete()
    except BadRequest:
        pass

    return SET_DATE