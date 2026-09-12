# Distributed Patterns — реализация на Node (saga + TypeORM + kafkajs)

Реализация язык-нейтрального контракта `../spec.md` (`R-DIST-*`) на Node/NestJS. Паттерны
(saga/idempotency/eventual consistency/outbox/compensation) архитектурные — одни на всех языках; меняется
реализация транзакций (`@Transactional` → `DataSource.transaction` / `EntityManager`) и форма запретов 2PC.

## 1. Когда нужны (`R-DIST-WHEN-*`)

`distributed/patterns-only-when-crossing-services` — операция охватывает 2+ сервиса и не завершается одной локальной транзакцией. `distributed/patterns-only-when-crossing-services` —
один сервис + один PG → обычная `DataSource.transaction` + атомарность БД, без распределённых паттернов.
`distributed/patterns-only-when-crossing-services` — сначала проверь альтернативы (объединить BC, modular monolith — несколько Nest-модулей в одном
процессе). `distributed/patterns-only-when-crossing-services` — saga для двух операций в одной БД. `distributed/patterns-only-when-crossing-services` — микросервисы «из амбиций»
(latency, debugging, новые failure modes) — лучше modular monolith.

## 2. Saga (`R-DIST-SAGA-*`)

`distributed/orchestration-versus-choreography` — saga, когда операция cross-service с локальными транзакциями на каждом шаге. `distributed/orchestration-versus-choreography` —
**orchestration** (центральный координатор) для сложных saga (4+ шага, branching). `distributed/orchestration-versus-choreography` — **choreography**
(события без координатора) для простых (2–3 шага). `distributed/saga-state-is-persistent` — **saga state в БД**: TypeORM-entity
`saga_<name>` (`sagaId`, `status`, `currentStep`, `payload jsonb`) — видимость, recovery, audit. `distributed/saga-state-is-persistent` —
`sagaId` сквозной в каждом сообщении (Kafka header / поле payload).

Orchestrator — отдельный `@Injectable` (`OrderSagaOrchestrator`), не handler: реагирует на события шагов
(kafkajs-consumer), продвигает state в БД и шлёт следующую команду через outbox — всё в одной
`DataSource.transaction`. NB: `@nestjs/cqrs` Sagas (RxJS поверх in-memory EventBus) — **не** распределённая saga:
state не персистентен, событие живёт в одном процессе. Для durable-оркестрации со стейт-машиной — Temporal
(`@temporalio/*`), если в стеке.

```ts
// PREFER: шаг саги = state-переход + команда в outbox атомарно
await this.dataSource.transaction(async (m) => {
  await m.update(OrderSagaEntity, { sagaId }, { status: 'PAYMENT_REQUESTED', currentStep: 2 });
  await m.insert(OutboxEventEntity, toOutbox(new RequestPaymentCommand(sagaId, orderId)));
});
// AVOID: this.state.set(sagaId, 'PAYMENT_REQUESTED') — in-memory Map, рестарт теряет in-flight saga
```

`distributed/no-two-phase-commit` — 2PC/XA вместо saga (Kafka не XA; в Node-экосистеме XA-координатора и нет — не эмулировать).
`distributed/every-step-has-compensation` — saga без compensation («полусделанная» транзакция). `distributed/saga-state-is-persistent` — saga state in-memory
(Map/RxJS-стейт). `distributed/saga-separate-from-use-cases` — saga в одном handler с use case (orchestrator — отдельный компонент).

## 3. Idempotency (`R-DIST-IDEM-*`)

`distributed/message-has-unique-id` — у каждого cross-service сообщения уникальный id (`eventId`/`messageId`, UUID v7). `distributed/receiver-deduplicates` —
receiver хранит `processed_event` (проверка до, запись в той же `DataSource.transaction`; cross-ref `kafka/processed-record-in-same-transaction`,
insert с `.orIgnore()` — UNIQUE-дедуп под race). `distributed/http-idempotency-record` — для HTTP-команд хранить
`(idempotencyKey, commandHash, response)` в PG; повтор с тем же ключом → сохранённый ответ; тот же ключ + другой
`commandHash` → `409 Conflict` (NestJS — guard/interceptor на write-эндпоинтах). `distributed/money-double-protection` — money:
`Idempotency-Key` + UNIQUE `(provider_id, external_payment_id)`. `distributed/http-idempotency-record` — TTL idempotency-записей 24–72ч.

`distributed/receiver-deduplicates` — receiver без dedup для money/critical. `distributed/money-double-protection` — только receiver-side (producer тоже
exactly-once: kafkajs `idempotent: true`, `kafka/producer-is-idempotent`). `distributed/idempotency-key-per-operation` — `Idempotency-Key = randomUUID()` на
каждый retry (ключ генерируется один раз на бизнес-операцию и переиспользуется при повторе).

## 4. Eventual consistency (`R-DIST-EC-*`)

`distributed/bounded-and-declared-staleness` — декларация в OpenAPI: `@ApiOperation({ description: 'Read-проекция, задержка до N секунд' })`
на eventual-consistent эндпоинте. `distributed/read-your-writes-when-required` — read-your-writes при необходимости (читать из write-side /
version-токен клиенту). `distributed/bounded-and-declared-staleness` — bounded staleness с явным SLO + alert. `distributed/ordering-by-version` — causal consistency
через `version`-поля (receiver применяет, только если `event.version > current.version`, иначе skip).

`distributed/bounded-and-declared-staleness` — молчаливая EC (stale-data без декларации). `distributed-patterns/no-two-phase-commit` — strict consistency через 2PC под
нагрузкой (перепроектируй boundary или прими EC).

## 5. Outbox + Inbox (`R-DIST-OBX-*`)

`distributed/outbox-for-outgoing-events` — **outbox** для исходящих событий обязателен (`R-KFK-OBX-*`; relay c
`FOR UPDATE SKIP LOCKED` через QueryBuilder — `node/implementation.md` §3). `distributed/inbox-for-critical-messages` — **inbox** для
входящих (опционально, critical): сохранить сообщение в `inbox`-таблицу до обработки, обработать асинхронно.
`distributed/database-is-source-of-truth` — single source of truth — БД сервиса; Kafka — транспорт (потеря Kafka → outbox продолжает копить).

`distributed/outbox-for-outgoing-events` — прямой `producer.send` из command-handler без outbox (`kafka/publish-via-outbox`). `distributed/outbox-for-outgoing-events` —
публикация после commit без outbox (TypeORM subscriber `afterInsert`/«after commit»-хук: падение между commit и
publish теряет событие — `kafka/publish-via-outbox`).

## 6. Compensation (`R-DIST-COMP-*`)

`distributed/every-step-has-compensation` — у каждой command в саге есть compensation-команда (`RequestPayment` ↔ `RefundPayment`).
`distributed/compensation-is-semantic-and-idempotent` — compensation идемпотентен (saga может повторить, `R-DIST-IDEM-*`). `distributed/compensation-is-semantic-and-idempotent` — **semantic
compensation**, не технический rollback (был платёж → compensation = refund новой транзакцией). `distributed/compensation-is-semantic-and-idempotent` —
compensation оставляет audit trail (статус `refunded` + ссылка на оригинал), не DELETE/UPDATE-с-потерей.

`distributed/every-step-has-compensation` — saga без compensation. `distributed/compensation-is-semantic-and-idempotent` — `DELETE` как compensation («создан заказ» →
`status: 'cancelled'`, не `repository.delete(order)`). `distributed/failed-compensation-goes-to-review` — compensation, которое может упасть без
повторного compensation/DLQ (висящие деньги — task-queue + manual review).

## 7. Distributed transactions — чего НЕ делать (`R-DIST-TX-*`)

`distributed/no-two-phase-commit` — 2PC/XA в стеке (Kafka не XA, не масштабируется, SPOF; Node-драйверы XA не поддерживают —
не городить координатор руками). `distributed/no-two-phase-commit` — единая «распределённая» транзакция через несколько
`DataSource`-ов (две БД из одного use case с видимостью атомарности). `distributed/no-two-phase-commit` — цепочка последовательных
commit'ов по нескольким `DataSource`/`QueryRunner` (в т.ч. обёртки вроде `typeorm-transactional` поверх двух
datasource) — best-effort, не атомарность; при сбое между commit'ами inconsistency без recovery.

`distributed/no-two-phase-commit` — saga с локальными транзакциями (стандарт). `distributed/no-two-phase-commit` — outbox + idempotent consumer для
event-driven sync. `distributed/patterns-only-when-crossing-services` — modular monolith (несколько BC-модулей Nest в одном процессе с одним PG) при
tight coupling — локальная `DataSource.transaction` работает.

## 8. Чеклист подключения к новому сервису (Node/NestJS)

1. Распределённые паттерны только при cross-service операции; иначе локальная `DataSource.transaction`.
2. Saga: orchestrator отдельным `@Injectable`, state в `saga_<name>`-таблице (не `@nestjs/cqrs` in-memory Sagas),
   `sagaId` сквозной, compensation на каждый шаг.
3. Idempotency: уникальный `eventId`, `processed_event` с `.orIgnore()`, HTTP — `Idempotency-Key`-interceptor,
   money — двойная защита, producer+receiver.
4. Eventual consistency задекларирована в OpenAPI, bounded-staleness SLO; нет молчаливой EC.
5. Outbox обязателен; БД — source of truth; нет прямого send из handler и «after commit»-хуков вместо outbox.
6. Compensation — semantic state-change с audit, идемпотентен, есть DLQ при сбое.
7. Нет 2PC/XA и multi-DataSource-commit-цепочек.
