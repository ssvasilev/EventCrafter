import importlib.metadata
from telegram import Update
from telegram.ext import ContextTypes


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        version_text = importlib.metadata.version("eventcrafter")
        await update.message.reply_text(
            f"Версия бота: {version_text}",
            reply_to_message_id=update.message.message_id
        )
    except Exception as e:
        await update.message.reply_text(
            "Не удалось определить версию бота",
            reply_to_message_id=update.message.message_id
        )
        print(f"Error getting version: {e}")