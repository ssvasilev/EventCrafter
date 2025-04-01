from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_draft_operations import delete_draft, get_user_drafts, get_draft
from src.database.db_operations import get_event
from src.logger.logger import logger
from src.handlers.menu import show_main_menu
from src.message.send_message import send_event_message


async def cancel_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены черновика"""
    query = update.callback_query
    await query.answer()

    try:
        # Получаем ID черновика из callback_data (формат: cancel_draft|123)
        draft_id = int(query.data.split('|')[1])

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        # Пытаемся удалить сообщение бота с формой
        try:
            await context.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение бота: {e}")

        # Показываем главное меню
        await show_main_menu(
            context.bot,
            chat_id=query.message.chat_id,
            user_id=query.from_user.id
        )

    except Exception as e:
        logger.error(f"Ошибка при отмене черновика: {e}")
        # В случае ошибки просто показываем меню
        await show_main_menu(
            context.bot,
            chat_id=query.message.chat_id,
            user_id=query.from_user.id
        )


async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода при редактировании поля (возврат к исходному сообщению)"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise Exception("Черновик не найден")

        # Восстанавливаем исходное сообщение мероприятия
        await _restore_original_message(context, draft)

    except Exception as e:
        logger.error(f"Ошибка при отмене ввода: {e}")
        await query.edit_message_text("⚠️ Не удалось отменить ввод")


async def _restore_original_message(context: ContextTypes.DEFAULT_TYPE, draft):
    """Восстанавливает исходное сообщение мероприятия"""
    if draft.get("original_message_id"):
        # Если редактировали существующее мероприятие
        event = get_event(context.bot_data["db_path"], draft["event_id"])
        if event:
            await send_event_message(
                event["id"],
                context,
                draft["chat_id"],
                message_id=draft["original_message_id"]
            )
    else:
        # Если создавали новое мероприятие
        await show_main_menu(
            context.bot,
            chat_id=draft["chat_id"],
            user_id=draft["creator_id"]
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Удаляем все активные черновики пользователя
    drafts = get_user_drafts(context.bot_data["drafts_db_path"], user_id)
    for draft in drafts:
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    await show_main_menu(
        context.bot,
        chat_id=chat_id,
        user_id=user_id
    )