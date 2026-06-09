---
lang: any
name: ucp-pg-migration-review
description: Ревью PostgreSQL-миграций (Liquibase/Flyway/сырой SQL) на безопасность для прода (коды PG-M-*) — ACCESS EXCLUSIVE, lock_timeout, CONCURRENTLY для индексов, expand-contract, NOT VALID + VALIDATE, N-1 совместимость кода.
when_to_use: Каждый PR с миграциями в db/changelog/, db/migration/, migrations/ или SQL с ALTER TABLE / CREATE INDEX.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью PostgreSQL миграции

Ты ревьюишь PostgreSQL-миграции на безопасность для прода: лок-блокировки, expand-contract, координация с приложением.

## Зависимости

- **`.claude/docs/backend/pg-migrations/pg-migrations-rules.md`** — источник правил. Кодами `PG-M-NNN`.

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/pg-migrations/pg-migrations-rules.md` (полный текст с SQL-рецептами expand-contract — `backend/pg-migrations/pg-migrations-style-guide.md`, открывай точечно по разделу). Цитируй коды `PG-M-NNN` в каждой находке.

2. **Найди миграции в diff:**
   - `db/changelog/**/*.{xml,sql,yml,json}` (Liquibase).
   - `db/migration/**/V*__*.sql` (Flyway).
   - `src/main/resources/db/**`.
   - Любые `*.sql` с `ALTER TABLE`, `CREATE INDEX`, `DROP TABLE`, `ALTER TYPE`.

3. **Каждый изменённый/новый changeset проанализируй на:**
   - **Лок-агрессивность.** ALTER TABLE без lock_timeout, CREATE INDEX без CONCURRENTLY, ADD CONSTRAINT без NOT VALID — критично.
   - **Expand-contract нарушения.** RENAME/DROP COLUMN, ALTER TYPE одним statement без 3+ релизов — критично.
   - **N-1 совместимость.** Может ли предыдущая версия кода жить с новой схемой?
   - **Long-running data ops.** UPDATE миллионов строк в миграции (а не в backfill-job).

4. **Определи серьёзность:**
   - **Критично** — может уронить прод или потерять данные: CREATE INDEX без CONCURRENTLY на большой таблице, ALTER TYPE на large, RENAME/DROP без expand-contract, отсутствие lock_timeout, ADD CONSTRAINT FK на больших без NOT VALID.
   - **Важно** — повышает риск, но не критично: SET NOT NULL без CHECK NOT VALID-паттерна, отсутствие rollback, нет batch'инга на UPDATE.
   - **Замечание** — стилистика: missing comments, naming.

5. **В конце — план безопасной выкатки:**
   - Когда катить (тихое окно или норма).
   - Сколько релизов до contract-фазы.
   - Что мониторить во время и после.

## Чек-лист правил

### Лок-безопасность

- `PG-M-022` `SET LOCAL lock_timeout = '3s'` в начале миграции с `ALTER TABLE`.
- `PG-M-080` `CREATE INDEX` / `DROP INDEX` — с `CONCURRENTLY`. В Liquibase — `runInTransaction="false"`.
- `PG-M-070` `ADD CONSTRAINT FOREIGN KEY` — с `NOT VALID` + отдельный `VALIDATE`.

### Изменение колонок и типов

- `PG-M-030` `ADD COLUMN ... NOT NULL DEFAULT 'X'` — только PG11+.
- `PG-M-031` `SET NOT NULL` на больших таблицах — через `ADD CONSTRAINT CHECK NOT VALID + VALIDATE + SET NOT NULL + DROP CONSTRAINT`.
- `PG-M-040` `RENAME COLUMN` — нельзя одним коммитом без даунтайма; expand-contract на 3+ релиза.
- `PG-M-050` `ALTER TYPE` (изменение типа колонки) на большой таблице — через теневую колонку + backfill + swap.
- `PG-M-060` `DROP COLUMN` — только если код уже не упоминает.

### Enum

- `PG-M-090` Удаление значения из enum — через теневой тип, не нативно.
- `PG-M-091` `ALTER TYPE ... ADD VALUE` и использование значения — в РАЗНЫХ changeset'ах.

### Long-running data

- `PG-M-110` `UPDATE` миллионов строк в миграции — батчами с промежуточным `COMMIT`.
- `PG-M-111` На больших — backfill в коде (`@Scheduled` + `SKIP LOCKED`), не в миграции.

### Координация

- `PG-M-002` / `PG-M-131` — N-1 совместимость с предыдущей версией кода.
- `PG-M-100` `DROP TABLE` / `RENAME TABLE` — после того как код перестал упоминать.

### Rollback

- `PG-M-120` / `PG-M-121` — `down`-миграции почти всегда не работают; `<rollback>` блок в Liquibase часто иллюзия.

## Формат вывода

```
[критично] PG-M-080 CREATE INDEX без CONCURRENTLY на orders.
   Файл: db/changelog/v0042-add-customer-index.xml
   Liquibase создаст индекс под SHARE-lock — заблокирует все INSERT/UPDATE/DELETE
   на orders на время построения (для 100M строк — 30+ минут).
   Должно быть:
     <changeSet id="..." author="..." runInTransaction="false">
         <sql>CREATE INDEX CONCURRENTLY ix_orders_customer_id
               ON orders (customer_id);</sql>
         <rollback>DROP INDEX CONCURRENTLY IF EXISTS ix_orders_customer_id;</rollback>
     </changeSet>

[критично] PG-M-040 RENAME COLUMN customer.created_dt → created_at одним statement.
   Файл: db/changelog/v0043-rename-created.xml
   Старая версия кода на canary'е упадёт сразу после применения миграции
   (ожидает столбец `created_dt`).
   Должно быть: 3 релиза по expand-contract:
     1. ADD COLUMN created_at + dual-write в коде
     2. backfill + переключение чтения на новую колонку
     3. DROP COLUMN created_dt после полного удаления упоминаний

[важно] PG-M-022 ALTER TABLE без SET LOCAL lock_timeout.
   Если в момент миграции на orders есть долгий SELECT, ACCESS EXCLUSIVE
   встанет в очередь и заблокирует всех новых клиентов.
   Должно быть:
     <sql>SET LOCAL lock_timeout = '3s';</sql>
     <sql>ALTER TABLE orders ...;</sql>
```

В конце:

```
План выкатки:
1. Этот PR — только expand (ADD COLUMN created_at, dual-write).
2. Через сутки — backfill-job завершается + следующий PR со switch reads.
3. Через сутки — финальный PR с DROP COLUMN created_dt.

Мониторить:
- pg_locks: ACCESS EXCLUSIVE на orders во время миграции (не должно быть > 1с).
- replication lag: всплеск UPDATE = всплеск WAL.
- application errors: если canary падает с column not found — rollback.
```

## Что не входит

- Типы колонок и naming в DDL — это `ucp-pg-schema-review` (уже мог отработать на этом PR).
- Производительность запросов / индексов — это `ucp-pg-explain-review`.
- Spring `@Transactional` patterns — `ucp-pattern-review`.
