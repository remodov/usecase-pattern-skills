---
name: ucp-node-distributed-review
lang: node
description: Ревью распределённых паттернов в NestJS-микросервисах по UCP (требования distributed-patterns/*) — saga и compensation, idempotency (processed_event, dedup), eventual consistency, outbox+inbox, запрет 2PC/XA и multi-DataSource-цепочек.
when_to_use: Изменения в cross-service flows, saga-оркестраторах, idempotency-таблицах, multi-DataSource коде, compensation-командах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Distributed Patterns (Node / saga + TypeORM + kafkajs)

Ты ревьюишь распределённые паттерны на соответствие **контракту** `backend/distributed-patterns/spec.md`
(`R-DIST-*`) и **Node-реализации** `backend/distributed-patterns/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/distributed-patterns/spec.md`** + **`backend/distributed-patterns/references/node/implementation.md`**.
- Парные: `backend/kafka/node/...` (outbox/idempotent), `cqrs` (EC), `backend/usecase-pattern/node/...` (граница TX), `pg-runtime`.

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`distributed/every-step-has-compensation`, `distributed/no-two-phase-commit`), не префикс.

2. **Скоп.** Saga-orchestrator, `saga_*`/`processed_event`/`inbox`-таблицы, cross-service consumers, multi-DataSource/`QueryRunner`-конфиги, compensation-команды; `git diff`.

3. **Прогон.**
   - **Когда (`R-DIST-WHEN-*`):** saga для одного сервиса/одной БД → `distributed/patterns-only-when-crossing-services`; микросервисы без бизнес-нужды → `distributed/patterns-only-when-crossing-services`.
   - **Saga (`R-DIST-SAGA-*`):** orchestration vs choreography по сложности; state в БД (in-memory Map/RxJS, в т.ч. `@nestjs/cqrs` Sagas → `distributed/saga-state-is-persistent`); `sagaId` сквозной; saga отдельным `@Injectable` (в handler с use case → `distributed/saga-separate-from-use-cases`); 2PC вместо saga → `distributed/no-two-phase-commit`; без compensation → `distributed/every-step-has-compensation`; шаг = state-переход + outbox в одной `DataSource.transaction`.
   - **Idempotency (`R-DIST-IDEM-*`):** `processed_event` (запись в той же транзакции, `.orIgnore()`); HTTP `(idempotencyKey, commandHash, response)`; money — двойная защита. Receiver без dedup → `distributed/receiver-deduplicates`. Только receiver-side (producer без `idempotent: true`) → `distributed/money-double-protection`. Новый key на retry → `distributed/idempotency-key-per-operation`.
   - **EC (`R-DIST-EC-*`):** декларация + bounded-staleness SLO; молчаливая EC → `distributed/bounded-and-declared-staleness`; strict через 2PC → `distributed-patterns/no-two-phase-commit`.
   - **Outbox/Inbox (`R-DIST-OBX-*`):** outbox обязателен; БД — source of truth; прямой `producer.send` без outbox → `distributed/outbox-for-outgoing-events`; publish после commit (subscriber `afterInsert`/after-commit-хук) без outbox → `distributed/outbox-for-outgoing-events`.
   - **Compensation (`R-DIST-COMP-*`):** semantic state-change, идемпотентна, audit. `DELETE` как compensation → `distributed/compensation-is-semantic-and-idempotent`; compensation без повторного/DLQ → `distributed/failed-compensation-goes-to-review`.
   - **2PC (`R-DIST-TX-*`):** XA/2PC → `distributed/no-two-phase-commit`; несколько `DataSource` в одной «атомарной» операции → `distributed/no-two-phase-commit`; цепочка commit по нескольким `DataSource`/`QueryRunner` (в т.ч. `typeorm-transactional` поверх двух datasource) → `distributed/no-two-phase-commit`.

4. **Cross-check:** outbox/consumer idempotency — `ucp-node-kafka-review`; EC read-model — `ucp-node-cqrs-review`; saga/idempotency-таблицы и locks — `ucp-pg-runtime-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — saga без compensation (`distributed/every-step-has-compensation`), saga state in-memory (`distributed/saga-state-is-persistent`), receiver без dedup для money (`distributed/receiver-deduplicates`), `DELETE` как compensation (`distributed/compensation-is-semantic-and-idempotent`), 2PC/XA или multi-DataSource-commit-цепочка (`distributed/no-two-phase-commit`/`X3`), прямой send без outbox (`distributed/outbox-for-outgoing-events`).
   - **Предупреждение** — saga в handler с use case (`distributed/saga-separate-from-use-cases`), новый idempotency-key на retry (`distributed/idempotency-key-per-operation`), compensation без DLQ (`distributed/failed-compensation-goes-to-review`), молчаливая EC (`distributed/bounded-and-declared-staleness`).
   - **Замечание** — saga для одного сервиса (`distributed/patterns-only-when-crossing-services`), нет bounded-staleness SLO (`distributed/bounded-and-declared-staleness`).

## Что не входит

- Outbox/consumer-механика — `ucp-node-kafka-review`. EC read-model — `ucp-node-cqrs-review`.
- Saga/idempotency-таблицы и блокировки — `ucp-pg-runtime-review` / `ucp-pg-schema-review`.

$ARGUMENTS
