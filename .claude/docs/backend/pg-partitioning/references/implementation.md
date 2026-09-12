# PostgreSQL Partitioning — реализация

Декларативное партиционирование PG10+ — когда оправдано, как выбрать ключ, как управлять. Кодами `PG-P-NNN` ссылается скилл `ucp-pg-schema-review`.

Партиционирование — инструмент для **больших** таблиц. Для маленьких overhead больше выигрыша. Главный практический выигрыш — управляемость (мгновенный `DROP` старых данных, autovacuum per-партиция, индексы на одной партиции).

---

## 1. Когда оправдано

### `pg-partitioning/partition-only-when-justified` — Партиционируй, если выполнено хотя бы одно:
- Таблица > 50 GB / 100M строк и растёт.
- Time-series (события, метрики, логи).
- Старые данные регулярно удаляются по сроку (`DROP TABLE` партиции — мгновенно, `DELETE` — мучительно).
- Multi-tenant с несколькими очень крупными тенантами.
- autovacuum не справляется на текущей таблице.

### `pg-partitioning/partition-only-when-justified` — Партиционирование избыточно, если:
- Таблица < 10 GB.
- Запросы редко включают potential partition key в `WHERE`.
- Нет данных для дропа по сроку.

## 2. Базовый паттерн

### `pg-partitioning/pk-includes-partition-key` — PK партиционированной таблицы обязан включать ключ партиционирования
```sql
CREATE TABLE event_log (
    id          bigint GENERATED ALWAYS AS IDENTITY,
    occurred_at timestamptz NOT NULL,
    payload     jsonb NOT NULL,
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);
```

## 3. Три типа

### `pg-partitioning/partition-type-matches-data` — RANGE — самый частый

Time-series, архивы по году/месяцу.

### `pg-partitioning/partition-type-matches-data` — LIST — фиксированный набор категорий

Регионы (`'EU'`, `'US'`, `'APAC'`).

### `pg-partitioning/partition-type-matches-data` — HASH — равномерное распределение без естественного ключа

Не даёт partition pruning по диапазону, помогает только при `WHERE key = ?` (одно значение → одна партиция).

### `pg-partitioning/partition-type-matches-data` — HASH-партиционирование оправдано редко

Чаще «равномерно распределить» решается одной таблицей с правильными индексами.

## 4. Выбор ключа

### `pg-partitioning/key-present-in-queries` — Ключ должен быть в `WHERE` почти всех запросов

Иначе partition pruning не работает, партиции — просто куча таблиц.

Правильно: `event_log PARTITION BY occurred_at` — все запросы фильтруют по дате. Multi-tenant `PARTITION BY tenant_id` — каждый запрос в контексте одного тенанта.

Неправильно: `orders PARTITION BY status`, если запросы ходят по `customer_id`.

### `pg-partitioning/key-present-in-queries` — Если запросы делятся на две группы (по `customer_id` И по `created_at`)

— выбирай тот, что чаще в самых тяжёлых запросах. Композитный partition key возможен, но обычно overkill.

### `pg-partitioning/balanced-partitions` — Распределение нагрузки

Партиции должны быть сравнимого размера. Если 99% данных в одной — это не партиционирование. Проверь распределение перед выбором.

## 5. Размер партиции

### `pg-partitioning/partition-size-range` — Целевой размер — 1–50 GB

Больше — autovacuum снова тормозит. Меньше — overhead планировщика.

Для time-series:
- Помесячно — умеренная нагрузка.
- Понедельно — средняя.
- Подневно — высокая (сотни миллионов в день).

### `pg-partitioning/partition-size-range` — Не делай сотни мелких партиций

> 1000 — планировщик тормозит. > 10000 — кластер еле дышит.

## 6. Управление

### `pg-partitioning/create-partitions-ahead` — Создание новых партиций — заранее, на месяц-два вперёд

Иначе `INSERT` без подходящей партиции упадёт. Ручной `cron` или расширение `pg_partman`:

```sql
SELECT partman.create_parent(
    p_parent_table => 'public.event_log',
    p_control      => 'occurred_at',
    p_type         => 'native',
    p_interval     => '1 month',
    p_premake      => 4
);
```

### `pg-partitioning/drop-partition-not-delete` — Удаление старых данных — `DROP TABLE` партиции, не `DELETE`

Мгновенно, без MVCC-следов и WAL-роста.

### `pg-partitioning/drop-partition-not-delete` — `DETACH PARTITION` отделяет партицию, не удаляя данные

Полезно для переноса в холодное хранилище. PG14+: `DETACH ... CONCURRENTLY` без блокировки родителя.

## 7. Индексы на партициях

### `pg-partitioning/indexes-on-parent` — `CREATE INDEX` на родительской таблице автоматически создаёт индексы на каждой партиции

Удобно, но можно partial per-партиция, если нагрузка отличается.

### `pg-partitioning/pk-includes-partition-key` — Уникальные индексы должны включать ключ партиционирования

Уникальность гарантируется только в пределах партиции — для глобальной уникальности нужна отдельная таблица справочника или application-level.

## 8. Foreign Keys

### `pg-partitioning/foreign-key-directions` — Partitioned table → FK на обычную таблицу — работает
```sql
CREATE TABLE event_log (
    customer_id bigint NOT NULL REFERENCES customer(id),
    ...
) PARTITION BY RANGE (occurred_at);
```

### `pg-partitioning/foreign-key-directions` — Обратное (обычная → partitioned) — работает с PG12+

Партиция-источник должна иметь PK с ключом партиционирования (`pg-partitioning/pk-includes-partition-key`).

## 9. Миграция существующей таблицы

### `pg-partitioning/migrate-via-shadow-table` — Прямого `ALTER TABLE ... PARTITION BY` нет

Миграция через теневую таблицу:
1. `CREATE TABLE event_log_new (LIKE event_log INCLUDING ALL) PARTITION BY RANGE (occurred_at)`.
2. Создать партиции на покрытие диапазона.
3. `INSERT INTO event_log_new SELECT FROM event_log` (батчами для большой).
4. `RENAME` в одной транзакции.

### `pg-partitioning/migrate-via-shadow-table` — На таблице 500 GB — несколько часов копирования + место под обе версии

Планируй заранее.

## 10. Антипаттерны

`pg-partitioning/partition-only-when-justified` Партиционировать малые таблицы. < 10 GB — overhead больше выигрыша.

`pg-partitioning/key-present-in-queries` Партиционировать по полю, которого нет в большинстве `WHERE`.

`pg-partitioning/balanced-partitions` Multi-tenant per-tenant партиции на сотнях тенантов — autovacuum и pg_class распухают. Лучше row-level security или partial indexes.

`pg-partitioning/partition-size-range` Множество мелких партиций (по часам, минутам) — > 1000 партиций тормозит планировщик.

`pg-partitioning/create-partitions-ahead` Забыть создать партицию заранее — `INSERT` упадёт.

`pg-partitioning/partition-key-immutable` `UPDATE` поля, по которому идёт партиционирование — PG переместит строку (`DELETE + INSERT`), большой WAL. Делай partition key immutable.

---

## Чек-лист на ревью

- [ ] Таблица > 50 GB или time-series с дропом старых данных?
- [ ] Ключ партиционирования в `WHERE` большинства запросов?
- [ ] Распределение по ключу равномерное (нет «99% в одном»)?
- [ ] Размер партиции — 1–50 GB?
- [ ] Партиций < 1000?
- [ ] PK включает ключ партиционирования?
- [ ] Есть автоматическое создание новых партиций (`pg_partman` или cron)?
- [ ] Удаление старых данных — через `DROP TABLE` партиции, не `DELETE`?
- [ ] Поле partition key не обновляется в типичных операциях?
