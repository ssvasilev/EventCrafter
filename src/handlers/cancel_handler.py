from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from src.database.db_draft_operations import delete_draft
from src.logger import logger

async def cancel_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания нового мероприятия"""
    query = update.callback_query
    await query.answer()

    try:
        # Получаем ID черновика
        draft_id = int(query.data.split('|')[1])

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Удаляем сообщение с формой
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except BadRequest as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка при отмене черновика: {e}")
        try:
            await query.edit_message_text("⚠️ Не удалось отменить создание")
        except:
            pass

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена редактирования существующего мероприятия"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise Exception("Черновик не найден")

        # Восстанавливаем оригинальное сообщение мероприятия
        if draft.get("event_id") and draft.get("original_message_id"):
            event = get_event(context.bot_data["db_path"], draft["event_id"])
            if event:
                await send_event_message(
                    event["id"],
                    context,
                    draft["chat_id"],
                    message_id=draft["original_message_id"]
                )

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Удаляем сообщение с формой редактирования
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except BadRequest:
            pass

    except Exception as e:
        logger.error(f"Ошибка при отмене редактирования: {e}")
        try:
            await query.edit_message_text("⚠️ Не удалось отменить редактирование")
        except:
            pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Удаляем все черновики пользователя
    drafts = get_user_drafts(context.bot_data["drafts_db_path"], user_id)
    for draft in drafts:
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    await update.message.reply_text("Все активные действия отменены")