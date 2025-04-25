# EventCrafter
[![Autotests](https://github.com/ssvasilev/EventCrafter/actions/workflows/tests.yml/badge.svg)](https://github.com/ssvasilev/EventCrafter/actions/workflows/tests.yml)

![image](https://github.com/user-attachments/assets/6f1005d2-7797-4580-a360-c40d48ad9e07)

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
  ![image](https://github.com/user-attachments/assets/072090e4-b3f9-4589-b972-2a5c7f872e6a)

  - Если автор мероприятия начал чат с ботом в личных сообщениях, то сразу после создания мероприятия, бот пришлёт ему сообщение с параметрами мероприятия и ссылками на чат и на конкретное сообщение мероприятия.
    ![image](https://github.com/user-attachments/assets/34a11cc2-cc14-4a6e-8983-bd52baaca3c9)

  
   - При создании мероприятия создаются задачи на уведомления участников за сутки и за 15 минут до мероприятия. Они приходят в личные сообщения, если пользователь начал чат с ботом.
     
   - ![image](https://github.com/user-attachments/assets/27782a9f-8c61-49dc-abfb-a06883990c47)

   - ![image](https://github.com/user-attachments/assets/aac272d2-37eb-4579-95e1-38f8bec1b48e)

  - Количество проводимых одновременно мероприятий не ограничено. Каждый пользователь может параллельно создавать мероприятие, но только по одному в каждом чате.
  - Так же создаётся задача, которая открепит сообщение и удалит мероприятие из базы данных, как только наступит время мероприятия (Сообщение с описанием и участниками останется в чате)
  - Поддерживается редактирование мероприятия (Описание, дата, время, лимит участников, удаление мероприятия)
  
  ![image](https://github.com/user-attachments/assets/33ac8343-9036-4503-9234-3c1de5c2cdf5)
  
  - Присутствует проверка прав, редактировать и удалять мероприятие может только его автор.
  - Отдельной кнопкой присутствует функция, получить сводку мероприятий, в которых участвует пользователь. Отчёт так же приходит в личный чат с ботом.

    ![image](https://github.com/user-attachments/assets/e8cf7e33-710a-471a-aea2-af72e8995ab5)


  - Реализована фукнция шаблонов. Часто проводимые мероприятия можно сохранить как шаблон (через кнопку "Редактировать - Сохранить как шаблон"), что бы потом быстро создавать мерпориятие, используя кнопку "Мои шаблоны". При выборе нужного шаблона, бот попросит ввести только дату, а остальные параметры возьмёт из шаблона.
  - 
![image](https://github.com/user-attachments/assets/b4c306b0-ecda-404b-bdce-1513893ba650)


  - Поддерживается удаление мероприятий. Автор может удалить созданное мероприятие, в таком случае ему в личне сообщения придёт уведомление об успешном удалении.

  ![image](https://github.com/user-attachments/assets/ad40a53d-b3df-4f53-b260-81ed6b505610)

  А всем участникам придёт уведомление об отмене.
  
  ![image](https://github.com/user-attachments/assets/324ea761-eda0-463a-84f1-6ca5103f185a)


  

 

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

WORKDIR /app

# Клонируем ветку
#RUN git clone -b autotest https://github.com/ssvasilev/EventCrafter.git /app

# Клонируем репозиторий
RUN git clone https://github.com/ssvasilev/EventCrafter.git /app

# Устанавливаем зависимости для тестов
RUN pip install --user -r requirements-test.txt

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
    working_dir: /app
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






