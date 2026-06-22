# Kafka — Node Style Guide (kafkajs)

Реализация язык-нейтрального контракта `../kafka-rules.md` (`R-KFK-*`) на Node/NestJS с **kafkajs**
(низкоуровневый клиент в обёртке-провайдере; Nest microservices Kafka-transport не даёт ручного управления
offset'ами — не используем для бизнес-consumer'ов). Коды общие с Java/Python; меняется клиент, семантика одна.

## 1. Producer (`R-KFK-PROD-*`)

`R-KFK-PROD-1` — идемпотентный producer: `kafka.producer({ idempotent: true, maxInFlightRequests: 5 })`
(требует `acks: -1` = all; kafkajs кидает ошибку при другом значении). `R-KFK-PROD-2` — `key` обязателен для
бизнес-событий = **aggregate id** — ordering per-aggregate. `R-KFK-PROD-3` — JSON-сериализация
(`value: JSON.stringify(event)`); Avro/Protobuf + Schema Registry (`@kafkajs/confluent-schema-registry`) — для
bandwidth-топиков. `R-KFK-PROD-4` — domain-события **не** через прямой `producer.send(...)` из handler — через **outbox**.

```ts
// PREFER
const producer = kafka.producer({ idempotent: true, maxInFlightRequests: 5 });
await producer.send({
  topic: 'orders.confirmed', acks: -1,
  messages: [{ key: String(order.id), value: JSON.stringify(event) }],
});
// AVOID: producer.send({ acks: 1, messages: [{ value: ... }] })  — без key, без репликации
```

`R-KFK-PROD-X1` — `idempotent: false` в проде. `R-KFK-PROD-X2` — `acks: 0`/`acks: 1`. `R-KFK-PROD-X3` — send без
key для бизнес-событий. `R-KFK-PROD-X4` — `producer.send` из той же транзакции (`DataSource.transaction`), что
DB-операция: Kafka не XA, rollback БД не откатит publish — outbox.

## 2. Consumer (`R-KFK-CONS-*`)

`R-KFK-CONS-1` — уникальный `groupId: '<service>-<purpose>'` per-роль. `R-KFK-CONS-2` — **ручное управление
offset'ами**: `consumer.run({ autoCommit: false, eachMessage })`, `consumer.commitOffsets([...])` **после** успешной
обработки (offset = `message.offset + 1` — коммитится следующий к чтению). `R-KFK-CONS-3` — обработчик идемпотентен
(`R-KFK-IDEM-*`). `R-KFK-CONS-4` — `subscribe({ fromBeginning: true })` для critical-consumer'ов (аналог
`auto.offset.reset: earliest`). `R-KFK-CONS-5` — concurrency через `partitionsConsumedConcurrently` ≤ числа партиций.
`R-KFK-CONS-6` — у kafkajs нет `max.poll.interval.ms`; аналог — `sessionTimeout`/`rebalanceTimeout` + обязательный
`await heartbeat()` внутри долгого `eachMessage`, иначе rebalance посреди обработки.

```ts
const consumer = kafka.consumer({ groupId: 'billing-order-confirmed' });
await consumer.subscribe({ topic: 'orders.confirmed', fromBeginning: true });
await consumer.run({
  autoCommit: false,
  partitionsConsumedConcurrently: 3,
  eachMessage: async ({ topic, partition, message, heartbeat }) => {
    const event = orderConfirmedSchema.parse(JSON.parse(message.value!.toString()));
    await handler.handle(event);                       // идемпотентен по eventId (R-KFK-IDEM)
    await consumer.commitOffsets([{ topic, partition, offset: String(Number(message.offset) + 1) }]);
  },
});
```

`R-KFK-CONS-X1` — `autoCommit: true` (дефолт kafkajs!) в проде — offset уходит до завершения обработки.
`R-KFK-CONS-X2` — блокировка event loop / `await sleep(...)` >1s в `eachMessage` без `heartbeat()` (rebalance).
`R-KFK-CONS-X3` — нет `groupId`/общий на разные consumer'ы. `R-KFK-CONS-X4` — HTTP к внешней системе из
`eachMessage` без CB/bulkhead (`R-RES-WHERE-1`, cockatiel — `node/resilience-style-guide.md`).

## 3. Outbox publishing (`R-KFK-OBX-*`)

`R-KFK-OBX-1` — domain-события пишутся в `outbox`-таблицу в той же `DataSource.transaction`, что бизнес-изменение,
не `producer.send` из handler. `R-KFK-OBX-2` — **outbox-relay** — отдельный `@Injectable` c `@Interval`
(`@nestjs/schedule`): читает unpublished с `FOR UPDATE SKIP LOCKED` через QueryBuilder
(`R-TYPEORM-*`, `PG-L-021`), публикует через kafkajs, проставляет `published_at`. `R-KFK-OBX-3` — topic из
`event_type`/`aggregate_type`. `R-KFK-OBX-4` — relay обрабатывает batch (10–50), не по одному.

```ts
await this.dataSource.transaction(async (manager) => {
  const events = await manager.getRepository(OutboxEventEntity).createQueryBuilder('e')
    .setLock('pessimistic_write').setOnLocked('skip_locked')
    .where('e.publishedAt IS NULL').orderBy('e.id').take(50).getMany();
  await this.producer.send({ topic, acks: -1, messages: events.map(toMessage) });
  await manager.update(OutboxEventEntity, events.map((e) => e.id), { publishedAt: new Date() });
});
```

`R-KFK-OBX-X1` — `producer.send` из транзакции с DB-операцией. `R-KFK-OBX-X2` — публикация после commit без outbox
(подписка на «after commit», падение между commit и publish теряет событие). `R-KFK-OBX-X3` — outbox без
`published_at`/partial-индекса `WHERE published_at IS NULL` (full scan).

## 4. Idempotent consumer (`R-KFK-IDEM-*`)

`R-KFK-IDEM-1` — у события уникальный `eventId` (UUID v7) в payload/header; consumer проверяет, обрабатывалось ли.
`R-KFK-IDEM-2` — таблица `processed_event` в PG с PK на `event_id` (UNIQUE-дедуп под race); TTL — partition-drop /
background-job. `R-KFK-IDEM-3` — запись в `processed_event` и бизнес-результат — в **одной**
`DataSource.transaction`. `R-KFK-IDEM-4` — money: двойная защита — `eventId` + `Idempotency-Key` на downstream HTTP.

```ts
// PREFER: dedup + бизнес-апдейт атомарно
await this.dataSource.transaction(async (m) => {
  const inserted = await m.createQueryBuilder().insert().into(ProcessedEventEntity)
    .values({ eventId: event.eventId }).orIgnore().execute();
  if (!inserted.identifiers.length) return;            // duplicate, skip
  await this.applyBusinessChange(m, event);
});
// AVOID: обработка без проверки eventId; dedup по message.offset
```

`R-KFK-IDEM-X1` — consumer без проверки `eventId` там, где дубль критичен. `R-KFK-IDEM-X2` — Kafka offset как
dedup-ключ (зависит от group; новый group → всё «впервые»).

## 5. Retry topic + DLQ (`R-KFK-RTRY-*`)

`R-KFK-RTRY-1` — retry-топики с возрастающим delay (`orders.confirmed.retry.1m/10m`, заголовок `x-attempt`);
у kafkajs нет аналога `@RetryableTopic` — публикация в retry-топик из catch в `eachMessage` + отдельный
retry-consumer, который `consumer.pause()` до наступления due-времени. `R-KFK-RTRY-2` — retry только для transient
(timeout/5xx/брокер), не для контрактных/poison. `R-KFK-RTRY-3` — alert на размер DLQ. `R-KFK-RTRY-4` — replay из
DLQ — ручная админ-операция.

`R-KFK-RTRY-X1` — blocking retry через `setTimeout`-цикл в `eachMessage` (держит партицию). `R-KFK-RTRY-X2` —
`catch (e) { logger.error(e); }` + commit (событие потеряно). `R-KFK-RTRY-X3` — retry-топик без max-attempts
(проверка `x-attempt` обязательна). `R-KFK-RTRY-X4` — DLQ без monitoring.

## 6. Event design (`R-KFK-EVT-*`)

`R-KFK-EVT-1` — имя в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderConfirmation`). `R-KFK-EVT-2` —
payload: `eventId`, `eventType` (версионированный), `occurredAt`, `aggregateType`/`aggregateId`, бизнес-значения;
без PII в broad-топиках. `R-KFK-EVT-3` — forward-compatible: добавление полей non-breaking; удаление/переименование →
`eventType.v2`. `R-KFK-EVT-4` — событие — immutable-класс/`readonly`-интерфейс в `core/<bc>/domain/event/`;
на границе consumer — **zod-схема** для валидации payload (`orderConfirmedSchema.parse(...)`).

`R-KFK-EVT-X1` — имя-команда. `R-KFK-EVT-X2` — агрегат/Entity целиком в payload (нестабильные поля, ломает
forward-compat). `R-KFK-EVT-X3` — PII в широковещательных топиках (только `customerId`, full PII — запросом).
`R-KFK-EVT-X4` — breaking change без версии в `eventType`.

## 7. Конфигурация (`R-KFK-CFG-*`)

`R-KFK-CFG-1` — параметры через типизированный валидируемый конфиг (`KafkaConfig` + zod/class-validator,
`NESTBOOT-4`). `R-KFK-CFG-2` — клиент собирается из конфига: `new Kafka({ clientId, brokers, ssl, sasl })`,
producer/consumer-опции — из тех же настроек, не разбросаны по коду. `R-KFK-CFG-3` — десериализация — через
**статический реестр `eventType → zod-схема`** (allow-list), не «инстанцировать класс по имени из payload».
`R-KFK-CFG-4` — fail-fast на старте: `admin.fetchTopicMetadata({ topics })` в `onApplicationBootstrap`, ожидаемый
топик отсутствует → сервис не стартует.

`R-KFK-CFG-X1` — динамический `require`/lookup класса по строке из payload (аналог `trusted.packages: '*'`) —
только статический реестр схем. `R-KFK-CFG-X2` — `brokers` хардкодом без env.

## 8. Observability (`R-KFK-OBS-*`)

`R-KFK-OBS-1` — метрики через `prom-client`: kafkajs instrumentation-события (`consumer.events.END_BATCH_PROCESS`,
`producer.events.REQUEST`) → counters/histograms; consumer lag — экспортером на стороне кластера или по
`fetchOffsets` vs latest. `R-KFK-OBS-2` — **alert на consumer lag** для критичных топиков. `R-KFK-OBS-3` — tracing:
producer кладёт `traceparent` в `message.headers`, consumer извлекает и продолжает trace
(`@opentelemetry/instrumentation-kafkajs`). `R-KFK-OBS-4` — DLQ-size alert.

`R-KFK-OBS-X1` — отсутствие consumer-lag alert.

## 9. Security (`R-KFK-SEC-*`)

`R-KFK-SEC-1` — в проде TLS: `new Kafka({ ssl: true, sasl: { mechanism: 'scram-sha-512', username, password } })`,
не plaintext. `R-KFK-SEC-2` — ACL на топики per-сервис (`clientId` в `KafkaConfig`). `R-KFK-SEC-3` — PII — отдельные
restricted-топики либо «слабая ссылка» (`customerId` + запрос PII у Customer-сервиса).

`R-KFK-SEC-X1` — `PLAINTEXT` в проде. `R-KFK-SEC-X2` — один service-account на весь кластер.

## 10. Чеклист подключения к новому сервису (Node/NestJS)

1. Producer `idempotent: true` + `acks: -1`, key = aggregate id, JSON; domain-события через outbox, не прямой send.
2. Consumer: уникальный `groupId`, `autoCommit: false` + `commitOffsets` после обработки, `fromBeginning: true`,
   идемпотентен по `eventId`, `heartbeat()` в долгих обработчиках.
3. Outbox-relay (`@Interval`): QueryBuilder `setLock('pessimistic_write').setOnLocked('skip_locked')`, batch,
   partial-индекс; нет send из транзакции с DB.
4. `processed_event` PK на `event_id`, запись в одной транзакции с бизнес-результатом (`orIgnore` insert).
5. Retry-топики с `x-attempt` + DLQ + monitoring; нет `setTimeout`-retry/проглатывания в `eachMessage`.
6. Событие — прошедшее время, без агрегата/PII; версия в `eventType`; payload валидируется zod из статического реестра.
7. Fail-fast на отсутствующий топик; SSL/SASL + per-service ACL; lag/DLQ alerts; `traceparent` в headers.
