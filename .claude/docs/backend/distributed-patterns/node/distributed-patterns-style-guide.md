# Distributed Patterns — Node Style Guide (saga + TypeORM + kafkajs)

Реализация язык-нейтрального контракта `../distributed-patterns-rules.md` (`R-DIST-*`) на Node/NestJS. Паттерны
(saga/idempotency/eventual consistency/outbox/compensation) архитектурные — одни на всех языках; меняется
реализация транзакций (`@Transactional` → `DataSource.transaction` / `EntityManager`) и форма запретов 2PC.

## 1. Когда нужны (`R-DIST-WHEN-*`)

`R-DIST-WHEN-1` — операция охватывает 2+ сервиса и не завершается одной локальной транзакцией. `R-DIST-WHEN-2` —
один сервис + один PG → обычная `DataSource.transaction` + атомарность БД, без распределённых паттернов.
`R-DIST-WHEN-3` — сначала проверь альтернативы (объединить BC, modular monolith — несколько Nest-модулей в одном
процессе). `R-DIST-WHEN-X1` — saga для двух операций в одной БД. `R-DIST-WHEN-X2` — микросервисы «из амбиций»
(latency, debugging, новые failure modes) — лучше modular monolith.

## 2. Saga (`R-DIST-SAGA-*`)

`R-DIST-SAGA-1` — saga, когда операция cross-service с локальными транзакциями на каждом шаге. `R-DIST-SAGA-2` —
**orchestration** (центральный координатор) для сложных saga (4+ шага, branching). `R-DIST-SAGA-3` — **choreography**
(события без координатора) для простых (2–3 шага). `R-DIST-SAGA-4` — **saga state в БД**: TypeORM-entity
`saga_<name>` (`sagaId`, `status`, `currentStep`, `payload jsonb`) — видимость, recovery, audit. `R-DIST-SAGA-5` —
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

`R-DIST-SAGA-X1` — 2PC/XA вместо saga (Kafka не XA; в Node-экосистеме XA-координатора и нет — не эмулировать).
`R-DIST-SAGA-X2` — saga без compensation («полусделанная» транзакция). `R-DIST-SAGA-X3` — saga state in-memory
(Map/RxJS-стейт). `R-DIST-SAGA-X4` — saga в одном handler с use case (orchestrator — отдельный компонент).

## 3. Idempotency (`R-DIST-IDEM-*`)

`R-DIST-IDEM-1` — у каждого cross-service сообщения уникальный id (`eventId`/`messageId`, UUID v7). `R-DIST-IDEM-2` —
receiver хранит `processed_event` (проверка до, запись в той же `DataSource.transaction`; cross-ref `R-KFK-IDEM-2`,
insert с `.orIgnore()` — UNIQUE-дедуп под race). `R-DIST-IDEM-3` — для HTTP-команд хранить
`(idempotencyKey, commandHash, response)` в PG; повтор с тем же ключом → сохранённый ответ; тот же ключ + другой
`commandHash` → `409 Conflict` (NestJS — guard/interceptor на write-эндпоинтах). `R-DIST-IDEM-4` — money:
`Idempotency-Key` + UNIQUE `(provider_id, external_payment_id)`. `R-DIST-IDEM-5` — TTL idempotency-записей 24–72ч.

`R-DIST-IDEM-X1` — receiver без dedup для money/critical. `R-DIST-IDEM-X2` — только receiver-side (producer тоже
exactly-once: kafkajs `idempotent: true`, `R-KFK-PROD-1`). `R-DIST-IDEM-X3` — `Idempotency-Key = randomUUID()` на
каждый retry (ключ генерируется один раз на бизнес-операцию и переиспользуется при повторе).

## 4. Eventual consistency (`R-DIST-EC-*`)

`R-DIST-EC-1` — декларация в OpenAPI: `@ApiOperation({ description: 'Read-проекция, задержка до N секунд' })`
на eventual-consistent эндпоинте. `R-DIST-EC-2` — read-your-writes при необходимости (читать из write-side /
version-токен клиенту). `R-DIST-EC-3` — bounded staleness с явным SLO + alert. `R-DIST-EC-4` — causal consistency
через `version`-поля (receiver применяет, только если `event.version > current.version`, иначе skip).

`R-DIST-EC-X1` — молчаливая EC (stale-data без декларации). `R-DIST-EC-X2` — strict consistency через 2PC под
нагрузкой (перепроектируй boundary или прими EC).

## 5. Outbox + Inbox (`R-DIST-OBX-*`)

`R-DIST-OBX-1` — **outbox** для исходящих событий обязателен (`R-KFK-OBX-*`; relay c
`FOR UPDATE SKIP LOCKED` через QueryBuilder — `node/kafka-style-guide.md` §3). `R-DIST-OBX-2` — **inbox** для
входящих (опционально, critical): сохранить сообщение в `inbox`-таблицу до обработки, обработать асинхронно.
`R-DIST-OBX-3` — single source of truth — БД сервиса; Kafka — транспорт (потеря Kafka → outbox продолжает копить).

`R-DIST-OBX-X1` — прямой `producer.send` из command-handler без outbox (`R-KFK-PROD-X4`). `R-DIST-OBX-X2` —
публикация после commit без outbox (TypeORM subscriber `afterInsert`/«after commit»-хук: падение между commit и
publish теряет событие — `R-KFK-OBX-X2`).

## 6. Compensation (`R-DIST-COMP-*`)

`R-DIST-COMP-1` — у каждой command в саге есть compensation-команда (`RequestPayment` ↔ `RefundPayment`).
`R-DIST-COMP-2` — compensation идемпотентен (saga может повторить, `R-DIST-IDEM-*`). `R-DIST-COMP-3` — **semantic
compensation**, не технический rollback (был платёж → compensation = refund новой транзакцией). `R-DIST-COMP-4` —
compensation оставляет audit trail (статус `refunded` + ссылка на оригинал), не DELETE/UPDATE-с-потерей.

`R-DIST-COMP-X1` — saga без compensation. `R-DIST-COMP-X2` — `DELETE` как compensation («создан заказ» →
`status: 'cancelled'`, не `repository.delete(order)`). `R-DIST-COMP-X3` — compensation, которое может упасть без
повторного compensation/DLQ (висящие деньги — task-queue + manual review).

## 7. Distributed transactions — чего НЕ делать (`R-DIST-TX-*`)

`R-DIST-TX-X1` — 2PC/XA в стеке (Kafka не XA, не масштабируется, SPOF; Node-драйверы XA не поддерживают —
не городить координатор руками). `R-DIST-TX-X2` — единая «распределённая» транзакция через несколько
`DataSource`-ов (две БД из одного use case с видимостью атомарности). `R-DIST-TX-X3` — цепочка последовательных
commit'ов по нескольким `DataSource`/`QueryRunner` (в т.ч. обёртки вроде `typeorm-transactional` поверх двух
datasource) — best-effort, не атомарность; при сбое между commit'ами inconsistency без recovery.

`R-DIST-TX-1` — saga с локальными транзакциями (стандарт). `R-DIST-TX-2` — outbox + idempotent consumer для
event-driven sync. `R-DIST-TX-3` — modular monolith (несколько BC-модулей Nest в одном процессе с одним PG) при
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
