# Используем базовый образ (например, Python)
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

#Создаём папку для базы данных
RUN mkdir -p /data

# Устанавливаем git
RUN apt-get update && apt-get install -y git

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем зависимости (если у вас есть requirements.txt)
RUN pip install -r requirements.txt

# Команда для запуска бота
CMD ["python", "eventcrafterbot.py"]