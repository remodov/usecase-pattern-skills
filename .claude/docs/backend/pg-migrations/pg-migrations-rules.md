# PostgreSQL Migrations — индекс правил

> **Что это.** Сжатый индекс правил `pg-migrations-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с SQL-рецептами expand-contract и обоснованием — `pg-migrations-style-guide.md`**; открывай её точечно по разделу.
> Коды: `PG-M-<NNN>`. X-кодов нет; сводные антипаттерны — `PG-M-15X` в разделе 9.

Базовый принцип: **`ALTER TABLE` берёт `ACCESS EXCLUSIVE` и блокирует ВСЁ** (INSERT/UPDATE/SELECT). Любое breaking-изменение режется на 3+ релиза по принципу N-1.

## 1. Что breaking, что нет
**MUST:**
- **PG-M-001.** Breaking — операция, ломающая старую версию кода. Не-breaking (один релиз): `ADD COLUMN NULL` (PG11+ с DEFAULT тоже), `ADD INDEX CONCURRENTLY`, `CREATE TABLE`, `ADD CONSTRAINT NOT VALID`. Breaking (expand-contract): `DROP/RENAME COLUMN`, `ALTER TYPE`, `ADD COLUMN NOT NULL` без default на больших, `DROP/RENAME TABLE`, удаление enum-значения, сужение `CHECK`.
- **PG-M-002.** N-1 правило: миграция совместима с предыдущей версией кода (окно работы старого кода с новой схемой).

## 2. Expand-Contract
**MUST:**
- **PG-M-010.** Любое breaking-изменение = 3+ релиза: Expand (добавили новое) → Migrate data + dual-write → Switch reads → Contract (старое удалено); между шагами — отдельный релиз приложения.

## 3. ALTER TABLE — операции и локи
**MUST:**
- **PG-M-020.** Переписывают таблицу под ACCESS EXCLUSIVE (опасно): `ALTER TYPE` с приведением, `SET NOT NULL`, `ADD CONSTRAINT CHECK`/`FK` без NOT VALID. Мгновенно (PG11+): `ADD COLUMN [NOT] NULL DEFAULT`, `DROP COLUMN`, `ADD CONSTRAINT NOT VALID`.
- **PG-M-021.** `ACCESS EXCLUSIVE` встаёт в очередь после всех ждущих и блокирует всех новых — долгий `SELECT` блокирует миграцию, за ней копится очередь (stall на проде).
- **PG-M-022.** `SET LOCAL lock_timeout = '3s'` в каждой миграции с `ALTER TABLE` — лучше упасть и повторить, чем блокировать прод.

## 4. Рецепты breaking changes
**MUST:**
- **PG-M-030.** `ADD COLUMN NOT NULL`: PG11+ с DEFAULT мгновенно; без default — expand-contract.
- **PG-M-031.** `SET NOT NULL` через `CHECK (col IS NOT NULL) NOT VALID` → `VALIDATE` → `SET NOT NULL` → опц. drop CHECK (PG12+, без ACCESS EXCLUSIVE на проверке).
- **PG-M-040.** `RENAME COLUMN` нельзя одним коммитом: `ADD COLUMN new` + dual-write → backfill батчами → релиз читает new → релиз только new → `DROP COLUMN old`.
- **PG-M-050.** `ALTER TYPE` переписывает всю таблицу под ACCESS EXCLUSIVE (часы на больших): новая колонка → backfill → swap → drop. Мгновенно: `varchar→text`, `varchar(50)→varchar(100)`. Переписывает: `int→bigint`, сужение.
- **PG-M-060.** `DROP COLUMN` дёшев, но требует expand-contract по коду (старая версия упадёт на `INSERT ... (col)`): код перестал писать → перестал упоминать → drop.
- **PG-M-070.** FK: `ADD CONSTRAINT FOREIGN KEY ... NOT VALID` + отдельный `VALIDATE CONSTRAINT`.
- **PG-M-080.** Индексы — всегда `CREATE/DROP INDEX CONCURRENTLY`, в миграционном инструменте `runInTransaction="false"`; сломанное построение → `INVALID` индекс дропнуть и пересоздать.
- **PG-M-090.** Удаление enum-значения нативно невозможно — через теневой тип (`CREATE TYPE …_v2` → `ADD COLUMN status_v2` → backfill с маппингом → swap → `DROP TYPE`).
- **PG-M-091.** `ALTER TYPE ... ADD VALUE` (PG12+) мгновенно, но новое значение нельзя использовать в той же транзакции — в миграционный инструмент отдельные changeset'ы.
- **PG-M-092.** Переименование enum-значения (PG10+) — `ALTER TYPE ... RENAME VALUE`; координация с кодом N-1.
- **PG-M-100.** `DROP`/`RENAME TABLE`: DDL тривиален, но вся версия кода уже не трогает таблицу — релиз 1 перестал ссылаться, релиз 2 (через дни, на случай rollback) drop/rename.

## 5. Long-running data migrations
**MUST:**
- **PG-M-110.** `UPDATE` миллионов строк одним statement открывает гигантскую TX (WAL, блокирует autovacuum) — батчами с промежуточными `COMMIT` + `pg_sleep`.
- **PG-M-111.** На больших таблицах — отдельный backfill-job в коде (фоновый job + `SKIP LOCKED`), не в миграции; миграция выполняется за минуту максимум.

## 6. Rollback — forward-fix лучше
**MUST:**
- **PG-M-120.** `down`-миграции на проде почти всегда не работают (миграционный `<rollback>` теряет данные на `DROP COLUMN` после backfill).
- **PG-M-121.** Реальный «откат» — новая forward-миграция; catastrophe — restore из backup.

## 7. Координация с приложением
**MUST:**
- **PG-M-130.** Стандартный flow: миграция → canary (1-2 инстанса) → через 5 мин остальные → через час-сутки следующая фаза.
- **PG-M-131.** N-1 совместимость: `ADD COLUMN` всегда nullable; не добавлять `NOT NULL` пока старый код пишет без значения; не дропать колонки пока есть упоминания.
- **PG-M-132.** CI-проверка совместимости: тесты предыдущей версии кода против новой схемы.

## 8. Lint миграций
**MUST:**
- **PG-M-140.** `squawk` — линтер миграций (ловит `CREATE INDEX` без `CONCURRENTLY`, `ALTER TYPE`, `DROP COLUMN`, FK без `NOT VALID`); в pre-commit + CI.

## 9. Антипаттерны
**MUST NOT:**
- **PG-M-150.** `ALTER TABLE` без `lock_timeout` — может блокировать прод на минуты.
- **PG-M-151.** `CREATE INDEX` без `CONCURRENTLY` в продакшен-миграции — десятки минут блокировки записи.
- **PG-M-152.** Big `UPDATE` одной транзакцией — гигантская TX, большой WAL, replication lag.
- **PG-M-153.** `ADD CONSTRAINT FOREIGN KEY` без `NOT VALID` — проверка каждой строки под ACCESS EXCLUSIVE.
- **PG-M-154.** `RENAME COLUMN` одним коммитом — старая версия кода падает.
- **PG-M-155.** `ALTER TYPE col TYPE bigint` на большой таблице — переписывает всю таблицу под ACCESS EXCLUSIVE.
- **PG-M-156.** `down`-миграции с `DROP COLUMN` — потеря данных при rollback.
