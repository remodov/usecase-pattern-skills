---
name: ucp-go-distributed-design
lang: go
description: Спроектировать распределённый сценарий в Go-микросервисах по UCP — saga orchestration/choreography со state в pgx/sqlc, idempotency middleware (chi), outbox+relay (kafka-go), compensation, eventual consistency, запрет 2PC/XA.
when_to_use: Триггеры — «saga для X», «cross-service процесс Y», «компенсация Z на Go». Для cross-service бизнес-операции с pgx/sqlc-стеком.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Distributed Patterns — проектирование (Go / net/http + chi)

Ты проектируешь распределённый сценарий по **контракту** `backend/distributed-patterns/spec.md`
(`R-DIST-*`) и **Go-реализации** `backend/distributed-patterns/references/go/implementation.md`.

Помни: в Go нет транзакционного менеджера — транзакция это явный `pgx.Tx`, передаваемый параметром или через
`context.Context`; saga-оркестратор — обычная struct в `internal/saga/`; всё явно, нет магии аннотаций.

Не делает: UseCase/Handler-обвязку (`ucp-go-pattern-design`), Kafka-продюсер/консьюмер без saga
(`ucp-go-kafka-design`), резилианс-обвязку (`ucp-go-resilience-design`), схему БД (`ucp-pg-schema-design`).

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды в обосновании, не в коде. Связанные:
   `backend/kafka/go/...` (outbox/idempotent consumer), `backend/cqrs/go/...` (EC read-model),
   `backend/usecase-pattern/go/...` (UoW-аналог через pgx.Tx), `pg-runtime` (saga/idempotency-таблицы).

2. **Проверь необходимость** (`R-DIST-WHEN-*`): распределённые паттерны только если операция cross-service.
   Один сервис + один PG → обычная `pgx.Tx` + sqlc. Сначала проверь альтернативы (объединить BC, modular monolith
   с общим `pgxpool.Pool`). Назови принятое решение.

3. **Saga** (`R-DIST-SAGA-*`): orchestration (отдельная struct `internal/saga/`, метод `Advance(ctx, event)`,
   state в `saga_<name>`-таблице через sqlc) для 4+ шагов/branching; choreography (события без координатора) для
   2–3; `saga_id` сквозной в каждом сообщении и заголовке Kafka; каждый шаг — отдельная `pgx.Tx`.

4. **Idempotency** (`R-DIST-IDEM-*`): уникальный `event_id`/`message_id` (UUID v4/v7); receiver проверяет
   `processed_event` атомарно в той же `pgx.Tx`; HTTP-команды — chi-middleware
   `adapters/in/http/middleware/idempotency.go` с `(idempotency_key, command_hash, response_body, status_code)`;
   повтор с тем же ключом → сохранённый ответ; другой `command_hash` → `409 Conflict`; money — заголовок
   `Idempotency-Key` + UNIQUE `(provider_id, external_payment_id)` на уровне БД; TTL 24–72ч.

5. **Eventual consistency** (`R-DIST-EC-*`): декларация в OpenAPI (`openapi.yaml` или `swaggo/swag`-комментарий);
   read-your-writes при необходимости — читать с primary или передавать `version`-токен клиенту; bounded-staleness
   SLO + Prometheus-метрика `read_projection_lag_seconds`; causal — `event.Version > current_version` перед
   применением, иначе идемпотентный skip.

6. **Outbox/Compensation** (`R-DIST-OBX/COMP-*`): outbox обязателен — `internal/outbox.Writer` (INSERT в той же
   `pgx.Tx`), relay-горутина через `errgroup` полит каждые 500мс и публикует через `segmentio/kafka-go`
   (`kafka.Writer`); на каждый шаг — идемпотентная **semantic** compensation (refund, не DELETE) с audit trail
   (статус `cancelled`/`refunded` + reference на оригинал); при сбое compensation — DLQ-топик + алёрт.

7. **Запрет** (`R-DIST-TX-*`): без 2PC/XA; `pgx` не поддерживает XA; нет последовательных `tx1.Commit; tx2.Commit`
   по разным сервисам/БД без saga-recovery. Самопроверка по чеклисту из
   `backend/distributed-patterns/references/go/implementation.md` §«Чеклист подключения».
   Предложи `ucp-go-distributed-review`.

## Антипаттерны, которые НЕ генерировать

- Saga для одного сервиса (`distributed/patterns-only-when-crossing-services`); saga без compensation (`distributed/every-step-has-compensation`/`distributed/every-step-has-compensation`);
  saga state in-memory (`distributed/saga-state-is-persistent`); saga-переходы внутри UseCase Handler (`distributed/saga-separate-from-use-cases`).
- Receiver без dedup для money/critical (`distributed/receiver-deduplicates`); новый `Idempotency-Key` на каждый retry (`distributed/idempotency-key-per-operation`).
- Молчаливая EC — stale-data без декларации в OpenAPI (`distributed/bounded-and-declared-staleness`).
- `DELETE` как compensation (`distributed/compensation-is-semantic-and-idempotent`); compensation без DLQ при сбое (`distributed/failed-compensation-goes-to-review`).
- 2PC/XA (`distributed/no-two-phase-commit`); `tx1.Commit; tx2.Commit` по двум БД без saga-recovery (`distributed/no-two-phase-commit`);
  прямой `producer.WriteMessages` из handler без outbox (`distributed/outbox-for-outgoing-events`).
- Relay через `time.Sleep`-цикл (используй `time.Ticker` + `errgroup`).

После работы скилла — обязательно `ucp-go-distributed-review`.

$ARGUMENTS
