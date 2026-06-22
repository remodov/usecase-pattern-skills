---
name: ucp-node-distributed-review
lang: node
description: Ревью распределённых паттернов в NestJS-микросервисах по UCP (коды R-DIST-*) — saga и compensation, idempotency (processed_event, dedup), eventual consistency, outbox+inbox, запрет 2PC/XA и multi-DataSource-цепочек.
when_to_use: Изменения в cross-service flows, saga-оркестраторах, idempotency-таблицах, multi-DataSource коде, compensation-командах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Distributed Patterns (Node / saga + TypeORM + kafkajs)

Ты ревьюишь распределённые паттерны на соответствие **контракту** `backend/distributed-patterns/distributed-patterns-rules.md`
(`R-DIST-*`) и **Node-реализации** `backend/distributed-patterns/node/distributed-patterns-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/distributed-patterns/distributed-patterns-rules.md`** + **`backend/distributed-patterns/node/distributed-patterns-style-guide.md`**.
- Парные: `backend/kafka/node/...` (outbox/idempotent), `cqrs` (EC), `backend/usecase-pattern/node/...` (граница TX), `pg-runtime`.

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-DIST-SAGA-X2`, `R-DIST-TX-X3`), не префикс.

2. **Скоп.** Saga-orchestrator, `saga_*`/`processed_event`/`inbox`-таблицы, cross-service consumers, multi-DataSource/`QueryRunner`-конфиги, compensation-команды; `git diff`.

3. **Прогон.**
   - **Когда (`R-DIST-WHEN-*`):** saga для одного сервиса/одной БД → `R-DIST-WHEN-X1`; микросервисы без бизнес-нужды → `R-DIST-WHEN-X2`.
   - **Saga (`R-DIST-SAGA-*`):** orchestration vs choreography по сложности; state в БД (in-memory Map/RxJS, в т.ч. `@nestjs/cqrs` Sagas → `R-DIST-SAGA-X3`); `sagaId` сквозной; saga отдельным `@Injectable` (в handler с use case → `R-DIST-SAGA-X4`); 2PC вместо saga → `R-DIST-SAGA-X1`; без compensation → `R-DIST-SAGA-X2`; шаг = state-переход + outbox в одной `DataSource.transaction`.
   - **Idempotency (`R-DIST-IDEM-*`):** `processed_event` (запись в той же транзакции, `.orIgnore()`); HTTP `(idempotencyKey, commandHash, response)`; money — двойная защита. Receiver без dedup → `R-DIST-IDEM-X1`. Только receiver-side (producer без `idempotent: true`) → `R-DIST-IDEM-X2`. Новый key на retry → `R-DIST-IDEM-X3`.
   - **EC (`R-DIST-EC-*`):** декларация + bounded-staleness SLO; молчаливая EC → `R-DIST-EC-X1`; strict через 2PC → `R-DIST-EC-X2`.
   - **Outbox/Inbox (`R-DIST-OBX-*`):** outbox обязателен; БД — source of truth; прямой `producer.send` без outbox → `R-DIST-OBX-X1`; publish после commit (subscriber `afterInsert`/after-commit-хук) без outbox → `R-DIST-OBX-X2`.
   - **Compensation (`R-DIST-COMP-*`):** semantic state-change, идемпотентна, audit. `DELETE` как compensation → `R-DIST-COMP-X2`; compensation без повторного/DLQ → `R-DIST-COMP-X3`.
   - **2PC (`R-DIST-TX-*`):** XA/2PC → `R-DIST-TX-X1`; несколько `DataSource` в одной «атомарной» операции → `R-DIST-TX-X2`; цепочка commit по нескольким `DataSource`/`QueryRunner` (в т.ч. `typeorm-transactional` поверх двух datasource) → `R-DIST-TX-X3`.

4. **Cross-check:** outbox/consumer idempotency — `ucp-node-kafka-review`; EC read-model — `ucp-node-cqrs-review`; saga/idempotency-таблицы и locks — `ucp-pg-runtime-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — saga без compensation (`R-DIST-SAGA-X2`), saga state in-memory (`R-DIST-SAGA-X3`), receiver без dedup для money (`R-DIST-IDEM-X1`), `DELETE` как compensation (`R-DIST-COMP-X2`), 2PC/XA или multi-DataSource-commit-цепочка (`R-DIST-TX-X1`/`X3`), прямой send без outbox (`R-DIST-OBX-X1`).
   - **Предупреждение** — saga в handler с use case (`R-DIST-SAGA-X4`), новый idempotency-key на retry (`R-DIST-IDEM-X3`), compensation без DLQ (`R-DIST-COMP-X3`), молчаливая EC (`R-DIST-EC-X1`).
   - **Замечание** — saga для одного сервиса (`R-DIST-WHEN-X1`), нет bounded-staleness SLO (`R-DIST-EC-3`).

## Что не входит

- Outbox/consumer-механика — `ucp-node-kafka-review`. EC read-model — `ucp-node-cqrs-review`.
- Saga/idempotency-таблицы и блокировки — `ucp-pg-runtime-review` / `ucp-pg-schema-review`.

$ARGUMENTS
