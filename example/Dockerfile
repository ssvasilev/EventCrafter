# Используем базовый образ (например, Python)
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

#Создаём папку для базы данных
RUN mkdir -p /data

# Устанавливаем git
RUN apt-get update && apt-get install -y git

# Устанавливаем необходимые пакеты локализации
RUN apt-get update && apt-get install -y locales git

# Генерируем локаль ru_RU.UTF-8
RUN sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

# Устанавливаем локаль по умолчанию
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем зависимости (если есть requirements.txt и requirements-test.txt)
RUN pip install -r requirements.txt
RUN pip install -r requirements-test.txt

FROM builder as tester
COPY --from=builder /app /app
WORKDIR /app

RUN pytest tests/integration/ -v --log-cli-level=INFO

# Команда для запуска бота
CMD ["python", "eventcrafterbot.py"]