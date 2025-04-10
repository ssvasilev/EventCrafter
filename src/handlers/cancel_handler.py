from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

from config import DB_PATH
from src.database.db_draft_operations import delete_draft, get_user_drafts, get_draft, get_user_chat_draft
from src.database.db_operations import get_event, get_participants
from src.logger import logger
from src.message.send_message import send_event_message, EMPTY_PARTICIPANTS_TEXT
from src.utils.utils import format_users_list


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

        # Получаем черновик (если есть)
        draft = get_user_chat_draft(
            context.bot_data["drafts_db_path"],
            query.from_user.id,
            query.message.chat_id
        )

        # Восстанавливаем оригинальное сообщение
        event = get_event(context.bot_data["db_path"], event_id)
        if event:
            try:
                # Редактируем текущее сообщение вместо удаления
                await send_event_message(
                    event_id=event["id"],
                    context=context,
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id  # Редактируем текущее сообщение
                )
            except Exception as e:
                logger.error(f"Ошибка при восстановлении сообщения: {e}")
                await restore_event_message_fallback(event, context, query)

        # Удаляем черновик если он существует
        if draft:
            delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    except Exception as e:
        logger.error(f"Ошибка при отмене редактирования: {e}")
        await query.edit_message_text("⚠️ Не удалось отменить редактирование")

async def restore_event_message_fallback(event, context, query):
    """
    Альтернативный способ восстановления сообщения о мероприятии
    Используется при ошибках в основном методе send_event_message
    """
    try:
        # Получаем базовую информацию о мероприятии
        db_path = context.bot_data.get("db_path", DB_PATH)
        participants = get_participants(db_path, event["id"])
        participants_text = format_users_list(participants, EMPTY_PARTICIPANTS_TEXT)

        # Формируем клавиатуру
        keyboard = [
            [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event['id']}")],
            [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event['id']}")],
            [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event['id']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Форматируем дату
        date = datetime.strptime(event["date"], "%d.%m.%Y").date()
        formatted_date = date.strftime("%d.%m.%Y (%A)")

        # Формируем текст сообщения (упрощенная версия)
        message_text = (
            f"📢 <b>{event['description']}</b>\n"
            f"📅 <i>Дата: </i> {formatted_date}\n"
            f"🕒 <i>Время: </i> {event['time']}\n"
            f"👥 <i>Лимит участников: </i> {event['participant_limit'] or '∞'}\n\n"
            f"✅ <i>Участники: </i>\n{participants_text}"
        )

        # Редактируем текущее сообщение (не удаляем его)
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        logger.info("Сообщение восстановлено в упрощенном формате")

    except Exception as e:
        logger.error(f"Ошибка в restore_event_message_fallback: {e}")
        try:
            # Последняя попытка - просто текст без форматирования
            await query.edit_message_text(
                text=f"📢 {event['description']}\n"
                     f"📅 Дата: {event['date']}\n"
                     f"🕒 Время: {event['time']}\n"
                     f"👥 Лимит: {event['participant_limit'] or '∞'}",
                reply_markup=InlineKeyboardMarkup(keyboard) if 'keyboard' in locals() else None
            )
        except Exception as e:
            logger.error(f"Критическая ошибка восстановления сообщения: {e}")
            # Не удаляем сообщение вообще, оставляем как есть
async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода при редактировании поля"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise Exception("Черновик не найден")

        event_id = draft.get("event_id")
        original_message_id = draft.get("original_message_id")

        # Удаляем черновик перед восстановлением сообщения
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        if event_id and original_message_id:
            # Восстанавливаем оригинальное сообщение
            event = get_event(context.bot_data["db_path"], event_id)
            if event:
                try:
                    await send_event_message(
                        event_id=event["id"],
                        context=context,
                        chat_id=query.message.chat_id,
                        message_id=original_message_id
                    )
                except Exception as e:
                    logger.error(f"Ошибка при восстановлении сообщения: {e}")
                    await restore_event_message_fallback(event, context, query)

        # Редактируем текущее сообщение с формой в пустое
        try:
            await query.edit_message_text(
                text="Редактирование отменено",
                reply_markup=None
            )
        except Exception as e:
            logger.info(f"Не удалось обновить сообщение с формой: {e}")

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


async def safe_restore_event(event_id, context, chat_id, message_id):
    """Безопасное восстановление сообщения о мероприятии"""
    try:
        event = get_event(context.bot_data["db_path"], event_id)
        if not event:
            return False

        await send_event_message(
            event_id=event_id,
            context=context,
            chat_id=chat_id,
            message_id=message_id
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка восстановления сообщения {message_id}: {e}")
        return False

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