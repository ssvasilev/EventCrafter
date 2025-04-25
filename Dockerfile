# Этап сборки и тестирования
FROM python:3.10-slim as builder

# Устанавливаем необходимые пакеты
RUN apt-get update && \
    apt-get install -y git locales && \
    sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen ru_RU.UTF-8

# Настройка локали
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8

# Устанавливаем рабочую директорию
WORKDIR /app

# Клонируем ветку
#RUN git clone -b fix-mention-bot2 https://github.com/ssvasilev/EventCrafter.git /app

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем зависимости для тестов
RUN pip install --user -r requirements-test.txt

# Добавляем путь к локальным бинарям pip
ENV PATH=/root/.local/bin:$PATH

# Этап для запуска тестов
FROM builder as tester

WORKDIR /app

# Создаем директорию для результатов
RUN mkdir -p /app/test_results

# Команда для запуска тестов
CMD ["sh", "-c", "cd /app && python -m pytest tests/ -v > test_results/test_results.log 2>&1 || echo 'Tests failed'"]

# Финальный этап
FROM python:3.10-slim as production

# Устанавливаем локали в финальном образе
RUN apt-get update && \
    apt-get install -y locales && \
    sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen ru_RU.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

# Настройка локали
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8

WORKDIR /app

# Копируем только необходимые файлы из builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /app /app

# Устанавливаем только production зависимости
RUN pip install -r requirements.txt && \
    mkdir -p /data

# Устанавливаем PATH для пользовательских скриптов Python
ENV PATH=/root/.local/bin:$PATH

#Копируем файл версии
COPY --from=builder /app/VERSION /app/VERSION

CMD ["python", "eventcrafterbot.py"]