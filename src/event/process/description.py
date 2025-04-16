from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft, get_draft
from src.logger import logger
from src.utils.show_input_error import show_input_error


async def process_description(update, context, draft, description):
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
        await show_input_error(update, context, "⚠️ Ошибка обработки ввода")