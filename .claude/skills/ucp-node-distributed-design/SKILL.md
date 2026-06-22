---
name: ucp-node-distributed-design
lang: node
description: Спроектировать распределённый сценарий в NestJS-микросервисах по UCP (коды R-DIST-*) — saga orchestration/choreography со state-таблицей и сквозным sagaId, idempotency, outbox+inbox, compensation, eventual consistency, запрет 2PC/XA.
when_to_use: Триггеры — «saga для X», «cross-service процесс Y», «компенсация Z на ноде». Для cross-service бизнес-операции.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(eslint*)
---

# Distributed Patterns — проектирование (Node / saga + TypeORM + kafkajs)

Ты проектируешь распределённый сценарий по **контракту** `backend/distributed-patterns/distributed-patterns-rules.md`
(`R-DIST-*`) и **Node-реализации** `backend/distributed-patterns/node/distributed-patterns-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `backend/kafka/node/...` (outbox/idempotent consumer), `cqrs` (EC read-model), `backend/usecase-pattern/node/...` (граница TX), `pg-runtime` (saga/idempotency-таблицы).

2. **Проверь необходимость** (`R-DIST-WHEN-*`): только если операция cross-service. Один сервис+PG → локальная `DataSource.transaction`. Сначала альтернативы (объединить BC, modular monolith — несколько Nest-модулей в одном процессе). Назови решение.

3. **Saga** (`R-DIST-SAGA-*`): orchestration (центральный координатор, отдельный `@Injectable`, не handler) для 4+ шагов/branching; choreography (события) для 2–3; **state в БД** (`saga_<name>`: `sagaId`/`status`/`currentStep`/`payload jsonb`); `sagaId` сквозной; каждый шаг — state-переход + команда в outbox в одной `DataSource.transaction`. NB: `@nestjs/cqrs` Sagas (RxJS поверх in-memory EventBus) — **не** распределённая saga; durable-стейт-машина — Temporal, если в стеке.

4. **Idempotency** (`R-DIST-IDEM-*`): уникальный id сообщения (UUID v7); receiver `processed_event` (запись в той же транзакции, insert с `.orIgnore()`); HTTP — `(idempotencyKey, commandHash, response)` + guard/interceptor на write-эндпоинтах, конфликт hash → `409`; money — `Idempotency-Key` + UNIQUE `(provider, external_id)`; TTL 24–72ч.

5. **Eventual consistency** (`R-DIST-EC-*`): декларация в OpenAPI (`@ApiOperation({ description })`); read-your-writes если критично; bounded-staleness SLO + alert; causal через `version`-поля.

6. **Outbox/Compensation** (`R-DIST-OBX/COMP-*`): outbox обязателен (`ucp-node-kafka-design`); на каждый шаг — идемпотентная **semantic** compensation (refund, не rollback) с audit; DLQ при сбое compensation.

7. **Запрет** (`R-DIST-TX-*`): без 2PC/XA и multi-DataSource-commit-цепочек (в т.ч. `typeorm-transactional` поверх двух datasource). Самопроверка (§8) + предложи `ucp-node-distributed-review`.

## Антипаттерны, которые НЕ генерировать

- Saga для одного сервиса (`R-DIST-WHEN-X1`); saga без compensation (`R-DIST-SAGA-X2`/`R-DIST-COMP-X1`); saga state in-memory (Map/RxJS-стейт, `R-DIST-SAGA-X3`); saga в одном handler с use case (`R-DIST-SAGA-X4`).
- Receiver без dedup для money (`R-DIST-IDEM-X1`); idempotency-key новый на каждый retry (`R-DIST-IDEM-X3`); молчаливая EC (`R-DIST-EC-X1`).
- `DELETE` как compensation (`R-DIST-COMP-X2`); compensation без повторного compensation/DLQ (`R-DIST-COMP-X3`).
- 2PC/XA (`R-DIST-TX-X1`); multi-DataSource-commit-цепочка (`R-DIST-TX-X3`); прямой `producer.send` без outbox (`R-DIST-OBX-X1`).

После работы скилла — обязательно `ucp-node-distributed-review`.

$ARGUMENTS
