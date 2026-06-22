---
name: ucp-go-cqrs-review
lang: go
description: Ревью CQRS-разделения в Go-сервисе (net/http + chi) по UCP (коды R-CQRS-*) — Command/Query-интерфейсы-маркеры, pgx read-only tx, sqlc ViewRepository, outbox+segmentio/kafka-go, idempotent consumer, eventual consistency в API.
when_to_use: Ревью Handler-структур с маркерами Command/Query, OrderViewRepository, read-DTO, outbox-репозиториев, Kafka-консюмеров read-side.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью CQRS (Go / net/http + chi)

Ты ревьюишь CQRS на соответствие **контракту** `backend/cqrs/cqrs-rules.md` (`R-CQRS-*`) и **Go-реализации** `backend/cqrs/go/cqrs-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/cqrs/cqrs-rules.md`** + **`backend/cqrs/go/cqrs-style-guide.md`**.
- Парные: `backend/usecase-pattern/go/...` (`Command`/`Query`/Handler), `backend/error-handling/go/error-handling-style-guide.md` (`R-ERR-MAP-*`, `apperr.Kind`), `backend/kafka/...` (outbox/idempotent), `backend/ddd-tactical/...` (агрегат).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй коды (`R-CQRS-QRY-X2`), не префикс.

2. **Скоп.** Handler-структуры реализующие `Command`/`Query`-маркеры (`core/cqrs/cqrs.go`), `*_view_repository.go`, read-DTO в `core/<bc>/dto/view/`, outbox-репозитории (`adapters/out/outbox/`), Kafka read-side консюмеры (`adapters/in/kafka/`), chi-хендлеры с eventual-consistency; `git diff`.

3. **Прогон.**
   - **Когда/уровень (`R-CQRS-WHEN/TIER-*`):** уровень соответствует зрелости; lightweight-маркеры обязаны иметь enforcement (pgx read-only транзакция `pgx.TxOptions{AccessMode: pgx.ReadOnly}`) — иначе `R-CQRS-TIER-X1`; полный split без боли → `R-CQRS-WHEN-X1`; event-driven read-model с одним `<X>Repository` → `R-CQRS-TIER-X2`.
   - **Command (`R-CQRS-CMD-*`):** `struct` реализует маркер `core/cqrs.Command` (неэкспортируемый `isCommand()`), меняет один агрегат через rw-транзакцию pgx, возвращает id/статус. Read-DTO из command → `R-CQRS-CMD-X2`. SELECT «для чтения потом» в command → `R-CQRS-CMD-X1`. Несколько агрегатов без саги → `R-CQRS-CMD-X3`.
   - **Query (`R-CQRS-QRY-*`):** `struct` реализует маркер `core/cqrs.Query` (неэкспортируемый `isQuery()`), читает через `<X>ViewRepository` с read-only транзакцией pgx, без commit. Write в query → `R-CQRS-QRY-X1`. Загружает агрегат через `<X>Repository` вместо `<X>ViewRepository` → `R-CQRS-QRY-X2`. Возвращает `*Aggregate` или Entity → `R-CQRS-QRY-X3`. Вызывает доменный метод → нарушение `R-CQRS-QRY-4`.
   - **Read-model (`R-CQRS-RM-*`):** денормализована (join'ов нет), независима от write-схемы, восстановима (есть rebuild-команда в `cmd/rebuild/`). Бизнес-логика в read-model → `R-CQRS-RM-X1`. Source-of-truth read-model → `R-CQRS-RM-X2`. Bidirectional sync → `R-CQRS-RM-X3`.
   - **Sync (`R-CQRS-SYNC-*`):** outbox+`segmentio/kafka-go`, idempotent consumer (`processed_event`-таблица или version-проверка), rebuild при бутстрапе, eventual consistency задекларирована (заголовок/OpenAPI). Синхронный `INSERT INTO order_summary` в command-транзакции → `R-CQRS-SYNC-X1`. PG-триггеры → `R-CQRS-SYNC-X2`. Payload = sqlc-структура write-схемы → `R-CQRS-SYNC-X3`.

4. **Grep-проверки.** Запускай до вынесения findings:
   - `Grep`: `pgx.TxOptions{}` без `AccessMode: pgx.ReadOnly` в query-handler — кандидат `R-CQRS-TIER-X1`.
   - `Grep`: `tx.Exec\|tx.Query` в `*_query_handler.go` — кандидат `R-CQRS-QRY-X1`.
   - `Grep`: `db.Order\|db\.` в struct-полях event-payload — кандидат `R-CQRS-SYNC-X3`.
   - `Grep`: `INSERT INTO order_summary` (или аналогичное) в `*_command_handler.go` / `*_handler.go` — кандидат `R-CQRS-SYNC-X1`.
   - `go vet ./...` — базовая санитарная проверка Go-кода.

5. **Cross-check:** `<X>ViewRepository`-реализация и sqlc-запросы — `ucp-go-sqlc-review`; outbox/idempotent consumer — `ucp-go-kafka-review`; агрегат на write-side — `ucp-go-ddd-tactical-review`; ошибки domain → `R-ERR-MAP-*` (`apperr.Kind`, `httperr.Write`) — `ucp-go-error-handling-review`.

6. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

7. **Серьёзность** (`RFF-12`):
   - **Критично** — write в query-handler (`R-CQRS-QRY-X1`), синхронный INSERT read-model в command-транзакции (`R-CQRS-SYNC-X1`), bidirectional sync (`R-CQRS-RM-X3`), агрегат/Entity наружу из query (`R-CQRS-QRY-X3`), schema-coupled event-payload (`R-CQRS-SYNC-X3`).
   - **Предупреждение** — загрузка агрегата ради read-DTO (`R-CQRS-QRY-X2`), read-DTO из command (`R-CQRS-CMD-X2`), PG-триггеры sync (`R-CQRS-SYNC-X2`), маркеры без pgx read-only enforcement (`R-CQRS-TIER-X1`), бизнес-логика в read-model (`R-CQRS-RM-X1`).
   - **Замечание** — полный split «just in case» (`R-CQRS-WHEN-X1`), eventual consistency не задекларирована в API (`R-CQRS-SYNC-4`), нет rebuild-команды (`R-CQRS-RM-4`).

## Что не входит

- sqlc-запросы и ViewRepository-реализация — `ucp-go-sqlc-review`. Outbox/consumer — `ucp-go-kafka-review`. Агрегат — `ucp-go-ddd-tactical-review`. Ошибки — `ucp-go-error-handling-review`.

$ARGUMENTS
