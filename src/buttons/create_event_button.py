from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from src.database.db_draft_operations import add_draft, get_user_chat_draft, update_draft, delete_draft
from src.logger.logger import logger

async def create_event_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки 'Создать мероприятие'"""
    query = update.callback_query
    try:
        await query.answer()

        creator_id = query.from_user.id
        chat_id = query.message.chat.id

        # Проверяем существующий черновик
        existing_draft = get_user_chat_draft(context.bot_data["drafts_db_path"], creator_id, chat_id)
        if existing_draft and existing_draft.get('status') != 'DONE':
            await query.edit_message_text("У вас уже есть активное создание мероприятия")
            return

        # Создаем черновик
        print("⏺ Добавление черновика:", context.bot_data["drafts_db_path"], creator_id, chat_id)
        draft_id = add_draft(
            db_path=context.bot_data["drafts_db_path"],
            creator_id=creator_id,
            chat_id=chat_id,
            status="AWAIT_DESCRIPTION",
            is_from_template=False,
            original_message_id=query.message.message_id  # Сохраняем ID исходного сообщения
        )
        print("✅ draft_id =", draft_id)
        if not draft_id:
            await query.edit_message_text("❌ Ошибка при создании мероприятия")
            return

        # Редактируем существующее сообщение вместо отправки нового
        keyboard = [[InlineKeyboardButton("⛔ Отмена", callback_data=f"cancel_draft|{draft_id}")]]
        try:
            logger.info(f"Попытка редактирования сообщения с ID {query.message.message_id}")
            await query.edit_message_text(
                text="✏️ Введите описание мероприятия:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            # Сохраняем ID сообщения в черновик (теперь это ID отредактированного сообщения)
            update_draft(
                db_path=context.bot_data["drafts_db_path"],
                draft_id=draft_id,
                bot_message_id=query.message.message_id
            )

            # Сохраняем draft_id в user_data для последующей обработки
            context.user_data['current_draft_id'] = draft_id

        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            logger.error(f"Контекст: {context.bot_data}")
            logger.error(f"Query: {query}")
            logger.error(f"Draft ID: {draft_id}")
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            await query.edit_message_text("❌ Не удалось начать создание мероприятия")
            # Удаляем черновик, если не удалось отредактировать сообщение
            delete_draft(context.bot_data["drafts_db_path"], draft_id)

    except Exception as e:
        logger.error(f"Ошибка в create_event_button: {e}")
        await query.edit_message_text("⚠️ Произошла непредвиденная ошибка")

# Регистрация обработчика
def register_create_handlers(application):
    application.add_handler(CallbackQueryHandler(
        create_event_button,
        pattern="^create_event$"
    ))