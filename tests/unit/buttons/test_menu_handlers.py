import pytest
from telegram import User, CallbackQuery, Update, Chat, Message
from telegram.ext import CallbackContext

from src.buttons.menu_button_handlers import menu_button_handler


@pytest.mark.asyncio
async def test_menu_handler_create_event(app):
    user = User(1, "Test", False)
    chat = Chat(1, "group")
    message = Message(1, None, chat, text="/start")
    query = CallbackQuery(
        id=1,
        from_user=user,
        chat_instance="test_chat_instance",
        message=message,
        data="menu_create_event"
    )
    update = Update(1, callback_query=query)

    await menu_button_handler(update, CallbackContext(app))

    # Проверяем, что обработчик был вызван
    # (здесь можно добавить моки для проверки вызовов)