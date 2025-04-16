from datetime import datetime

from telegram.error import BadRequest

from src.database.db_draft_operations import update_draft
from src.event.edit.update_draft_message import update_draft_message

from src.logger import logger
from src.utils.show_input_error import show_input_error


async def process_regular_date(update, context, draft, date_input):
    """Обработка даты для обычного сценария"""
    try:
        # 1. Валидация даты
        datetime.strptime(date_input, "%d.%m.%Y").date()

        # 2. Обновление черновика
        update_draft(
            db_path=context.bot_data["drafts_db_path"],
            draft_id=draft["id"],
            status="AWAIT_TIME",
            date=date_input
        )

        # 3. Обновление сообщения
        new_text = f"📢 {draft['description']}\n\n📅 Дата: {date_input}\n\nВведите время (ЧЧ:ММ)"
        await update_draft_message(context, draft["id"], new_text, update.message.chat_id)

        # 4. Удаление сообщения пользователя
        try:
            await update.message.delete()
        except BadRequest:
            pass

    except ValueError:
        await show_input_error(update, context, "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    except Exception as e:
        logger.error(f"Ошибка обработки даты: {e}")
        await show_input_error(update, context, "⚠️ Ошибка обработки ввода")