# PostgreSQL Migrations Style Guide

Правила миграций PG без даунтайма: expand-contract, ACCESS EXCLUSIVE-операции, CONCURRENTLY, CHECK NOT VALID. Кодами `PG-M-NNN` ссылается скилл `ucp-pg-migration-review`.

Базовый принцип: **`ALTER TABLE` берёт `ACCESS EXCLUSIVE` lock и блокирует ВСЁ — INSERT, UPDATE, SELECT.** Любое breaking-изменение режется на 3+ релиза с принципом N-1 (миграция совместима с предыдущей версией кода).

---

## 1. Что breaking, что нет

### `PG-M-001` — Breaking change — операция, ломающая старую версию кода

Не-breaking (один релиз):
- `ADD COLUMN ... NULL` (PG11+ с `DEFAULT` тоже).
- `ADD INDEX CONCURRENTLY`.
- `CREATE TABLE`.
- `ADD CONSTRAINT ... NOT VALID`.

Breaking (нужен expand-contract):
- `DROP COLUMN`, `RENAME COLUMN`.
- `ALTER TYPE` (изменение типа).
- `ADD COLUMN ... NOT NULL` без default на больших таблицах.
- `DROP TABLE`, `RENAME TABLE`.
- Удаление значения из enum.
- Сужение `CHECK`.

### `PG-M-002` — N-1 правило: миграция совместима с предыдущей версией кода

Между деплоем миграции и деплоем нового кода — окно работы старого кода с новой схемой.

## 2. Expand-Contract — ключевой паттерн

### `PG-M-010` — Любое breaking-изменение = 3+ релиза:
1. **Expand** — добавили новое (старое работает).
2. **Migrate data** + **dual-write** в коде.
3. **Switch reads** — читатели на новое.
4. **Contract** — старое удалено.

Между шагами — отдельный релиз приложения.

## 3. ALTER TABLE — операции и локи

### `PG-M-020` — Что переписывает таблицу под `ACCESS EXCLUSIVE` (опасно):
- `ALTER TYPE` (с приведением).
- `SET NOT NULL` (проверяет каждую строку).
- `ADD CONSTRAINT CHECK` без NOT VALID.
- `ADD CONSTRAINT FOREIGN KEY` без NOT VALID.

**Что мгновенно (PG11+):**
- `ADD COLUMN NULL DEFAULT 'X'`.
- `ADD COLUMN NOT NULL DEFAULT 'X'`.
- `DROP COLUMN`.
- `ADD CONSTRAINT ... NOT VALID`.

### `PG-M-021` — `ACCESS EXCLUSIVE` встаёт в очередь после ВСЕХ ждущих и блокирует ВСЕХ новых

Долгий `SELECT` блокирует миграцию, за миграцией копится очередь — кратковременный stall на проде.

### `PG-M-022` — `SET LOCAL lock_timeout = '3s'` в каждой миграции с `ALTER TABLE`

Лучше упасть и повторить, чем блокировать прод.

```sql
BEGIN;
SET LOCAL lock_timeout = '3s';
ALTER TABLE order_doc ADD COLUMN ...;
COMMIT;
```

## 4. Рецепты breaking changes

### 4.1. ADD COLUMN NOT NULL

### `PG-M-030` — PG11+ с `DEFAULT` — мгновенно

Без default — expand-contract.

### `PG-M-031` — `SET NOT NULL` через `CHECK NOT VALID` (PG12+):
```sql
-- 1. CHECK NOT VALID — мгновенно
ALTER TABLE t ADD CONSTRAINT ck_t_col_nn CHECK (col IS NOT NULL) NOT VALID;
-- 2. VALIDATE — без ACCESS EXCLUSIVE
ALTER TABLE t VALIDATE CONSTRAINT ck_t_col_nn;
-- 3. SET NOT NULL — теперь дёшево
ALTER TABLE t ALTER COLUMN col SET NOT NULL;
-- 4. опционально: дропнуть избыточный CHECK
ALTER TABLE t DROP CONSTRAINT ck_t_col_nn;
```

### 4.2. RENAME COLUMN

### `PG-M-040` — Нельзя одним коммитом без даунтайма

Шаги:
1. `ADD COLUMN new_name <type>` + dual-write.
2. Backfill: `UPDATE t SET new_name = old_name WHERE new_name IS NULL` батчами.
3. Релиз: код читает `new_name`, dual-write остаётся.
4. Релиз: код только `new_name`.
5. `DROP COLUMN old_name`.

Альтернатива для read-only: `ALTER TABLE RENAME COLUMN` + view-обёртка с computed column.

### 4.3. ALTER TYPE

### `PG-M-050` — `ALTER TYPE` переписывает всю таблицу под ACCESS EXCLUSIVE

На больших — часы. Безопасный путь: новая колонка → backfill → swap → drop old.

Исключения (мгновенно):
- `varchar → text` (одинаковое представление).
- `varchar(50) → varchar(100)` (расширение).

Переписывает: `int → bigint`, `varchar(100) → varchar(50)` (сужение).

### 4.4. DROP COLUMN

### `PG-M-060` — `DROP COLUMN` дёшев, но требует expand-contract по коду:

старая версия упадёт на `INSERT INTO ... (col, ...) VALUES (...)`.

Шаги: код перестал писать → код перестал упоминать → миграция drop.

### 4.5. Foreign Key

### `PG-M-070` — `ADD CONSTRAINT FOREIGN KEY ... NOT VALID` + отдельный `VALIDATE`:
```sql
ALTER TABLE order_item
  ADD CONSTRAINT fk_order_item_order_id
  FOREIGN KEY (order_id) REFERENCES order_doc(id) NOT VALID;

ALTER TABLE order_item VALIDATE CONSTRAINT fk_order_item_order_id;
```

### 4.6. UNIQUE через индекс

```sql
CREATE UNIQUE INDEX CONCURRENTLY uk_customer_email ON customer (email);
ALTER TABLE customer ADD CONSTRAINT uk_customer_email UNIQUE USING INDEX uk_customer_email;
```

### 4.7. Индексы

### `PG-M-080` — В продакшен-миграциях — всегда `CREATE INDEX CONCURRENTLY` / `DROP INDEX CONCURRENTLY`

В Liquibase — `runInTransaction="false"`.

```xml
<changeSet id="..." author="..." runInTransaction="false">
    <sql>CREATE INDEX CONCURRENTLY ix_... ON ... (...);</sql>
    <rollback>DROP INDEX CONCURRENTLY IF EXISTS ix_...;</rollback>
</changeSet>
```

При сломанном построении — индекс остаётся `INVALID`, надо дропнуть и пересоздать.

### 4.8. Enum — удаление значения

### `PG-M-090` — Нативно невозможно. Через теневой тип

Шаги: `CREATE TYPE order_status_v2` → `ADD COLUMN status_v2 order_status_v2` → backfill с маппингом удаляемого значения → swap колонок → `DROP TYPE order_status`.

### `PG-M-091` — `ALTER TYPE ... ADD VALUE` (PG12+) — мгновенно

, но новое значение **нельзя использовать в той же транзакции**. В Liquibase — отдельные changeset'ы.

### `PG-M-092` — Переименование значения (PG10+):

`ALTER TYPE ... RENAME VALUE 'OLD' TO 'NEW'`. Координация с кодом — N-1.

### 4.9. DROP / RENAME TABLE

### `PG-M-100` — DDL тривиален, но требует, чтобы вся версия кода уже не трогала таблицу

Релиз 1: код перестал ссылаться. Релиз 2: миграция dropу/переименование (через несколько дней — на случай rollback).

## 5. Long-running data migrations

### `PG-M-110` — `UPDATE` миллионов строк одним statement — открывает гигантскую TX, копит WAL, блокирует autovacuum

Делай батчами с промежуточными `COMMIT`:

```sql
DO $$
DECLARE rows_updated integer := 1;
BEGIN
    WHILE rows_updated > 0 LOOP
        UPDATE t SET col = X WHERE id IN (
            SELECT id FROM t WHERE col IS NULL LIMIT 10000
        );
        GET DIAGNOSTICS rows_updated = ROW_COUNT;
        COMMIT;
        PERFORM pg_sleep(0.1);
    END LOOP;
END $$;
```

### `PG-M-111` — На больших таблицах — отдельный backfill-job в коде

, не в миграции. Миграция должна выполниться за минуту максимум. Backfill — `@Scheduled` + `SKIP LOCKED`.

## 6. Rollback — почему forward-fix лучше

### `PG-M-120` — `down`-миграции на проде почти всегда не работают

Liquibase `<rollback>` теряет данные на `DROP COLUMN` после backfill.

### `PG-M-121` — Реальный «откат» — это новая forward-миграция

Catastrophe — restore из backup.

## 7. Координация с приложением

### `PG-M-130` — Стандартный flow:
1. Миграция накатывается.
2. Canary (1-2 инстанса).
3. Через 5 мин — остальные инстансы.
4. Через час-сутки — следующая фаза, если есть.

### `PG-M-131` — Миграция совместима с N-1:

`ADD COLUMN` всегда nullable; не добавлять `NOT NULL` пока старый код может писать без значения; не дропать колонки пока есть упоминания в коде.

### `PG-M-132` — CI-проверка совместимости:

запустить тесты предыдущей версии кода против новой схемы.

## 8. Lint миграций

### `PG-M-140` — `squawk` — линтер для миграций

Ловит `CREATE INDEX` без `CONCURRENTLY`, `ALTER TYPE`, `DROP COLUMN`, `ADD CONSTRAINT FK` без `NOT VALID`. Подключи в pre-commit + CI.

## 9. Антипаттерны

`PG-M-150` `ALTER TABLE` без `lock_timeout` — миграция может блокировать прод на минуты.

`PG-M-151` `CREATE INDEX` без `CONCURRENTLY` в продакшен-миграции — десятки минут блокировки записи.

`PG-M-152` Big `UPDATE` одной транзакцией — гигантская TX, большой WAL, replication lag.

`PG-M-153` `ADD CONSTRAINT FOREIGN KEY` без `NOT VALID` — проверка каждой строки под ACCESS EXCLUSIVE.

`PG-M-154` `RENAME COLUMN` одним коммитом — старая версия кода падает.

`PG-M-155` `ALTER TYPE col TYPE bigint` на большой таблице — переписывает всю таблицу под ACCESS EXCLUSIVE.

`PG-M-156` `down`-миграции с `DROP COLUMN` — потеря данных при rollback.

---

## Чек-лист на ревью миграции

- [ ] `SET LOCAL lock_timeout = '3s'` в начале миграции с `ALTER TABLE`.
- [ ] `CREATE INDEX` / `DROP INDEX` — с `CONCURRENTLY`, `runInTransaction="false"`.
- [ ] `ADD CONSTRAINT FOREIGN KEY` — с `NOT VALID` + отдельный `VALIDATE`.
- [ ] `SET NOT NULL` на больших таблицах — через `CHECK NOT VALID + VALIDATE + SET NOT NULL`.
- [ ] `ADD COLUMN NOT NULL DEFAULT` — только PG11+.
- [ ] `RENAME COLUMN` / `DROP COLUMN` — расписан expand-contract.
- [ ] `ALTER TYPE` — через теневую колонку, не одним statement.
- [ ] Удаление значения из enum — через теневой тип.
- [ ] Big `UPDATE` (>1M строк) — батчами или вынесено в backfill-job.
- [ ] N-1 совместимость с предыдущей версией кода.
- [ ] Нет `down`-миграций (или явно описан, почему форвард не подходит).
- [ ] Подключён `squawk` lint в CI.
