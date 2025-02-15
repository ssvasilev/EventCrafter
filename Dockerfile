# Используем базовый образ (например, Python)
FROM python:3.9-slim

# Устанавливаем git
RUN apt-get update && apt-get install -y git

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости (если у вас есть requirements.txt)
RUN pip install -r requirements.txt

# Команда для запуска бота
CMD ["python", "eventcrafterbot.py"]