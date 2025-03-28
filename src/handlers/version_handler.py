from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Ищем файл VERSION в текущей рабочей директории (/app в контейнере)
        version_path = Path("/app/VERSION")

        if not version_path.exists():
            await update.message.reply_text(
                f"Файл VERSION не найден по пути: {version_path}",
                reply_to_message_id=update.message.message_id
            )
            return

        with open(version_path, 'r') as f:
            version_text = f.read().strip()

        await update.message.reply_text(
            f"📌 Версия бота: {version_text}",
            reply_to_message_id=update.message.message_id
        )

    except Exception as e:
        print(f"Ошибка при чтении версии: {e}")
        await update.message.reply_text(
            f"⚠ Ошибка при чтении версии: {e}",
            reply_to_message_id=update.message.message_id
        )