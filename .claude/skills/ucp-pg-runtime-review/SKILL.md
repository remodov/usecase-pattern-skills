---
name: ucp-pg-runtime-review
description: Ревью PostgreSQL runtime-аспектов — WAL-нагрузка, autovacuum/bloat, блокировки в коде. Проверяет fillfactor на write-heavy таблицах, длинные транзакции (Spring @Transactional вокруг HTTP/Kafka), bulk-операции (COPY vs INSERT), SELECT FOR UPDATE / SKIP LOCKED через jOOQ, advisory locks, deadlock-prone порядок блокировок, мониторинг bloat и replication slots. Вызывается при тормозах под нагрузкой, ревью кода с транзакциями, разборе WAL/disk-issues.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью PostgreSQL runtime

Ты ревьюишь Java/Spring-код и DDL-миграции на runtime-проблемы PostgreSQL: излишний WAL, bloat от плохого autovacuum, неправильные блокировки.

## Зависимости

- **`.claude/docs/pg-runtime-style-guide.md`** в проекте (или из `claude-code-java`) — единственный источник правил. Кодами `PG-W-NNN` (WAL), `PG-V-NNN` (VACUUM), `PG-L-NNN` (Locks).

## Инструкции

1. **Прочти style guide** из `.claude/docs/pg-runtime-style-guide.md`. Цитируй коды правил в каждой находке.

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
```

## Что не входит

- Типы колонок и naming — это `ucp-pg-schema-review`.
- Композитные индексы и план запроса — это `ucp-pg-explain-review`.
- Чисто Java-код без DB-взаимодействия — это `ucp-pattern-review`.
