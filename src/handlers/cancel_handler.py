from telegram import Update
from telegram.ext import ContextTypes
from src.database.db_draft_operations import delete_draft
from src.logger.logger import logger
from src.handlers.menu import show_main_menu

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