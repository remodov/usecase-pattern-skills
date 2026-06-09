---
lang: any
name: ucp-pg-runtime-review
description: Ревью PostgreSQL runtime-аспектов (коды PG-W-*, PG-V-*, PG-L-*, PG-CP-*, PG-IS-*) — WAL-нагрузка, autovacuum/bloat, блокировки и FOR UPDATE/SKIP LOCKED, длинные @Transactional, HikariCP/PgBouncer, уровни изоляции и retry на 40001.
when_to_use: Тормоза под нагрузкой, ревью кода с транзакциями и блокировками, тюнинг connection pool.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью PostgreSQL runtime

Ты ревьюишь Java/Spring-код, DDL-миграции и application config на runtime-проблемы PostgreSQL: излишний WAL, bloat от плохого autovacuum, неправильные блокировки, неверная настройка HikariCP/PgBouncer, неверно поднятый уровень изоляции без retry.

## Зависимости

- **`.claude/docs/backend/pg-runtime/pg-runtime-rules.md`** в проекте (или из `claude-code-java`) — источник правил. Кодами `PG-W-NNN` (WAL), `PG-V-NNN` (VACUUM), `PG-L-NNN` (Locks), `PG-CP-NNN` (Connection Pool), `PG-IS-NNN` (Isolation).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/pg-runtime/pg-runtime-rules.md` (полный текст с SQL-примерами и yaml-конфигами — `backend/pg-runtime/pg-runtime-style-guide.md`, открывай точечно по разделу). Цитируй коды правил в каждой находке.

2. **Определи режим работы.** Если пользователь дал:
   - **Java-код с `@Transactional`** — фокус на длительность транзакций (PG-W-061, PG-V-050) и блокировки.
   - **DDL миграция** — fillfactor, индексы под HOT.
   - **Bulk-импорт** — COPY vs INSERT, batch-size, dropping indexes.
   - **Outbox-relay / scheduled job** — `SKIP LOCKED`, advisory lock на singleton.
   - **Финансовая операция** (transfer, payment) — pessimistic locking, deadlock prevention.

3. **При ревью кода ищи паттерны:**
   - `@Transactional` методы, ходящие во внешние HTTP/Kafka/S3 (PG-W-061).
   - Циклы `INSERT` вместо `batchUpdate` или `COPY` (PG-W-010).
   - `SELECT FOR UPDATE` вне `@Transactional` (PG-L-041, PG-L-090).
   - `UPDATE` денежных счетов без упорядочения по `id` (PG-L-071).
   - Outbox-relay без `SKIP LOCKED` (PG-L-021).
   - Создание индекса без `CONCURRENTLY` в продакшен-миграции.

4. **При ревью DDL/конфигурации схемы:**
   - Write-heavy таблицы без `fillfactor < 100` (PG-W-021).
   - `UNLOGGED` упомянут — оправдан ли (PG-W-040)?
   - autovacuum выключен per-table — намеренно?

5. **Сгруппируй вывод** по категориям: критично (open длинные транзакции, deadlock-prone порядок, отсутствие SKIP LOCKED), важно (fillfactor дефолт, batch-size), наблюдение.

## Чек-лист правил

### WAL и операционная нагрузка (`PG-W-*`)

- `PG-W-010` Bulk-вставки через `COPY`/`batchUpdate`, не цикл.
- `PG-W-011` Длина транзакции — не сотни тысяч insert'ов в одной (батчи 1–10K).
- `PG-W-012` Перед массовой загрузкой — дроп индексов.
- `PG-W-021` Write-heavy таблицы — `fillfactor = 80–90`.
- `PG-W-022` Не вешать индекс на колонку, обновляемую почти на каждом UPDATE и редко в WHERE.
- `PG-W-030` JSONB не должен содержать одновременно горячие и тяжёлые поля (полный re-write при UPDATE).
- `PG-W-040` Кеши/временные данные — `UNLOGGED`.
- `PG-W-051` `synchronous_commit = off` для метрик/логов через `SET LOCAL`.
- `PG-W-061` `@Transactional` НЕ оборачивает HTTP/Kafka/S3 — длинная транзакция блокирует autovacuum и WAL.
- `PG-W-070` Replication slot lag — мониторится.

### VACUUM (`PG-V-*`)

- `PG-V-021` На больших горячих таблицах снижен `autovacuum_vacuum_scale_factor` до 0.05.
- `PG-V-053` Нет `autovacuum_enabled = false` без явного плана.
- `PG-V-060` После big-миграции — `VACUUM ANALYZE` в той же миграции.
- `PG-V-061` После `CREATE INDEX CONCURRENTLY` — `VACUUM` для visibility map.

### Блокировки (`PG-L-*`)

- `PG-L-010` `SELECT FOR UPDATE` для read-modify-write по одной строке.
- `PG-L-020` Очереди / outbox-relay — `FOR UPDATE SKIP LOCKED LIMIT N`.
- `PG-L-041` Lock-запрос внутри `@Transactional`.
- `PG-L-051` Optimistic для read-heavy / низкоконкурентного, pessimistic для write-heavy / денежного.
- `PG-L-060` Singleton scheduled-job — `pg_try_advisory_xact_lock`.
- `PG-L-071` Multi-row блокировки — в порядке возрастания `id` (предотвращает deadlock).
- `PG-L-072` Java retry на `CannotAcquireLockException` (1–3 попытки с backoff).
- `PG-L-080` `SET LOCAL lock_timeout` для миграций и критичных операций.
- `PG-L-090`/`091`/`092`/`093`/`094`/`095` — антипаттерны блокировок.

## Формат вывода

```
[критично] PG-W-061 OrderService.processOrder @Transactional оборачивает HTTP-вызов в PaymentGateway.
   Файл: src/main/java/.../OrderService.java:42
   `@Transactional` метод open ~3 секунд (HTTP latency) → транзакция держит row-lock на orders + блокирует autovacuum.
   Должно быть: разделить на 2 транзакции — внутри @Transactional только запись в БД, HTTP — отдельным шагом.

[критично] PG-L-021 OutboxRelay не использует SKIP LOCKED.
   Файл: src/main/java/.../OutboxRelay.java:18
   При >1 инстансе сервиса будет дублирующая публикация.
   Должно быть: ctx.selectFrom(OUTBOX).where(OUTBOX.PUBLISHED_AT.isNull()).limit(50)
                   .forUpdate().skipLocked().fetch();

[важно] PG-W-021 order_doc создаётся без fillfactor.
   Эта таблица — write-heavy (UPDATE статуса при каждом изменении заказа).
   Должно быть: CREATE TABLE order_doc (...) WITH (fillfactor = 85);

[критично] PG-CP-082 OrderService.processOrder @Transactional оборачивает HTTP-вызов.
   File: src/main/java/.../OrderService.java:42
   Соединение из HikariCP-пула удерживается всё время HTTP-вызова (~3 сек).
   При нагрузке пул полностью занят, новые запросы ждут или таймаутят.
   Должно быть: разделить на 2 транзакции, HTTP вне @Transactional.

[критично] PG-IS-083 @Transactional(isolation = SERIALIZABLE) без retry.
   File: src/main/java/.../TransferHandler.java:18
   Под нагрузкой будут случайные 40001 (CannotSerializeTransactionException).
   Должно быть: + @Retryable(retryFor = CannotSerializeTransactionException.class,
                              maxAttempts = 3, backoff = @Backoff(delay = 50)).

[важно] PG-CP-002 maximum-pool-size = 100 для одного инстанса.
   Если у вас 10 инстансов и default max_connections=100 PG, общая сумма 1000
   при дефолте PG. Снизь до 20 либо подними max_connections.
```

## Чек-лист правил (расширение)

Помимо указанных выше WAL/VACUUM/Locks-правил, проверяй также:

### Connection pool (`PG-CP-*`)

- `PG-CP-002` Размер пула 10–20 на инстанс, не сотни.
- `PG-CP-010` `maximum-pool-size = minimum-idle`.
- `PG-CP-014` `leak-detection-threshold` включён (60s).
- `PG-CP-013` `max-lifetime: 30 мин` (меньше LB-таймаута).
- `PG-CP-045` При PgBouncer + transaction mode: `prepareThreshold = 0` или PgBouncer 1.21+.
- `PG-CP-060` Read-replica routing — отдельный DataSource через `@Transactional(readOnly = true)`.
- `PG-CP-082` `@Transactional` НЕ вокруг HTTP/Kafka/S3.

### Isolation (`PG-IS-*`)

- `PG-IS-041` Дефолтный `READ COMMITTED` не указывать явно.
- `PG-IS-022`/`PG-IS-042` На `Isolation.REPEATABLE_READ` / `SERIALIZABLE` обязательно `@Retryable` на `CannotSerializeTransactionException`.
- `PG-IS-033` SERIALIZABLE — только когда инвариант невозможно выразить через CHECK / FOR UPDATE.
- `PG-IS-070` Серверный `idle_in_transaction_session_timeout = 30–60 сек`.

## Что не входит

- Типы колонок и naming — это `ucp-pg-schema-review`.
- Композитные индексы и план запроса — это `ucp-pg-explain-review`.
- DDL-миграции, expand-contract, ACCESS EXCLUSIVE — это `ucp-pg-migration-review`.
- Чисто Java-код без DB-взаимодействия — это `ucp-pattern-review`.
