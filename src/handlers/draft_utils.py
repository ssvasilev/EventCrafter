
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from src.database.db_operations import  get_event
from src.event.edit.edit_step import process_edit_step
from src.event.process.description import process_description
from src.event.process.limit import process_limit
from src.event.process.regular_date import process_regular_date
from src.event.process.template_date import process_template_date
from src.event.process.time import process_time
from src.logger.logger import logger
from src.utils.show_input_error import show_input_error


async def process_draft_step(update: Update, context: ContextTypes.DEFAULT_TYPE, draft):
    #Обрабатывает текущий шаг черновика на основе его статуса
    chat_id = update.message.chat_id

    try:
        # Добавляем детальное логирование
        logger.info(f"Начало обработки черновика ID {draft['id']}, статус: {draft['status']}")
        logger.info(f"Полные данные черновика: {draft}")

        # Проверка обязательных полей для редактирования
        if draft["status"].startswith("EDIT_"):
            if 'event_id' not in draft:
                logger.error(f"Черновик редактирования {draft['id']} не содержит event_id!")
                await show_input_error(update, context, "⚠️ Ошибка: мероприятие не найдено")
                return

            event = get_event(context.bot_data["db_path"], draft["event_id"])
            if not event:
                logger.error(f"Мероприятие {draft['event_id']} не найдено в БД")
                await show_input_error(update, context, "⚠️ Мероприятие не найдено")
                return

        # Обработка в зависимости от статуса
        if draft["status"] == "AWAIT_DESCRIPTION":
            await process_description(update, context, draft, update.message.text)
        elif draft.get('is_from_template') and draft['status'] == 'AWAIT_DATE':
            await process_template_date(update, context, draft, update.message.text)
        elif draft["status"] == "AWAIT_DATE":
            await process_regular_date(update, context, draft, update.message.text)
        elif draft["status"] == "AWAIT_TIME":
            await process_time(update, context, draft, update.message.text)
        elif draft["status"] == "AWAIT_LIMIT":
            await process_limit(update, context, draft, update.message.text)
        elif draft["status"].startswith("EDIT_"):
            await process_edit_step(update, context, draft)
        else:
            logger.error(f"Неизвестный статус черновика: {draft['status']}")
            await show_input_error(update, context, "⚠️ Неизвестное состояние")

        # Пытаемся удалить сообщение пользователя
        try:
            await update.message.delete()
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    except Exception as e:
        logger.error(f"Ошибка обработки черновика: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла ошибка при обработке вашего ввода"
        )