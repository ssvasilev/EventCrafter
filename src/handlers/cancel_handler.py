from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest
from src.database.db_draft_operations import delete_draft, get_user_drafts, get_draft, get_user_chat_draft
from src.database.db_operations import get_event
from src.logger import logger
from src.message.send_message import send_event_message


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

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены редактирования мероприятия"""
    query = update.callback_query
    await query.answer()

    try:
        # Получаем event_id из callback_data
        event_id = int(query.data.split('|')[1])
        draft = get_user_chat_draft(
            context.bot_data["drafts_db_path"],
            query.from_user.id,
            query.message.chat_id
        )

        # Если есть черновик - удаляем его
        if draft:
            delete_draft(context.bot_data["drafts_db_path"], draft["id"])

        # Восстанавливаем оригинальное сообщение мероприятия
        event = get_event(context.bot_data["db_path"], event_id)
        if event:
            await send_event_message(
                event["id"],
                context,
                query.message.chat_id,
                message_id=query.message.message_id
            )

    except Exception as e:
        logger.error(f"Ошибка при отмене редактирования: {e}")
        try:
            await query.edit_message_text("⚠️ Не удалось отменить редактирование")
        except:
            pass

async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода при редактировании поля"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise Exception("Черновик не найден")

        # Если это редактирование существующего мероприятия
        if draft.get("event_id"):
            await cancel_edit(update, context)
        else:
            # Если это создание нового мероприятия
            await cancel_draft(update, context)

    except Exception as e:
        logger.error(f"Ошибка при отмене ввода: {e}")
        await query.edit_message_text("⚠️ Не удалось отменить ввод")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Удаляем все черновики пользователя
    drafts = get_user_drafts(context.bot_data["drafts_db_path"], user_id)
    for draft in drafts:
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    await update.message.reply_text("Все активные действия отменены")

def register_cancel_handlers(application):
    """Регистрирует обработчики отмены"""
    application.add_handler(CallbackQueryHandler(
        cancel_draft,
        pattern=r"^cancel_draft\|"
    ))
    application.add_handler(CallbackQueryHandler(
        cancel_edit,
        pattern=r"^cancel_edit\|"
    ))
    application.add_handler(CallbackQueryHandler(
        cancel_input,
        pattern=r"^cancel_input\|"
    ))