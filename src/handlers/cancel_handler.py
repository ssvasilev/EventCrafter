from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

from config import DB_PATH
from src.database.db_draft_operations import delete_draft, get_user_drafts, get_draft, get_user_chat_draft
from src.database.db_operations import get_event, get_participants
from src.logger import logger
from src.message.send_message import send_event_message, EMPTY_PARTICIPANTS_TEXT
from src.utils.pin_message import pin_message_safe
from src.utils.utils import format_users_list


async def cancel_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Упрощенный обработчик отмены черновика (авторство уже проверено)"""
    query = update.callback_query
    await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            # Проверяем user_data как fallback
            if 'current_draft_id' in context.user_data:
                draft_id = context.user_data['current_draft_id']
                draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if draft:
            delete_draft(context.bot_data["drafts_db_path"], draft_id)
            if 'current_draft_id' in context.user_data:
                del context.user_data['current_draft_id']

            await query.edit_message_text("Создание мероприятия отменено")
        else:
            await query.answer("Черновик уже удален", show_alert=False)

    except Exception as e:
        logger.error(f"Ошибка при отмене черновика: {e}")
        await query.answer("⚠️ Не удалось отменить создание", show_alert=False)

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены редактирования мероприятия"""
    query = update.callback_query
    #await query.answer()

    try:
        # Получаем event_id из callback_data
        event_id = int(query.data.split('|')[1])
        event = get_event(context.bot_data["db_path"], event_id)

        if not event:
            await query.edit_message_text("Мероприятие не найдено")
            return

        # Проверяем авторство
        if query.from_user.id != event["creator_id"]:
            await query.answer("Только автор может отменить редактирование", show_alert=False)
            return

        # Получаем черновик (если есть)
        draft = get_user_chat_draft(
            context.bot_data["drafts_db_path"],
            query.from_user.id,
            query.message.chat_id
        )

        # Восстанавливаем оригинальное сообщение
        try:
            # Редактируем текущее сообщение вместо удаления
            await send_event_message(
                event_id=event["id"],
                context=context,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id
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
    Упрощенное восстановление сообщения при ошибках основного метода.
    Не удаляет сообщения, только редактирует существующее.
    """
    try:
        # Получаем базовые данные
        db_path = context.bot_data.get("db_path", DB_PATH)
        participants = get_participants(db_path, event["id"])

        # Формируем упрощенное сообщение
        message_text = (
            f"📢 <b>{event['description']}</b>\n"
            f"📅 <i>Дата:</i> {event['date']}\n"
            f"🕒 <i>Время:</i> {event['time']}\n"
            f"👥 <i>Лимит:</i> {'∞' if event['participant_limit'] is None else event['participant_limit']}\n\n"
            f"✅ <i>Участники:</i>\n{format_users_list(participants, EMPTY_PARTICIPANTS_TEXT)}"
        )

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Участвую", callback_data=f"join|{event['id']}")],
            [InlineKeyboardButton("❌ Не участвую", callback_data=f"leave|{event['id']}")],
            [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event['id']}")]
        ])

        # Редактируем текущее сообщение
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )

        # Пытаемся закрепить (если это новое сообщение)
        if not event.get("message_id"):
            await pin_message_safe(context, query.message.chat_id, query.message.message_id)

    except Exception as e:
        logger.error(f"Критическая ошибка в restore_event_message_fallback: {e}")
        # Последняя попытка - минимальное сообщение
        try:
            await query.edit_message_text(
                text=f"📢 {event['description']}\n"
                     f"📅 Дата: {event['date']}\n"
                     f"🕒 Время: {event['time']}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{event['id']}")]
                ])
            )
        except:
            pass  # Сохраняем текущее состояние чата
async def cancel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены ввода при редактировании поля мероприятия"""
    query = update.callback_query
    #await query.answer()

    try:
        draft_id = int(query.data.split('|')[1])
        draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

        if not draft:
            raise Exception("Черновик не найден")

        # Проверяем авторство для редактирования существующего мероприятия
        if draft.get("event_id"):
            event = get_event(context.bot_data["db_path"], draft["event_id"])
            if event and query.from_user.id != event["creator_id"]:
                await query.answer("❌ Только автор может отменить редактирование", show_alert=False)
                return
        # Сохраняем необходимые данные перед удалением черновика
        event_id = draft.get("event_id")
        original_message_id = draft.get("original_message_id")
        current_message_id = query.message.message_id

        # Удаляем черновик
        delete_draft(context.bot_data["drafts_db_path"], draft_id)

        if event_id and original_message_id:
            # Если это редактирование существующего мероприятия
            if current_message_id != original_message_id:
                # Удаляем сообщение с формой редактирования
                try:
                    await context.bot.delete_message(
                        chat_id=query.message.chat_id,
                        message_id=current_message_id
                    )
                except Exception as e:
                    logger.info(f"Не удалось удалить сообщение с формой: {e}")

            # Восстанавливаем оригинальное сообщение
            event = get_event(context.bot_data["db_path"], event_id)
            if event:
                try:
                    await send_event_message(
                        event_id=event_id,
                        context=context,
                        chat_id=query.message.chat_id,
                        message_id=original_message_id
                    )
                except Exception as e:
                    logger.error(f"Ошибка восстановления сообщения: {e}")
                    await restore_event_message_fallback(event, context, query)
        else:
            # Если это создание нового мероприятия (не редактирование)
            try:
                await query.edit_message_text(
                    text="Создание мероприятия отменено",
                    reply_markup=None
                )
            except Exception as e:
                logger.info(f"Не удалось обновить сообщение: {e}")

    except Exception as e:
        logger.error(f"Ошибка при отмене ввода: {e}", exc_info=True)
        try:
            await query.edit_message_text("⚠️ Не удалось отменить ввод")
        except:
            pass
"""
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #Обработчик команды /cancel
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    # Удаляем все черновики пользователя
    drafts = get_user_drafts(context.bot_data["drafts_db_path"], user_id)
    for draft in drafts:
        delete_draft(context.bot_data["drafts_db_path"], draft["id"])

    await update.message.reply_text("Все активные действия отменены")
"""
"""
async def safe_restore_event(event_id, context, chat_id, message_id):
    #Безопасное восстановление сообщения о мероприятии
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
"""

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