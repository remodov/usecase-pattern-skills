---
lang: any
name: ucp-pg-runtime-review
description: Ревью PostgreSQL runtime-аспектов (требования pg-runtime/*) — WAL-нагрузка, autovacuum/bloat, блокировки и FOR UPDATE/SKIP LOCKED, длинные @Transactional, HikariCP/PgBouncer, уровни изоляции и retry на 40001.
when_to_use: Тормоза под нагрузкой, ревью кода с транзакциями и блокировками, тюнинг connection pool.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью PostgreSQL runtime

Ты ревьюишь Java/Spring-код, DDL-миграции и application config на runtime-проблемы PostgreSQL: излишний WAL, bloat от плохого autovacuum, неправильные блокировки, неверная настройка HikariCP/PgBouncer, неверно поднятый уровень изоляции без retry.

## Зависимости

- **`.claude/docs/backend/pg-runtime/spec.md`** в проекте (или из `claude-code-java`) — источник правил. Кодами `PG-W-NNN` (WAL), `PG-V-NNN` (VACUUM), `PG-L-NNN` (Locks), `PG-CP-NNN` (Connection Pool), `PG-IS-NNN` (Isolation).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/pg-runtime/spec.md` (полный текст с SQL-примерами и yaml-конфигами — `backend/pg-runtime/references/implementation.md`, открывай точечно по разделу). Цитируй коды правил в каждой находке.

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

- `pg-runtime/bulk-load-via-copy` (`pg-runtime/bulk-load-via-copy`, `W`) Bulk-вставки через `COPY`/`batchUpdate`, не цикл.
- `pg-runtime/bulk-load-via-copy` (`pg-runtime/bulk-load-via-copy`, `W`) Длина транзакции — не сотни тысяч insert'ов в одной (батчи 1–10K).
- `pg-runtime/bulk-load-via-copy` (`pg-runtime/bulk-load-via-copy`, `W`) Перед массовой загрузкой — дроп индексов.
- `pg-runtime/fillfactor-for-hot-updates` (`pg-runtime/fillfactor-for-hot-updates`, `W`) Write-heavy таблицы — `fillfactor = 80–90`.
- `pg-runtime/fillfactor-for-hot-updates` (`pg-runtime/fillfactor-for-hot-updates`, `W`) Не вешать индекс на колонку, обновляемую почти на каждом UPDATE и редко в WHERE.
- `pg-runtime/toast-large-values-separately` (`pg-runtime/toast-large-values-separately`, `W`) JSONB не должен содержать одновременно горячие и тяжёлые поля (полный re-write при UPDATE).
- `pg-runtime/unlogged-for-disposable-data` (`pg-runtime/unlogged-for-disposable-data`, `W`) Кеши/временные данные — `UNLOGGED`.
- `pg-runtime/synchronous-commit-scope` (`pg-runtime/synchronous-commit-scope`, `W`) `synchronous_commit = off` для метрик/логов через `SET LOCAL`.
- `pg-runtime/short-transactions` (`pg-runtime/short-transactions`, `W`) `@Transactional` НЕ оборачивает HTTP/Kafka/S3 — длинная транзакция блокирует autovacuum и WAL.
- `pg-runtime/replication-slots-watched` (`pg-runtime/replication-slots-watched`, `W`) Replication slot lag — мониторится.

### VACUUM (`PG-V-*`)

- `pg-runtime/autovacuum-tuning-per-table` (`pg-runtime/autovacuum-tuning-per-table`, `V`) На больших горячих таблицах снижен `autovacuum_vacuum_scale_factor` до 0.05.
- `pg-runtime/autovacuum-tuning-per-table` (`pg-runtime/autovacuum-tuning-per-table`, `V`) Нет `autovacuum_enabled = false` без явного плана.
- `pg-runtime/vacuum-analyze-after-bulk-change` (`pg-runtime/vacuum-analyze-after-bulk-change`, `V`) После big-миграции — `VACUUM ANALYZE` в той же миграции.
- `pg-runtime/vacuum-analyze-after-bulk-change` (`pg-runtime/vacuum-analyze-after-bulk-change`, `V`) После `CREATE INDEX CONCURRENTLY` — `VACUUM` для visibility map.

### Блокировки (`PG-L-*`)

- `pg-runtime/row-lock-inside-transaction` (`pg-runtime/row-lock-inside-transaction`, `L`) `SELECT FOR UPDATE` для read-modify-write по одной строке.
- `pg-runtime/skip-locked-for-queues` (`pg-runtime/skip-locked-for-queues`, `L`) Очереди / outbox-relay — `FOR UPDATE SKIP LOCKED LIMIT N`.
- `pg-runtime/row-lock-inside-transaction` (`pg-runtime/row-lock-inside-transaction`, `L`) Lock-запрос внутри `@Transactional`.
- `pg-runtime/pessimistic-versus-optimistic` (`pg-runtime/pessimistic-versus-optimistic`, `L`) Optimistic для read-heavy / низкоконкурентного, pessimistic для write-heavy / денежного.
- `pg-runtime/advisory-lock-for-singleton` (`pg-runtime/advisory-lock-for-singleton`, `L`) Singleton scheduled-job — `pg_try_advisory_xact_lock`.
- `pg-runtime/deadlock-prevention-by-order` (`pg-runtime/deadlock-prevention-by-order`, `L`) Multi-row блокировки — в порядке возрастания `id` (предотвращает deadlock).
- `pg-runtime/deadlock-prevention-by-order` (`pg-runtime/deadlock-prevention-by-order`, `L`) Java retry на `CannotAcquireLockException` (1–3 попытки с backoff).
- `pg-runtime/lock-timeout-for-critical-operations` (`pg-runtime/lock-timeout-for-critical-operations`, `L`) `SET LOCAL lock_timeout` для миграций и критичных операций.
- `pg-runtime/row-lock-inside-transaction`/`091`/`092`/`093`/`094`/`095` — антипаттерны блокировок.

## Формат вывода

```
[критично] pg-runtime/short-transactions (PG-W-061) OrderService.processOrder @Transactional оборачивает HTTP-вызов в PaymentGateway.
   Файл: src/main/java/.../OrderService.java:42
   `@Transactional` метод open ~3 секунд (HTTP latency) → транзакция держит row-lock на orders + блокирует autovacuum.
   Должно быть: разделить на 2 транзакции — внутри @Transactional только запись в БД, HTTP — отдельным шагом.

[критично] pg-runtime/skip-locked-for-queues (PG-L-021) OutboxRelay не использует SKIP LOCKED.
   Файл: src/main/java/.../OutboxRelay.java:18
   При >1 инстансе сервиса будет дублирующая публикация.
   Должно быть: ctx.selectFrom(OUTBOX).where(OUTBOX.PUBLISHED_AT.isNull()).limit(50)
                   .forUpdate().skipLocked().fetch();

[важно] pg-runtime/fillfactor-for-hot-updates (PG-W-021) order_doc создаётся без fillfactor.
   Эта таблица — write-heavy (UPDATE статуса при каждом изменении заказа).
   Должно быть: CREATE TABLE order_doc (...) WITH (fillfactor = 85);

[критично] pg-runtime/short-transactions (PG-CP-082) OrderService.processOrder @Transactional оборачивает HTTP-вызов.
   File: src/main/java/.../OrderService.java:42
   Соединение из HikariCP-пула удерживается всё время HTTP-вызова (~3 сек).
   При нагрузке пул полностью занят, новые запросы ждут или таймаутят.
   Должно быть: разделить на 2 транзакции, HTTP вне @Transactional.

[критично] pg-runtime/retry-on-serialization-failure (PG-IS-083) @Transactional(isolation = SERIALIZABLE) без retry.
   File: src/main/java/.../TransferHandler.java:18
   Под нагрузкой будут случайные 40001 (CannotSerializeTransactionException).
   Должно быть: + @Retryable(retryFor = CannotSerializeTransactionException.class,
                              maxAttempts = 3, backoff = @Backoff(delay = 50)).

[важно] pg-runtime/pool-size-is-calculated (PG-CP-002) maximum-pool-size = 100 для одного инстанса.
   Если у вас 10 инстансов и default max_connections=100 PG, общая сумма 1000
   при дефолте PG. Снизь до 20 либо подними max_connections.
```

## Чек-лист правил (расширение)

Помимо указанных выше WAL/VACUUM/Locks-правил, проверяй также:

### Connection pool (`PG-CP-*`)

- `pg-runtime/pool-size-is-calculated` (`pg-runtime/pool-size-is-calculated`, `CP`) Размер пула 10–20 на инстанс, не сотни.
- `pg-runtime/pool-settings-complete` (`pg-runtime/pool-settings-complete`, `CP`) `maximum-pool-size = minimum-idle`.
- `pg-runtime/leak-detection-enabled` (`pg-runtime/leak-detection-enabled`, `CP`) `leak-detection-threshold` включён (60s).
- `pg-runtime/pool-settings-complete` (`pg-runtime/pool-settings-complete`, `CP`) `max-lifetime: 30 мин` (меньше LB-таймаута).
- `pg-runtime/pooler-transaction-mode-constraints` (`pg-runtime/pooler-transaction-mode-constraints`, `CP`) При PgBouncer + transaction mode: `prepareThreshold = 0` или PgBouncer 1.21+.
- `pg-runtime/read-replica-separate-datasource` (`pg-runtime/read-replica-separate-datasource`, `CP`) Read-replica routing — отдельный DataSource через `@Transactional(readOnly = true)`.
- `pg-runtime/short-transactions` (`pg-runtime/short-transactions`, `CP`) `@Transactional` НЕ вокруг HTTP/Kafka/S3.

### Isolation (`PG-IS-*`)

- `pg-runtime/default-isolation-is-right` (`pg-runtime/default-isolation-is-right`, `IS`) Дефолтный `READ COMMITTED` не указывать явно.
- `pg-runtime/repeatable-read-for-consistent-snapshot`/`pg-runtime/retry-on-serialization-failure` На `Isolation.REPEATABLE_READ` / `SERIALIZABLE` обязательно `@Retryable` на `CannotSerializeTransactionException`.
- `pg-runtime/serializable-for-cross-row-invariants` (`pg-runtime/serializable-for-cross-row-invariants`, `IS`) SERIALIZABLE — только когда инвариант невозможно выразить через CHECK / FOR UPDATE.
- `pg-runtime/idle-in-transaction-timeout` (`pg-runtime/idle-in-transaction-timeout`, `IS`) Серверный `idle_in_transaction_session_timeout = 30–60 сек`.

## Что не входит

- Типы колонок и naming — это `ucp-pg-schema-review`.
- Композитные индексы и план запроса — это `ucp-pg-explain-review`.
- DDL-миграции, expand-contract, ACCESS EXCLUSIVE — это `ucp-pg-migration-review`.
- Чисто Java-код без DB-взаимодействия — это `ucp-pattern-review`.
