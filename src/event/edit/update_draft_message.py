from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from src.database.db_draft_operations import get_draft, update_draft
from src.logger import logger


async def update_draft_message(context, draft_id, new_text, chat_id):
    """Универсальная функция для обновления сообщения черновика"""
    try:
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)
        if not draft:
            raise ValueError("Черновик не найден")

        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]

        # Если есть bot_message_id, пробуем редактировать
        if draft.get("bot_message_id"):
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=int(draft["bot_message_id"]),
                    text=new_text,
                    reply_markup=InlineKeyboardMarkup(keyboard))
                return
            except (BadRequest, ValueError) as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")

        # Если редактирование не удалось - создаем новое
        new_message = await context.bot.send_message(
            chat_id=chat_id,
            text=new_text,
            reply_markup=InlineKeyboardMarkup(keyboard))

        # Обновляем bot_message_id в базе
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft_id,
            bot_message_id=new_message.message_id)

    except Exception as e:
        logger.error(f"Ошибка в _update_draft_message: {e}")
        raise