# EventCrafter
[![Autotests](https://github.com/ssvasilev/EventCrafter/actions/workflows/tests.yml/badge.svg)](https://github.com/ssvasilev/EventCrafter/actions/workflows/tests.yml)

![main_menu](https://github.com/user-attachments/assets/d463b03d-9352-4d34-96a7-cf97e78311ad)



Бот для организации мероприятий в небольших групповых чатах telegram. 

Подходит для организации онлайн и оффлайн встреч. 

Готов к запуску внутри docker-контейнера. 

Использует БД SQLite для хранения информации.


Функционал:
  - Создание меропрития с указанием описания, даты, времени, лимита участников (0 - бесконечный лимит)
  - Участники чата могут нажать кнопку "Участвую" для внесения себя в список участников, если есть ещё свободное место в лимите. Если нет, участник добавляется в резерв.
  - Когда кто-то из участников нажмёт "Не участвую", он переместится в список "Отказавшиеся", а первый из резерва займёт его место в участниках.
  - Время до мероприятия обновляется только при обращении к боту.
  - Бот поддерживает ссылки только в супер-группы и общие чаты. Ссылки на приватные чаты не поддерживаются приватностью самого телеграмма, будет выводиться ошибка: "К сожалению, у Вас нет доступа к этому сообщению: Вы не участник чата, где оно опубликовано"
  - При создании мероприятия закрепляет сообщение с ним в чате

![event](https://github.com/user-attachments/assets/7983bc06-a1b8-443f-9248-d7266de919fc)



  - Если автор мероприятия начал чат с ботом в личных сообщениях, то сразу после создания мероприятия, бот пришлёт ему сообщение с параметрами мероприятия и ссылками на чат и на конкретное сообщение мероприятия.
    
![event_create](https://github.com/user-attachments/assets/44c701ed-a9b3-456c-86c0-91f0bbe4ab1c)

  
   - При создании мероприятия создаются задачи на уведомления участников за сутки и за 15 минут до мероприятия. Они приходят в личные сообщения, если пользователь начал чат с ботом.
     
![notification_1day](https://github.com/user-attachments/assets/1f44cc16-e4e0-4f1b-8957-a5d5cd0fff81)

![notification_15min](https://github.com/user-attachments/assets/fcaa1232-5e8b-47c1-a2e9-9ce442ea781f)


  - Количество проводимых одновременно мероприятий не ограничено. Каждый пользователь может параллельно создавать мероприятие, но только по одному в каждом чате.
  - Так же создаётся задача, которая открепит сообщение и удалит мероприятие из базы данных, как только наступит время мероприятия (Сообщение с описанием и участниками останется в чате)
  - Поддерживается редактирование мероприятия (Описание, дата, время, лимит участников, удаление мероприятия)
  

![edit](https://github.com/user-attachments/assets/0f893317-8f29-4119-8b68-64116321453f)

  - Присутствует проверка прав, редактировать и удалять мероприятие может только его автор.
  - Отдельной кнопкой присутствует функция, позволяющая получить сводку мероприятий, в которых участвует пользователь. Отчёт так же приходит в личный чат с ботом.

![my_events](https://github.com/user-attachments/assets/65510b7b-1d0d-4fbf-83f2-bf6d5d816ad7)



  - Реализована фукнция шаблонов. Часто проводимые мероприятия можно сохранить как шаблон (через кнопку "Редактировать - Сохранить как шаблон"), что бы потом быстро создавать мерпориятие, используя кнопку "Мои шаблоны". При выборе нужного шаблона, бот попросит ввести только дату, а остальные параметры возьмёт из шаблона.

![template](https://github.com/user-attachments/assets/e3bbde36-809f-420f-ad79-620077cb5399)


  - Поддерживается удаление мероприятий. Автор может удалить созданное мероприятие, в таком случае ему в личне сообщения придёт уведомление об успешном удалении.

![event_delete](https://github.com/user-attachments/assets/83e6942a-3794-4fd6-a18e-9b3834ee4973)

  А всем участникам придёт уведомление об отмене.
  
![event_cancel](https://github.com/user-attachments/assets/88a31706-b1d3-4435-8e10-de4256d40157)

  

 

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
![bot_settings_1](https://github.com/user-attachments/assets/8a437444-1d5a-4188-9706-8ea79674428b)

![bot_settings_2](https://github.com/user-attachments/assets/3560916c-7a9b-4a7d-84ee-66f67d60be2d)

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
CMD ["pytest", "tests/", "-v", "--log-cli-level=INFO", "--tb=short"]

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






