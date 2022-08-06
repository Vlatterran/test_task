Инструкция по запуску:
1. Клонировать репозиторий
2. Установить все необходимые зависимости

    ``pip install -r requirements.txt``
3. Запустить код

    ``python main.py <Google Spred Sheet ID> <Dadabase URL>``
   
   При первом будет выведена ссылка ждя предоставления утилите доступа чтение гугл-диска и гугл-таблиц  

> Дополнительные параметры запуска мож*но посмотреть с помощью ``python main.py --help``

> [Тестовая таблица](https://docs.google.com/spreadsheets/d/1Tgmkt3XjGCeGgoUURNJKAFjQDfOzOsTZpaeWGkRx3NQ/edit#gid=0)

Код использует таблицу order. Если таблица отсутствует, код автоматически создаст её

Таблица order создаётся следующим SQL скриптом (сгенерирован автоматически)
   
   ```
   create table "order"
   (
       number        integer        not null
           primary key,
       cost_usd      numeric(10, 2) not null,
       cost_rub      numeric(10, 2) not null,
       delivery_date date           not null
   );
   
   comment on column "order".number is 'заказ №';
   
   comment on column "order".cost_usd is 'стоимость,$';
   
   comment on column "order".cost_rub is 'стоимость,₽';
   
   comment on column "order".delivery_date is 'срок поставки';
   
   alter table "order"
       owner to postgres;

