from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.database.db_operations import get_event
from src.event.edit.update_event_field import update_event_field, validate_and_update
from src.event.edit.update_limit import update_participant_limit
from src.logger import logger
from src.utils.show_input_error import show_input_error


async def process_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    """Обрабатывает шаг редактирования с унифицированным выводом ошибок"""
    user = update.message.from_user if update.message else update.callback_query.from_user

    # Проверяем авторство
    event = get_event(context.bot_data["db_path"], draft["event_id"])
    if user.id != event["creator_id"]:
        await show_input_error(
            update, context,
            "❌ Только автор может редактировать мероприятие"
        )
        return

    field = draft["status"].split("_")[1]  # Получаем поле из статуса
    user_input = update.message.text if update.message else None

    if field == "description":
        await update_event_field(context, draft, "description", user_input)
    elif field == "date":
        await validate_and_update(update, context, draft, "date", user_input, "%d.%m.%Y", "ДД.ММ.ГГГГ")
    elif field == "time":
        await validate_and_update(update, context, draft, "time", user_input, "%H:%M", "ЧЧ:ММ")
    elif field == "limit":
        await update_participant_limit(update, context, draft, user_input)

    # Удаляем сообщение пользователя, если это текстовый ввод
    if update.message:
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")