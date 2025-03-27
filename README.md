# EventCrafter
Бот для организации мероприятий в небольших групповых чатах telegram. 

Подходит для организации онлайн и оффлайн встреч. 

Готов к запуску внутри docker-контейнера. 

Использует БД SQLite для хранения информации.

Функционал:
  - Создание меропрития с указанием описания, даты, времени, лимита участников (0 - бесконечный лимит)
  - Участники чата могут нажать кнопку "Участвую" для внесения себя в список участников, если есть ещё свободное место в лимите. Если нет, участник добавляется в резерв.
  - Когда кто-то из участников нажмёт "Не участвую", он переместится в список "Отказавшиеся", а первый из резерва займёт его место в участниках.
  - Время до мероприятия обновляется только при обращении к боту.
  - При создании мероприятия закрепляет сообщение с ним в чате
  ![image](https://github.com/user-attachments/assets/891c48ac-f32a-4584-bcfb-196c212c7124)
  
  - При создании мероприятия создаются задачи на уведомления участников за сутки и за час до мероприятия.
  - Поддерживается ведение сразу нескольких мероприятий одновременно.
  - Так же создаётся задача, которая открепит сообщение и удалит мероприятие из базы данных, как только наступит время мероприятия (Сообщение с описанием и участниками останется в чате)
  - Поддерживается редактирование мероприятия (Описание, дата, время, лимит участников, удаление мероприятия)
  
  ![image](https://github.com/user-attachments/assets/d71ba3ac-1d21-4dfe-bcfc-40ae33154e3e)
  
  - Присутствует проверка прав, редактировать и удалять мероприятие может только его автор.
  - Уведомления о мероприятии приходят только в личный чат с ботом, что бы бот смог их отправлять, необходимо самостоятельно начать общение с ботом.
  - Отдельной кнопкой присутствует функция, получить сводку мероприятий, в которых участвует пользователь. Отчёт так же приходит в личный чат с ботом.
  
  ![image](https://github.com/user-attachments/assets/7c06714c-6c03-4c8f-9a1e-7ef5768c7d6c)

## Установка:
1. Для начала необходимо создать нового бота у официального telegram-бота [@BotFather](https://telegram.me/BotFather). Придумываем имя и сохраняем к себе токен бота.
2. Производим следующие настройки в разделе Bot Settings:
   
       Allow Groups? - Enable
   
   Group Admin Rights:
       
        ✔️ Delete messages
    
        ✔️ Pin messages
    
        ✔️ Manage Topics
    
        ✔️ Manage chat
       
   Channel Admin Rights:
    
        ✔️ Post in the channel
        
        ✔️ Edit messages of other users
        
        ✔️ Delete messages
        
        ✔️ Manage channel
![image](https://github.com/user-attachments/assets/0059c9b5-5384-47e6-b5db-8b242a02e611)
![image](https://github.com/user-attachments/assets/e5003b0e-d3be-4a50-bf19-933e4f34951e)

3. На сервере с Docker, создаём два файла:

Dockerfile     
```Dockerfile
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

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем зависимости для тестов
RUN pip install --user -r requirements-test.txt

# Этап для запуска тестов
FROM builder as tester
CMD ["sh", "-c", "python -m pytest -v > /app/test_results/test_results.log 2>&1 || echo 'Tests failed'"]

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

# Команда для запуска бота
CMD ["python", "eventcrafterbot.py"]
```
docker-compose.yml
```docker-compose.yml

version: "3.8"

services:
  eventcrafter:
    build: 
      context: .
      target: production
    container_name: eventcrafter
    restart: unless-stopped
    environment:
      - BOT_TOKEN={{Токен бота из пункта 1}}
      - TIMEZONE=Europe/Moscow
      - DATABASE_URL=sqlite+aiosqlite:////data/eventcrafter.db
    volumes:
      - ./data:/data
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  tests:
    build:
      context: .
      target: tester
    container_name: eventcrafter_tests
    environment:
      - DATABASE_URL=sqlite+aiosqlite:////tmp/test.db
    volumes:
      - ./test_results:/app/test_results
    restart: "no"


```
## Автотесты:

Система автотестов реализована путём альтернативной сборки одноразового контейнера.

_Команда для сборки тестового контейнера и запуска тестов:_
```
docker compose build tests && docker compose run --rm -v $(pwd)/test_results:/app/test_results tests
```
для упрощения можно выполнить скрипт:

```
./run_tests.sh
```
_Запуск тестов без логов_
```
docker compose run --rm tests
```

## Запуск
_Команда для сборки рабочего контейнера:_
```
docker compose build eventcrafter
```

_Команда для запуска бота:_
```
docker compose up -d eventcrafter
```

Бот готов к работе.






