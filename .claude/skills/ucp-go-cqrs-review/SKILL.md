---
name: ucp-go-cqrs-review
lang: go
description: Ревью CQRS-разделения в Go-сервисе (net/http + chi) по UCP (требования cqrs/*) — Command/Query-интерфейсы-маркеры, pgx read-only tx, sqlc ViewRepository, outbox+segmentio/kafka-go, idempotent consumer, eventual consistency в API.
when_to_use: Ревью Handler-структур с маркерами Command/Query, OrderViewRepository, read-DTO, outbox-репозиториев, Kafka-консюмеров read-side.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью CQRS (Go / net/http + chi)

Ты ревьюишь CQRS на соответствие **контракту** `backend/cqrs/spec.md` (`R-CQRS-*`) и **Go-реализации** `backend/cqrs/references/go/implementation.md`.

## Зависимости

- **`.claude/docs/backend/cqrs/spec.md`** + **`backend/cqrs/references/go/implementation.md`**.
- Парные: `backend/usecase-pattern/go/...` (`Command`/`Query`/Handler), `backend/error-handling/references/go/implementation.md` (`R-ERR-MAP-*`, `apperr.Kind`), `backend/kafka/...` (outbox/idempotent), `backend/ddd-tactical/...` (агрегат).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй коды (`cqrs/read-via-projection-not-aggregate`), не префикс.

2. **Скоп.** Handler-структуры реализующие `Command`/`Query`-маркеры (`core/cqrs/cqrs.go`), `*_view_repository.go`, read-DTO в `core/<bc>/dto/view/`, outbox-репозитории (`adapters/out/outbox/`), Kafka read-side консюмеры (`adapters/in/kafka/`), chi-хендлеры с eventual-consistency; `git diff`.

3. **Прогон.**
   - **Когда/уровень (`R-CQRS-WHEN/TIER-*`):** уровень соответствует зрелости; lightweight-маркеры обязаны иметь enforcement (pgx read-only транзакция `pgx.TxOptions{AccessMode: pgx.ReadOnly}`) — иначе `cqrs/split-matches-maturity-level`; полный split без боли → `cqrs/lightweight-first-full-on-evidence`; event-driven read-model с одним `<X>Repository` → `cqrs/split-matches-maturity-level`.
   - **Command (`R-CQRS-CMD-*`):** `struct` реализует маркер `core/cqrs.Command` (неэкспортируемый `isCommand()`), меняет один агрегат через rw-транзакцию pgx, возвращает id/статус. Read-DTO из command → `cqrs/command-returns-minimum`. SELECT «для чтения потом» в command → `cqrs/command-handler-does-not-query`. Несколько агрегатов без саги → `cqrs/command-changes-one-aggregate`.
   - **Query (`R-CQRS-QRY-*`):** `struct` реализует маркер `core/cqrs.Query` (неэкспортируемый `isQuery()`), читает через `<X>ViewRepository` с read-only транзакцией pgx, без commit. Write в query → `cqrs/query-is-read-only`. Загружает агрегат через `<X>Repository` вместо `<X>ViewRepository` → `cqrs/read-via-projection-not-aggregate`. Возвращает `*Aggregate` или Entity → `cqrs/query-returns-read-model`. Вызывает доменный метод → нарушение `cqrs/query-is-read-only`.
   - **Read-model (`R-CQRS-RM-*`):** денормализована (join'ов нет), независима от write-схемы, восстановима (есть rebuild-команда в `cmd/rebuild/`). Бизнес-логика в read-model → `cqrs/projection-has-no-logic-or-backflow`. Source-of-truth read-model → `cqrs/read-model-is-rebuildable`. Bidirectional sync → `cqrs/projection-has-no-logic-or-backflow`.
   - **Sync (`R-CQRS-SYNC-*`):** outbox+`segmentio/kafka-go`, idempotent consumer (`processed_event`-таблица или version-проверка), rebuild при бутстрапе, eventual consistency задекларирована (заголовок/OpenAPI). Синхронный `INSERT INTO order_summary` в command-транзакции → `cqrs/read-model-synced-by-events`. PG-триггеры → `cqrs/read-model-synced-by-events`. Payload = sqlc-структура write-схемы → `cqrs/events-not-coupled-to-write-schema`.

4. **Grep-проверки.** Запускай до вынесения findings:
   - `Grep`: `pgx.TxOptions{}` без `AccessMode: pgx.ReadOnly` в query-handler — кандидат `cqrs/split-matches-maturity-level`.
   - `Grep`: `tx.Exec\|tx.Query` в `*_query_handler.go` — кандидат `cqrs/query-is-read-only`.
   - `Grep`: `db.Order\|db\.` в struct-полях event-payload — кандидат `cqrs/events-not-coupled-to-write-schema`.
   - `Grep`: `INSERT INTO order_summary` (или аналогичное) в `*_command_handler.go` / `*_handler.go` — кандидат `cqrs/read-model-synced-by-events`.
   - `go vet ./...` — базовая санитарная проверка Go-кода.

5. **Cross-check:** `<X>ViewRepository`-реализация и sqlc-запросы — `ucp-go-sqlc-review`; outbox/idempotent consumer — `ucp-go-kafka-review`; агрегат на write-side — `ucp-go-ddd-tactical-review`; ошибки domain → `R-ERR-MAP-*` (`apperr.Kind`, `httperr.Write`) — `ucp-go-error-handling-review`.

6. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

7. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — write в query-handler (`cqrs/query-is-read-only`), синхронный INSERT read-model в command-транзакции (`cqrs/read-model-synced-by-events`), bidirectional sync (`cqrs/projection-has-no-logic-or-backflow`), агрегат/Entity наружу из query (`cqrs/query-returns-read-model`), schema-coupled event-payload (`cqrs/events-not-coupled-to-write-schema`).
   - **Предупреждение** — загрузка агрегата ради read-DTO (`cqrs/read-via-projection-not-aggregate`), read-DTO из command (`cqrs/command-returns-minimum`), PG-триггеры sync (`cqrs/read-model-synced-by-events`), маркеры без pgx read-only enforcement (`cqrs/split-matches-maturity-level`), бизнес-логика в read-model (`cqrs/projection-has-no-logic-or-backflow`).
   - **Замечание** — полный split «just in case» (`cqrs/lightweight-first-full-on-evidence`), eventual consistency не задекларирована в API (`cqrs/eventual-consistency-declared`), нет rebuild-команды (`cqrs/read-model-is-rebuildable`).

## Что не входит

- sqlc-запросы и ViewRepository-реализация — `ucp-go-sqlc-review`. Outbox/consumer — `ucp-go-kafka-review`. Агрегат — `ucp-go-ddd-tactical-review`. Ошибки — `ucp-go-error-handling-review`.

$ARGUMENTS
