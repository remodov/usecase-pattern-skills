---
name: ucp-go-distributed-review
lang: go
description: Ревью распределённых паттернов в Go-сервисе (net/http + chi) по UCP — saga/compensation, idempotency (processed_event/middleware), eventual consistency, outbox+inbox, запрет 2PC; pgx-транзакции, sqlc, segmentio-kafka-go, gobreaker.
when_to_use: Изменения в cross-service flows, saga-оркестраторах (internal/saga/), idempotency-middleware, outbox/inbox, compensation-командах или коде с несколькими pgx.Tx.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Distributed Patterns (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/distributed-patterns/spec.md`
(`R-DIST-*`) и его **Go-реализации** `backend/distributed-patterns/references/go/implementation.md`.
Помни парадигму: в Go нет транзакционного менеджера — транзакция это явный `pgx.Tx`, пробрасываемый явно;
saga-оркестратор — обычная struct; нет аннотаций, нет магии — всё явно.

## Зависимости

- **`.claude/docs/backend/distributed-patterns/spec.md`** — общий контракт (`R-DIST-WHEN-*`/`SAGA-*`/`IDEM-*`/`EC-*`/`OBX-*`/`COMP-*`/`TX-*`).
- **`.claude/docs/backend/distributed-patterns/references/go/implementation.md`** — Go-реализация (pgx.Tx явно, sqlc `queries.WithTx(tx)`, outbox writer+relay, idempotency-middleware, DLQ через kafka-go).
- Парные: `backend/kafka/go/...` (outbox/idempotent consumer), `backend/cqrs/go/...` (EC read-model), `backend/resilience/go/...` (gobreaker, retry-go), `backend/observability/go/...` (read_projection_lag_seconds).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй конкретные коды (`distributed/every-step-has-compensation`, `distributed/no-two-phase-commit`), не только префикс.

2. **Скоп.** Saga-оркестраторы (`internal/saga/*.go`), таблицы `saga_*`/`processed_event`/`inbox_message`/`outbox_message`, cross-service consumer'ы (`adapters/in/kafka/`), idempotency-middleware (`adapters/in/http/middleware/`), compensation-команды, код с несколькими `pgx.Tx`; `git diff`.

3. **Прогон по группам.**

   ### `R-DIST-WHEN-*`
   - Распределённые паттерны при операции в одном сервисе + одном PG → `distributed/patterns-only-when-crossing-services`; достаточно одной `pgx.Tx`.
   - Микросервисы без бизнес-нужды (latency, debugging, failure modes) → `distributed/patterns-only-when-crossing-services`.

   ### `R-DIST-SAGA-*`
   - Orchestration vs choreography: 4+ шагов или branching → orchestration (`distributed/orchestration-versus-choreography`); 2–3 шага без branching → choreography (`distributed/orchestration-versus-choreography`).
   - Saga state в БД (`saga_<name>` таблица, поля `saga_id`/`status`/`current_step`/`payload` через sqlc) → `distributed/saga-state-is-persistent`.
   - `saga_id` сквозной в каждом сообщении → `distributed/saga-state-is-persistent`.
   - Orchestrator — отдельная struct в `internal/saga/`, не в UseCase Handler → `distributed/saga-separate-from-use-cases`.
   - 2PC/XA (в Go нет стандартного XA; `database/sql` не поддерживает XA) → `distributed/no-two-phase-commit`.
   - Saga без compensation → `distributed/every-step-has-compensation`.
   - Saga state in-memory (рестарт теряет in-flight saga) → `distributed/saga-state-is-persistent`.

   ### `R-DIST-IDEM-*`
   - Уникальный `event_id` / `message_id` (UUID v4/v7) в каждом cross-service сообщении → `distributed/message-has-unique-id`.
   - Receiver: `ExistsProcessedEvent` до обработки + `InsertProcessedEvent` в той же `pgx.Tx` → `distributed/receiver-deduplicates`.
   - HTTP-команды: chi-middleware с `(idempotency_key, command_hash, response_body, status_code)` в БД; повтор с тем же ключом → сохранённый ответ; другой `command_hash` → `409 Conflict` → `distributed/http-idempotency-record`.
   - Money: заголовок `Idempotency-Key` + UNIQUE `(provider_id, external_payment_id)` на уровне БД → `distributed/money-double-protection`.
   - TTL idempotency-записей 24–72 часа (`expires_at`-поле, фоновая очистка) → `distributed/http-idempotency-record`.
   - Receiver без dedup для money/critical → `distributed/receiver-deduplicates`.
   - Только receiver-side (producer тоже: `RequiredAcks: kafka.RequireAll`, `Balancer: &kafka.Hash{}`) → `distributed/money-double-protection`.
   - Новый UUID как `Idempotency-Key` на каждый retry → `distributed/idempotency-key-per-operation`.

   ### `R-DIST-EC-*`
   - Декларация в OpenAPI/swagger-комментариях (`swaggo/swag`) или `openapi.yaml` для eventual-consistent endpoint → `distributed/bounded-and-declared-staleness`.
   - Read-your-writes при необходимости: читать с write-side или передавать `version`-токен в response → `distributed/read-your-writes-when-required`.
   - Bounded staleness SLO + Prometheus-метрика `read_projection_lag_seconds` > порога → `distributed/bounded-and-declared-staleness`.
   - Causal consistency: `event.Version > current_version` перед `UpsertProjection`, иначе идемпотентный skip → `distributed/ordering-by-version`.
   - Молчаливая EC: endpoint возвращает stale-data без декларации → `distributed/bounded-and-declared-staleness`.
   - Strict consistency через 2PC под нагрузкой → `distributed-patterns/no-two-phase-commit`.

   ### `R-DIST-OBX-*`
   - Outbox writer (`outbox.Writer`) записывает в `outbox_message` в той же `pgx.Tx` (`queries.WithTx(tx)`) → `distributed/outbox-for-outgoing-events`.
   - Inbox pattern для critical-сценариев: сохранить в `inbox_message` до обработки → `distributed/inbox-for-critical-messages`.
   - БД — source of truth; Kafka — транспорт; relay публикует из `outbox_message` → `distributed/database-is-source-of-truth`.
   - Прямой `producer.WriteMessages` из command-handler без outbox → `distributed/outbox-for-outgoing-events`.
   - Публикация через goroutine-after-commit без outbox (нет атомарности с транзакцией) → `distributed/outbox-for-outgoing-events`.

   ### `R-DIST-COMP-*`
   - У каждой command в саге есть compensation-команда → `distributed/every-step-has-compensation`.
   - Compensation идемпотентен: проверяется по `(saga_id, step)` в БД → `distributed/compensation-is-semantic-and-idempotent`.
   - Semantic compensation: был платёж → refund (новая бизнес-транзакция), не технический rollback → `distributed/compensation-is-semantic-and-idempotent`.
   - Audit trail: статус `refunded`/`cancelled` + ссылка на оригинал; не DELETE → `distributed/compensation-is-semantic-and-idempotent`.
   - Compensation через outbox (at-least-once гарантия, та же pgx.Tx).
   - Compensation без DLQ + manual review → `distributed/compensation-is-semantic-and-idempotent`; сбой compensation без routing в DLQ-топик → `distributed/failed-compensation-goes-to-review`.
   - `DELETE FROM orders` как compensation → `distributed/compensation-is-semantic-and-idempotent`.

   ### `R-DIST-TX-*`
   - Последовательный commit по двум `pgx.Tx` разных БД без saga-recovery → `distributed/no-two-phase-commit`.
   - Единая «транзакция» через несколько `pgxpool.Pool` разных сервисов → `distributed/no-two-phase-commit`.
   - Попытка XA через `database/sql` (не поддерживается) → `distributed/no-two-phase-commit`.
   - Каждый шаг saga: один `pgx.Tx` + outbox writer в той же транзакции, `tx.Commit` только после записи в outbox → `distributed/no-two-phase-commit`.

4. **Grep-проверки:**
   - `Grep`: `tx1.Commit` + `tx2.Commit` в одной функции (→ `distributed/no-two-phase-commit`).
   - `Grep`: `producer.WriteMessages` / `kafka.Writer` в `handler`/`usecase` без `outbox` (→ `distributed/outbox-for-outgoing-events`).
   - `Grep`: `go func` / `goroutine` после `tx.Commit` с Kafka-записью (→ `distributed/outbox-for-outgoing-events`).
   - `Grep`: `DELETE FROM saga_` или `DELETE FROM orders` (→ `distributed/compensation-is-semantic-and-idempotent`).

5. **Cross-check:** outbox/consumer idempotency → `ucp-go-kafka-review`; EC read-model → `ucp-go-cqrs-review`; saga/idempotency-таблицы и индексы → `ucp-pg-runtime-review`; DLQ-топик + алёрт → `ucp-go-observability-review`.

6. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

7. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — saga без compensation (`distributed/every-step-has-compensation`), saga state in-memory (`distributed/saga-state-is-persistent`), receiver без dedup для money (`distributed/receiver-deduplicates`), `DELETE` как compensation (`distributed/compensation-is-semantic-and-idempotent`), прямой kafka-publish из handler без outbox (`distributed/outbox-for-outgoing-events`), последовательный commit по двум `pgx.Tx` разных БД (`distributed/no-two-phase-commit`).
   - **Предупреждение** — saga в UseCase Handler (`distributed/saga-separate-from-use-cases`), новый UUID как `Idempotency-Key` на retry (`distributed/idempotency-key-per-operation`), compensation без DLQ (`distributed/failed-compensation-goes-to-review`), молчаливая EC (`distributed/bounded-and-declared-staleness`), goroutine-after-commit без outbox (`distributed/outbox-for-outgoing-events`).
   - **Замечание** — saga для одного сервиса (`distributed/patterns-only-when-crossing-services`), нет bounded-staleness SLO (`distributed/bounded-and-declared-staleness`), нет `read_projection_lag_seconds` метрики.

## Что не входит

- Outbox/consumer-механика Kafka — `ucp-go-kafka-review`.
- EC read-model — `ucp-go-cqrs-review`.
- Saga/idempotency-таблицы, индексы и блокировки — `ucp-pg-runtime-review` / `ucp-pg-schema-review`.
- Retry/CB-конфиг (gobreaker, avast-retry-go) — `ucp-go-resilience-review`.

$ARGUMENTS
