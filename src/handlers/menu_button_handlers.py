from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from src.database.db_draft_operations import get_draft
from src.database.db_operations import get_event
from src.handlers.button_handlers import handle_cancel_delete
from src.handlers.create_event_handler import create_event_button
from src.buttons.my_events_button import my_events_button
from src.handlers.cancel_handler import cancel_draft, cancel_input, cancel_edit
from src.logger.logger import logger

async def menu_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    try:
        if data.startswith("menu_"):
            action = data[5:]  # Убираем префикс "menu_"

            if action == "create_event":
                await create_event_button(update, context)
            elif action == "my_events":
                await my_events_button(update, context)
            else:
                logger.warning(f"Unknown menu action: {action}")
                await query.edit_message_text("Неизвестная команда меню.")

        elif data.startswith("cancel_"):
            if data.startswith("cancel_draft|"):
                draft_id = int(data.split('|')[1])
                draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

                if not draft:
                    await query.answer("Черновик не найден", show_alert=False)
                    return

                # Для черновиков редактирования проверяем авторство мероприятия
                if draft.get("event_id"):
                    event = get_event(context.bot_data["db_path"], draft["event_id"])
                    if event and query.from_user.id != event["creator_id"]:
                        await query.answer("❌ Только автор может отменить редактирование", show_alert=False)
                        return

                # Для новых черновиков проверяем, что отменяет автор
                elif query.from_user.id != draft["creator_id"]:
                    await query.answer("❌ Только автор может отменить черновик", show_alert=False)
                    return

                await cancel_draft(update, context)

            elif data.startswith("cancel_edit|"):
                event_id = int(data.split('|')[1])
                event = get_event(context.bot_data["db_path"], event_id)

                if not event:
                    await query.answer("Мероприятие не найдено", show_alert=False)
                    return

                if query.from_user.id != event["creator_id"]:
                    await query.answer("❌ Только автор может отменить редактирование", show_alert=False)
                    return

                # Если проверка пройдена, вызываем cancel_edit
                await cancel_edit(update, context)

            elif data.startswith("cancel_delete|"):
                event_id = int(data.split('|')[1])
                await handle_cancel_delete(query, context, event_id)

            elif data.startswith("cancel_input|"):
                draft_id = int(data.split('|')[1])
                draft = get_draft(context.bot_data["drafts_db_path"], draft_id)

                if not draft:
                    await query.answer("Черновик не найден", show_alert=False)
                    return

                # Для черновиков редактирования проверяем авторство
                if draft.get("event_id"):
                    event = get_event(context.bot_data["db_path"], draft["event_id"])
                    if event and query.from_user.id != event["creator_id"]:
                        await query.answer("❌ Только автор может отменить ввод", show_alert=False)
                        return

                # Для новых черновиков проверяем автор
                elif query.from_user.id != draft["creator_id"]:
                    await query.answer("❌ Только автор может отменить ввод", show_alert=False)
                    return

                await cancel_input(update, context)

            else:
                logger.warning(f"Unknown cancel action: {data}")
                await query.edit_message_text("Неизвестная команда отмены.")

    except Exception as e:
        logger.error(f"Ошибка в обработчике кнопок меню: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Произошла ошибка при обработке команды меню"
        )

def register_menu_button_handler(application):
    application.add_handler(
        CallbackQueryHandler(
            menu_button_handler,
            pattern=r"^(menu_|cancel_)"  # Обрабатываем menu_* и cancel_*
        )
    )