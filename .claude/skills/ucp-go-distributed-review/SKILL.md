---
name: ucp-go-distributed-review
lang: go
description: Ревью распределённых паттернов в Go-сервисе (net/http + chi) по UCP (коды R-DIST-*) — saga/compensation, idempotency (processed_event/middleware), eventual consistency, outbox+inbox, запрет 2PC; pgx-транзакции, sqlc, segmentio-kafka-go, gobreaker.
when_to_use: Изменения в cross-service flows, saga-оркестраторах (internal/saga/), idempotency-middleware, outbox/inbox, compensation-командах или коде с несколькими pgx.Tx.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Distributed Patterns (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/distributed-patterns/distributed-patterns-rules.md`
(`R-DIST-*`) и его **Go-реализации** `backend/distributed-patterns/go/distributed-patterns-style-guide.md`.
Помни парадигму: в Go нет транзакционного менеджера — транзакция это явный `pgx.Tx`, пробрасываемый явно;
saga-оркестратор — обычная struct; нет аннотаций, нет магии — всё явно.

## Зависимости

- **`.claude/docs/backend/distributed-patterns/distributed-patterns-rules.md`** — общий контракт (`R-DIST-WHEN-*`/`SAGA-*`/`IDEM-*`/`EC-*`/`OBX-*`/`COMP-*`/`TX-*`).
- **`.claude/docs/backend/distributed-patterns/go/distributed-patterns-style-guide.md`** — Go-реализация (pgx.Tx явно, sqlc `queries.WithTx(tx)`, outbox writer+relay, idempotency-middleware, DLQ через kafka-go).
- Парные: `backend/kafka/go/...` (outbox/idempotent consumer), `backend/cqrs/go/...` (EC read-model), `backend/resilience/go/...` (gobreaker, retry-go), `backend/observability/go/...` (read_projection_lag_seconds).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй конкретные коды (`R-DIST-SAGA-X2`, `R-DIST-TX-X3`), не только префикс.

2. **Скоп.** Saga-оркестраторы (`internal/saga/*.go`), таблицы `saga_*`/`processed_event`/`inbox_message`/`outbox_message`, cross-service consumer'ы (`adapters/in/kafka/`), idempotency-middleware (`adapters/in/http/middleware/`), compensation-команды, код с несколькими `pgx.Tx`; `git diff`.

3. **Прогон по группам.**

   ### `R-DIST-WHEN-*`
   - Распределённые паттерны при операции в одном сервисе + одном PG → `R-DIST-WHEN-X1`; достаточно одной `pgx.Tx`.
   - Микросервисы без бизнес-нужды (latency, debugging, failure modes) → `R-DIST-WHEN-X2`.

   ### `R-DIST-SAGA-*`
   - Orchestration vs choreography: 4+ шагов или branching → orchestration (`R-DIST-SAGA-2`); 2–3 шага без branching → choreography (`R-DIST-SAGA-3`).
   - Saga state в БД (`saga_<name>` таблица, поля `saga_id`/`status`/`current_step`/`payload` через sqlc) → `R-DIST-SAGA-4`.
   - `saga_id` сквозной в каждом сообщении → `R-DIST-SAGA-5`.
   - Orchestrator — отдельная struct в `internal/saga/`, не в UseCase Handler → `R-DIST-SAGA-X4`.
   - 2PC/XA (в Go нет стандартного XA; `database/sql` не поддерживает XA) → `R-DIST-SAGA-X1`.
   - Saga без compensation → `R-DIST-SAGA-X2`.
   - Saga state in-memory (рестарт теряет in-flight saga) → `R-DIST-SAGA-X3`.

   ### `R-DIST-IDEM-*`
   - Уникальный `event_id` / `message_id` (UUID v4/v7) в каждом cross-service сообщении → `R-DIST-IDEM-1`.
   - Receiver: `ExistsProcessedEvent` до обработки + `InsertProcessedEvent` в той же `pgx.Tx` → `R-DIST-IDEM-2`.
   - HTTP-команды: chi-middleware с `(idempotency_key, command_hash, response_body, status_code)` в БД; повтор с тем же ключом → сохранённый ответ; другой `command_hash` → `409 Conflict` → `R-DIST-IDEM-3`.
   - Money: заголовок `Idempotency-Key` + UNIQUE `(provider_id, external_payment_id)` на уровне БД → `R-DIST-IDEM-4`.
   - TTL idempotency-записей 24–72 часа (`expires_at`-поле, фоновая очистка) → `R-DIST-IDEM-5`.
   - Receiver без dedup для money/critical → `R-DIST-IDEM-X1`.
   - Только receiver-side (producer тоже: `RequiredAcks: kafka.RequireAll`, `Balancer: &kafka.Hash{}`) → `R-DIST-IDEM-X2`.
   - Новый UUID как `Idempotency-Key` на каждый retry → `R-DIST-IDEM-X3`.

   ### `R-DIST-EC-*`
   - Декларация в OpenAPI/swagger-комментариях (`swaggo/swag`) или `openapi.yaml` для eventual-consistent endpoint → `R-DIST-EC-1`.
   - Read-your-writes при необходимости: читать с write-side или передавать `version`-токен в response → `R-DIST-EC-2`.
   - Bounded staleness SLO + Prometheus-метрика `read_projection_lag_seconds` > порога → `R-DIST-EC-3`.
   - Causal consistency: `event.Version > current_version` перед `UpsertProjection`, иначе идемпотентный skip → `R-DIST-EC-4`.
   - Молчаливая EC: endpoint возвращает stale-data без декларации → `R-DIST-EC-X1`.
   - Strict consistency через 2PC под нагрузкой → `R-DIST-EC-X2`.

   ### `R-DIST-OBX-*`
   - Outbox writer (`outbox.Writer`) записывает в `outbox_message` в той же `pgx.Tx` (`queries.WithTx(tx)`) → `R-DIST-OBX-1`.
   - Inbox pattern для critical-сценариев: сохранить в `inbox_message` до обработки → `R-DIST-OBX-2`.
   - БД — source of truth; Kafka — транспорт; relay публикует из `outbox_message` → `R-DIST-OBX-3`.
   - Прямой `producer.WriteMessages` из command-handler без outbox → `R-DIST-OBX-X1`.
   - Публикация через goroutine-after-commit без outbox (нет атомарности с транзакцией) → `R-DIST-OBX-X2`.

   ### `R-DIST-COMP-*`
   - У каждой command в саге есть compensation-команда → `R-DIST-COMP-1`.
   - Compensation идемпотентен: проверяется по `(saga_id, step)` в БД → `R-DIST-COMP-2`.
   - Semantic compensation: был платёж → refund (новая бизнес-транзакция), не технический rollback → `R-DIST-COMP-3`.
   - Audit trail: статус `refunded`/`cancelled` + ссылка на оригинал; не DELETE → `R-DIST-COMP-4`.
   - Compensation через outbox (at-least-once гарантия, та же pgx.Tx).
   - Compensation без DLQ + manual review → `R-DIST-COMP-X2`; сбой compensation без routing в DLQ-топик → `R-DIST-COMP-X3`.
   - `DELETE FROM orders` как compensation → `R-DIST-COMP-X2`.

   ### `R-DIST-TX-*`
   - Последовательный commit по двум `pgx.Tx` разных БД без saga-recovery → `R-DIST-TX-X3`.
   - Единая «транзакция» через несколько `pgxpool.Pool` разных сервисов → `R-DIST-TX-X2`.
   - Попытка XA через `database/sql` (не поддерживается) → `R-DIST-TX-X1`.
   - Каждый шаг saga: один `pgx.Tx` + outbox writer в той же транзакции, `tx.Commit` только после записи в outbox → `R-DIST-TX-1`.

4. **Grep-проверки:**
   - `Grep`: `tx1.Commit` + `tx2.Commit` в одной функции (→ `R-DIST-TX-X3`).
   - `Grep`: `producer.WriteMessages` / `kafka.Writer` в `handler`/`usecase` без `outbox` (→ `R-DIST-OBX-X1`).
   - `Grep`: `go func` / `goroutine` после `tx.Commit` с Kafka-записью (→ `R-DIST-OBX-X2`).
   - `Grep`: `DELETE FROM saga_` или `DELETE FROM orders` (→ `R-DIST-COMP-X2`).

5. **Cross-check:** outbox/consumer idempotency → `ucp-go-kafka-review`; EC read-model → `ucp-go-cqrs-review`; saga/idempotency-таблицы и индексы → `ucp-pg-runtime-review`; DLQ-топик + алёрт → `ucp-go-observability-review`.

6. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

7. **Серьёзность** (`RFF-12`):
   - **Критично** — saga без compensation (`R-DIST-SAGA-X2`), saga state in-memory (`R-DIST-SAGA-X3`), receiver без dedup для money (`R-DIST-IDEM-X1`), `DELETE` как compensation (`R-DIST-COMP-X2`), прямой kafka-publish из handler без outbox (`R-DIST-OBX-X1`), последовательный commit по двум `pgx.Tx` разных БД (`R-DIST-TX-X3`).
   - **Предупреждение** — saga в UseCase Handler (`R-DIST-SAGA-X4`), новый UUID как `Idempotency-Key` на retry (`R-DIST-IDEM-X3`), compensation без DLQ (`R-DIST-COMP-X3`), молчаливая EC (`R-DIST-EC-X1`), goroutine-after-commit без outbox (`R-DIST-OBX-X2`).
   - **Замечание** — saga для одного сервиса (`R-DIST-WHEN-X1`), нет bounded-staleness SLO (`R-DIST-EC-3`), нет `read_projection_lag_seconds` метрики.

## Что не входит

- Outbox/consumer-механика Kafka — `ucp-go-kafka-review`.
- EC read-model — `ucp-go-cqrs-review`.
- Saga/idempotency-таблицы, индексы и блокировки — `ucp-pg-runtime-review` / `ucp-pg-schema-review`.
- Retry/CB-конфиг (gobreaker, avast-retry-go) — `ucp-go-resilience-review`.

$ARGUMENTS
