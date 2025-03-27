# Используем базовый образ (например, Python)
FROM python:3.10-slim as builder

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаём папку для базы данных
RUN mkdir -p /data

# Устанавливаем необходимые пакеты
RUN apt-get update && \
    apt-get install -y git locales && \
    sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем локаль
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем основные зависимости
RUN pip install --no-cache-dir -r requirements.txt


# Стадия для тестирования
FROM python:3.10-slim as tester
WORKDIR /app

# Копируем из builder
COPY --from=builder /app /app
COPY --from=builder /data /data
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Устанавливаем тестовые зависимости
RUN pip install --no-cache-dir -r requirements-test.txt

# Устанавливаем переменные окружения для тестов
ENV PYTHONPATH=/app
ENV DATABASE_URL=sqlite+aiosqlite:////data/test.db

# Запуск тестов
CMD ["python", "-m", "pytest", "tests/integration/", "-v", "--log-cli-level=INFO"]

# Основная стадия
FROM python:3.10-slim
WORKDIR /app

# Копируем из builder
COPY --from=builder /app /app
COPY --from=builder /data /data

# Устанавливаем переменные окружения
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8
ENV DATABASE_URL=sqlite+aiosqlite:////data/eventcrafter.db

# Команда для запуска бота
CMD ["python", "eventcrafterbot.py"]