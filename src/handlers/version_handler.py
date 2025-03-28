from pathlib import Path
from telegram import Update
from telegram.ext import ContextTypes


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Путь к файлу VERSION (на два уровня выше от текущего файла)
        version_path = Path(__file__).parent.parent / "VERSION"

        # Читаем версию из файла
        with open(version_path, 'r') as f:
            version_text = f.read().strip()

        await update.message.reply_text(
            f"📌 Версия бота: {version_text}",
            reply_to_message_id=update.message.message_id
        )

    except FileNotFoundError:
        await update.message.reply_text(
            "Файл с версией не найден",
            reply_to_message_id=update.message.message_id
        )
    except Exception as e:
        print(f"Ошибка при чтении версии: {e}")
        await update.message.reply_text(
            "⚠ Не удалось определить версию",
            reply_to_message_id=update.message.message_id
        )