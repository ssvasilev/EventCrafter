from datetime import datetime

from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft
from src.event.edit.update_draft_message import update_draft_message

from src.logger import logger
from src.utils.show_input_error import show_input_error


async def process_time(update, context, draft, time_input):
    """Обработка шага ввода времени"""
    try:
        datetime.strptime(time_input, "%H:%M").time()

        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_LIMIT",
            time=time_input
        )

        # Обновляем сообщение через универсальную функцию
        new_text = (f"📢 {draft['description']}\n\n"
                    f"📅 Дата: {draft['date']}\n"
                    f"🕒 Время: {time_input}\n\n"
                    f"Введите лимит участников (0 - без лимита):")

        await update_draft_message(context, draft["id"], new_text, update.message.chat_id)

        # Удаляем сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

    except ValueError:
        await show_input_error(
            update, context,
            "❌ Неверный формат времени. Используйте ЧЧ:ММ"
        )
    except Exception as e:
        logger.error(f"Ошибка обработки времени: {e}", exc_info=True)
        await show_input_error(
            update, context,
            "⚠️ Произошла ошибка при обработке времени"
        )