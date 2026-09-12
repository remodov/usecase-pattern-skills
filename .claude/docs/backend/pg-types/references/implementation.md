# PostgreSQL Types — реализация

Подход к выбору типов колонок в PostgreSQL для прикладного бэкенда (Java/Spring/jOOQ). Каждое правило имеет код вида `PG-T-NNN` — скилл `ucp-pg-schema-review` цитирует эти коды при ревью DDL и миграций.

Базовый принцип: **тип в схеме — это контракт, который пересмотреть на бою стоит дороже, чем выбрать правильно сразу**. `int → bigint`, `varchar(36) → uuid`, `timestamp → timestamptz` — это многочасовые миграции с локами, которые надо было предотвратить за 30 секунд при первом DDL.

---

## 1. Числа

### `pg-types/pk-bigint-identity` — PK всегда `bigint`. Без вариантов

`integer` (4 байта) кажется достаточным, но через несколько лет одна из таблиц всё равно упрётся в 2.1 млрд, а замена `int → bigint` на бою — это `ALTER TYPE` под `ACCESS EXCLUSIVE` либо expand-contract. Стоимость превентивных 4 байт — нулевая.

### `pg-types/smallint-only-for-short-scale` — `smallint` оправдан только для нумератора фиксированной короткой шкалы

(день недели, год выпуска). Для счётчиков, лимитов, остатков — `integer`/`bigint`.

### `pg-types/pk-bigint-identity` — С PG10+ для авто-id используем `bigint GENERATED ALWAYS AS IDENTITY`, а не `serial`/`bigserial`

`IDENTITY` — стандарт SQL, sequence привязан к колонке через каталог, корректно работает с `pg_dump`, защищён от случайной явной вставки. `BY DEFAULT` — мягкая версия, если бывают legacy-импорты.

### `pg-types/money-is-numeric` — Деньги, проценты, налоги, тарифы — `numeric(p, s)`. Никогда `real`/`double precision`/`float`

Двоичная плавающая точка не представляет десятичные дроби точно (`0.1 + 0.2 ≠ 0.3`). Для финансов — `numeric(15, 2)` (валюты), `numeric(20, 8)` (курсы), `numeric(5, 2) CHECK BETWEEN 0 AND 100` (проценты). Альтернатива «копейки в `bigint`» рабочая, но требует дисциплины во всём коде.

### `pg-types/money-is-numeric` — Тип `money` PostgreSQL не использовать

Привязан к глобальной локали сервера, не хранит код валюты. `numeric` + отдельная `currency char(3)`.

### `pg-types/float-only-for-inexact` — `real`/`double precision` — только когда уместна неточность:

временные ряды метрик, ML-фичи, embeddings, физические величины. Для денежных и учётных полей — никогда.

### `pg-types/boolean-is-boolean` — Boolean — это `boolean`

Не `smallint 0/1`, не `varchar('Y'/'N')`, не `char(1)` с `CHECK`.

---

## 2. Строки

### `pg-types/text-by-default` — Без бизнес-причины ограничивать длину — `text`

В PostgreSQL `text` и `varchar(n)` хранятся одинаково (TOAST для длинных), скорость одинаковая. `varchar(255)` — наследие MySQL/Oracle, в PG это просто `text` с лишним `CHECK`.

### `pg-types/varchar-when-domain-rule` — Длину `varchar(n)` ставим, когда она — доменное правило

`varchar(15)` для E.164 phone, `char(2)` для ISO-страны, `char(3)` для валюты, `varchar(12)` для ИНН. «Просто пусть будет ограничение» — антипаттерн.

### `pg-types/varchar-when-domain-rule` — `char(n)` оправдан только для строго фиксированной длины из стандарта

(ISO-страна, валюта). Иначе паддинг пробелами создаёт сюрпризы при `LIKE`, `=`, `length()`.

### `pg-types/case-insensitive-via-citext` — Case-insensitive поля — `citext` либо functional unique index `lower(...)`. Не «`LOWER()` в каждом запросе»

Для логинов, email, тегов.

### `pg-types/utf8-cluster` — Кластер должен быть в `UTF8`

`SQL_ASCII` — наследие, эмодзи и не-ASCII в данных будут ломаться.

### `pg-types/no-premature-column-split` — Не делите таблицу на «горячие короткие колонки» и «редкий длинный текст» преждевременно — TOAST уже это делает

Делите, только если измерения показывают узкое место.

---

## 3. Время

### `pg-types/business-time-is-timestamptz` — Бизнес-время — всегда `timestamptz`. Никогда `timestamp`/`timestamp without time zone`

`timestamptz` хранит UTC и конвертирует в зону сессии на I/O-границе. `timestamp` без зоны — «локальное время непонятно где», через год никто не помнит, в какой зоне был сервер.

### `pg-types/time-mapping-keeps-zone` — На Java-стороне `timestamptz` ↔ `Instant` или `OffsetDateTime`. `LocalDateTime` — никогда

`LocalDateTime` теряет зону → один и тот же запрос на UTC-сервере и MSK-ноуте даёт разные результаты.

| Колонка PG | Java тип |
|---|---|
| `timestamptz` | `Instant` (рекомендуется) или `OffsetDateTime` |
| `timestamp` (без TZ) | `LocalDateTime` (но сам тип нежелателен) |
| `date` | `LocalDate` |
| `time` | `LocalTime` |

### `pg-types/business-time-is-timestamptz` — `timestamp` (без TZ) допустим только для «локального времени без момента»:

расписание открытия магазина, локальное время вылета. Зона хранится отдельной колонкой.

### `pg-types/now-vs-clock-timestamp` — Различай `now()`/`transaction_timestamp()` (время начала транзакции) vs `clock_timestamp()` (момент вызова) vs `statement_timestamp()` (начало statement)

Для `created_at` обычно `now()`. Для замеров «сколько шёл цикл» — `clock_timestamp()`.

### `pg-types/time-through-clock-service` — Время в коде — через источник времени сервиса (`DateTimeUtil` со сменным `Clock` или `DateTimeService`-бин) с подменой в тестах. Не `Instant.now()` напрямую

См. также `test-strategy/tests-are-synchronous-and-deterministic` / `test-strategy/tests-are-synchronous-and-deterministic`. `DEFAULT now()` приемлемо для аудита, но не для проверяемых сценариев.

### `pg-types/intervals-not-magic-seconds` — В SQL для смещений — `INTERVAL`, не магические числа секунд

`now() - interval '15 minutes'`, не `now() - 900 * interval '1 second'`.

---

## 4. UUID и идентификаторы

### `pg-types/uuid-is-uuid-type` — UUID хранится в типе `uuid`. Никогда `varchar(36)`/`char(36)`/`text`

16 vs 36+ байт; type-safety на вставке; нормализация регистра; быстрее на сравнении.

### `pg-types/uuid-v7-for-keys` — Для PK / FK берём UUID v7, не v4

v4 случаен → каждая вставка идёт в случайную страницу btree → больше random IO, плохая упаковка. v7 = 48-битный timestamp + 74 случайных бита → последовательные вставки рядом в индексе. Тип тот же `uuid`, меняется только генератор. На таблицах от 50–100M строк разница 2–5x в скорости вставки.

### `pg-types/uuid-v7-for-keys` — Генерируем UUID v7 на стороне приложения

(`com.github.f4b6a3.uuid.UuidCreator.getTimeOrderedEpoch()`), если PG <18 или нужен id до commit. На PG18+ — встроенная `uuidv7()`.

### `pg-types/uuid-only-when-justified` — `bigint IDENTITY` дешевле и быстрее. UUID — когда нужен по делу:

распределённые сервисы без координации, публичные URL/ссылки в письмах, id нужен до commit. Иначе — `bigint`.

### `pg-types/index-fk-under-uuid-pk` — При UUID-PK обязателен индекс по FK в дочерних таблицах

PostgreSQL не строит его автоматически. Без — `DELETE` родителя уйдёт в seq-scan child.

---

## 5. Enum, boolean и перечисления

### `pg-types/boolean-is-boolean` — Boolean — `boolean`

(Дубликат `pg-types/boolean-is-boolean` для удобства поиска в этом разделе.)

### `pg-types/enum-vs-reference-table` — Правила выбора между PG `ENUM` / reference table / `CHECK IN`:

| Случай | Выбор |
|---|---|
| Список известен, редко меняется, без атрибутов | `ENUM` |
| Список растёт/переименовывается, нужны атрибуты | reference table |
| Простой технический список ≤7 значений | `CHECK IN (...)` |
| Часто меняется в админке | reference table |

Статусы доменных сущностей (`order_status`) — обычно reference table, потому что приобретают атрибуты со временем (`is_terminal`, `sort_order`, `description`).

### `pg-types/typed-enum-in-code` — В Java — `enum`, не `String`

`@Enumerated(EnumType.STRING)` для JPA или typed converter для jOOQ.

---

## 6. JSONB

### `pg-types/jsonb-not-json` — Всегда `jsonb`. `json` — почти никогда

`jsonb` хранит разобранное двоичное представление, индексируется через GIN, быстрее на доступе. `json` оправдан только для бит-в-бит сохранения исходного документа (audit log с законным требованием неизменности).

### `pg-types/jsonb-for-peripheral-attributes` — Если по полю регулярно фильтруют, сортируют или джойнят — это колонка, не JSON-ключ

`jsonb` — для **полиморфных, опциональных, редко-фильтруемых** атрибутов: audit payload, конфиги интеграций, специфичные атрибуты товара. «Гибкая схема, мы потом разберёмся» = «через год реляционная БД, которая делает вид, что она document store».

### `pg-types/jsonb-for-peripheral-attributes` — Хорошие кейсы JSONB:

payload события (полиморфен по `event_type`), атрибуты товара по категории (`{size, material}` vs `{power_w, voltage}`), конфиг канала интеграции (`SMTP {host,port}` vs `Telegram {bot_token,chat_id}`), кеш-копия данных из внешнего API.

### `pg-types/jsonb-for-peripheral-attributes` — Плохие кейсы:

все основные поля сущности в одном `data jsonb`; поле, по которому ищут, лежит в JSONB; «чтобы не писать миграции».

### `pg-types/jsonb-index-matches-query` — Базовые операторы:
- `->` доступ по ключу/индексу (возвращает `jsonb`)
- `->>` доступ по ключу (возвращает `text`)
- `#>` / `#>>` — доступ по пути
- `@>` содержит (subset)
- `?` / `?|` / `?&` — наличие ключа

### `pg-types/jsonb-index-matches-query` — Для поиска `@>` — GIN-индекс с `jsonb_path_ops`

(меньше и быстрее дефолтного GIN, но поддерживает только `@>`).

### `pg-types/jsonb-index-matches-query` — Для запроса по конкретному JSONB-ключу — functional index, не GIN:

`CREATE INDEX ix_event_type ON event_log ((payload ->> 'event_type'))`. Дешевле GIN.

### `pg-types/no-binary-in-jsonb` — Не пишите в JSONB бинарь, большие тексты, base64

Бинарь — `bytea`, текст — `text`.

---

## 7. Массивы и range

### `pg-types/array-for-simple-scalars` — Массив уместен только для простых скаляров без идентичности и без атрибутов:

теги, локали, флаги. До десятков элементов на запись.

### `pg-types/array-for-simple-scalars` — Если у элементов есть атрибуты или они независимо обновляются — отдельная таблица с FK, не массив

`jsonb[]` для строк заказа — антипаттерн. Это таблица «положенная на бок».

### `pg-types/range-for-intervals` — Когда сущность семантически — это интервал, range-тип

`tstzrange`/`daterange`/`int4range` для тарифов с периодом действия, бронирований, цен с историей.

### `pg-types/exclude-constraint-for-overlap` — Для требования «интервалы не пересекаются» — `EXCLUDE` constraint, не код приложения
```sql
CREATE EXTENSION btree_gist;
EXCLUDE USING gist (room_id WITH =, period WITH &&)
```
Application-level lock не защищает от race; `EXCLUDE` защищает.

### `pg-types/range-for-intervals` — По умолчанию range с границей `[)` — включая нижнюю, исключая верхнюю

Стандарт для дат/интервалов: иначе «бронь 14:00-16:00» и «16:00-18:00» считаются пересекающимися.

---

## 8. Антипаттерны (сводный список)

`pg-types/text-by-default` `varchar(255)` по привычке — берите `text` или `varchar(n)` по доменному правилу.

`pg-types/business-time-is-timestamptz` `timestamp without time zone` для бизнес-времени — берите `timestamptz`.

`pg-types/uuid-is-uuid-type` `varchar(36)` для UUID — берите тип `uuid`.

`pg-types/money-is-numeric` `float`/`real`/`double precision` для денег — берите `numeric(p, s)`.

`pg-types/pk-bigint-identity` `serial`/`bigserial` в новой схеме — берите `bigint GENERATED ALWAYS AS IDENTITY`.

`pg-types/boolean-is-boolean` `smallint 0/1` или `char(1) Y/N` вместо boolean — берите `boolean`.

`pg-types/enum-vs-reference-table` PG `ENUM` для часто-меняющегося списка — берите reference table.

`pg-types/jsonb-for-peripheral-attributes` JSONB как «гибкая схема» для основных полей — выносите в колонки.

`pg-types/array-for-simple-scalars` Массив там, где должна быть отдельная таблица — заведите таблицу с FK.

`pg-types/range-for-intervals` Две колонки `valid_from`/`valid_to` вместо range-типа — берите `tstzrange` + `EXCLUDE`.

`pg-types/money-is-numeric` Тип `money` — берите `numeric` + `currency char(3)`.

`pg-types/time-mapping-keeps-zone` `LocalDateTime` в Java для `timestamptz` — берите `Instant`/`OffsetDateTime`.

`pg-types/time-through-clock-service` `Instant.now()` напрямую в коде — заведите источник времени (`DateTimeUtil` или `DateTimeService`) и подменяйте его в тестах.

`pg-types/uuid-v7-for-keys` UUID v4 для PK — берите v7.

---

## Чек-лист на ревью схемы / миграции

- [ ] Все id — `bigint GENERATED ALWAYS AS IDENTITY` или `uuid` (v7)
- [ ] Все «когда что-то произошло» — `timestamptz`, не `timestamp`
- [ ] Все деньги — `numeric(p, s)`, не `float`
- [ ] Все строки без бизнес-длины — `text`, не `varchar(255)`
- [ ] UUID — тип `uuid`, не `varchar(36)`
- [ ] Boolean — `boolean`, не `smallint`/`char(1)`
- [ ] Enum c будущим ростом — reference table, не `ENUM`
- [ ] JSONB — только полиморфные/опциональные поля, не «горячие»
- [ ] Массивы — только простые скаляры
- [ ] Интервалы — range-тип с `EXCLUDE` для непересечения
- [ ] На Java — `Instant`/`OffsetDateTime` для `timestamptz`, `enum` для перечислений
- [ ] Время в коде через источник времени сервиса, не `now()`
