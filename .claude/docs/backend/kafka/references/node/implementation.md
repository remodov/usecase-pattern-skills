# Kafka — реализация на Node (kafkajs)

Реализация язык-нейтрального контракта `../spec.md` (`R-KFK-*`) на Node/NestJS с **kafkajs**
(низкоуровневый клиент в обёртке-провайдере; Nest microservices Kafka-transport не даёт ручного управления
offset'ами — не используем для бизнес-consumer'ов). Коды общие с Java/Python; меняется клиент, семантика одна.

## 1. Producer (`R-KFK-PROD-*`)

`kafka/producer-is-idempotent` — идемпотентный producer: `kafka.producer({ idempotent: true, maxInFlightRequests: 5 })`
(требует `acks: -1` = all; kafkajs кидает ошибку при другом значении). `kafka/partition-key-required` — `key` обязателен для
бизнес-событий = **aggregate id** — ordering per-aggregate. `kafka/serialization-format` — JSON-сериализация
(`value: JSON.stringify(event)`); Avro/Protobuf + Schema Registry (`@kafkajs/confluent-schema-registry`) — для
bandwidth-топиков. `kafka/publish-via-outbox` — domain-события **не** через прямой `producer.send(...)` из handler — через **outbox**.

```ts
// PREFER
const producer = kafka.producer({ idempotent: true, maxInFlightRequests: 5 });
await producer.send({
  topic: 'orders.confirmed', acks: -1,
  messages: [{ key: String(order.id), value: JSON.stringify(event) }],
});
// AVOID: producer.send({ acks: 1, messages: [{ value: ... }] })  — без key, без репликации
```

`kafka/producer-is-idempotent` — `idempotent: false` в проде. `kafka/producer-is-idempotent` — `acks: 0`/`acks: 1`. `kafka/partition-key-required` — send без
key для бизнес-событий. `kafka/publish-via-outbox` — `producer.send` из той же транзакции (`DataSource.transaction`), что
DB-операция: Kafka не XA, rollback БД не откатит publish — outbox.

## 2. Consumer (`R-KFK-CONS-*`)

`kafka/consumer-group-per-purpose` — уникальный `groupId: '<service>-<purpose>'` per-роль. `kafka/manual-offset-commit` — **ручное управление
offset'ами**: `consumer.run({ autoCommit: false, eachMessage })`, `consumer.commitOffsets([...])` **после** успешной
обработки (offset = `message.offset + 1` — коммитится следующий к чтению). `kafka/consumer-is-idempotent` — обработчик идемпотентен
(`R-KFK-IDEM-*`). `kafka/earliest-offset-for-critical-consumers` — `subscribe({ fromBeginning: true })` для critical-consumer'ов (аналог
`auto.offset.reset: earliest`). `kafka/concurrency-and-poll-interval` — concurrency через `partitionsConsumedConcurrently` ≤ числа партиций.
`kafka/concurrency-and-poll-interval` — у kafkajs нет `max.poll.interval.ms`; аналог — `sessionTimeout`/`rebalanceTimeout` + обязательный
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

`kafka/manual-offset-commit` — `autoCommit: true` (дефолт kafkajs!) в проде — offset уходит до завершения обработки.
`kafka/listener-does-not-block-poll-loop` — блокировка event loop / `await sleep(...)` >1s в `eachMessage` без `heartbeat()` (rebalance).
`kafka/consumer-group-per-purpose` — нет `groupId`/общий на разные consumer'ы. `kafka/listener-does-not-block-poll-loop` — HTTP к внешней системе из
`eachMessage` без CB/bulkhead (`resilience/outbound-calls-fully-protected`, cockatiel — `node/implementation.md`).

## 3. Outbox publishing (`R-KFK-OBX-*`)

`kafka/publish-via-outbox` — domain-события пишутся в `outbox`-таблицу в той же `DataSource.transaction`, что бизнес-изменение,
не `producer.send` из handler. `kafka/outbox-relay-reads-in-batches` — **outbox-relay** — отдельный `@Injectable` c `@Interval`
(`@nestjs/schedule`): читает unpublished с `FOR UPDATE SKIP LOCKED` через QueryBuilder
(`R-TYPEORM-*`, `pg-runtime/skip-locked-for-queues`), публикует через kafkajs, проставляет `published_at`. `kafka/outbox-relay-reads-in-batches` — topic из
`event_type`/`aggregate_type`. `kafka/outbox-relay-reads-in-batches` — relay обрабатывает batch (10–50), не по одному.

```ts
await this.dataSource.transaction(async (manager) => {
  const events = await manager.getRepository(OutboxEventEntity).createQueryBuilder('e')
    .setLock('pessimistic_write').setOnLocked('skip_locked')
    .where('e.publishedAt IS NULL').orderBy('e.id').take(50).getMany();
  await this.producer.send({ topic, acks: -1, messages: events.map(toMessage) });
  await manager.update(OutboxEventEntity, events.map((e) => e.id), { publishedAt: new Date() });
});
```

`kafka/publish-via-outbox` — `producer.send` из транзакции с DB-операцией. `kafka/publish-via-outbox` — публикация после commit без outbox
(подписка на «after commit», падение между commit и publish теряет событие). `kafka/outbox-table-shape` — outbox без
`published_at`/partial-индекса `WHERE published_at IS NULL` (full scan).

## 4. Idempotent consumer (`R-KFK-IDEM-*`)

`kafka/consumer-is-idempotent` — у события уникальный `eventId` (UUID v7) в payload/header; consumer проверяет, обрабатывалось ли.
`kafka/processed-record-in-same-transaction` — таблица `processed_event` в PG с PK на `event_id` (UNIQUE-дедуп под race); TTL — partition-drop /
background-job. `kafka/processed-record-in-same-transaction` — запись в `processed_event` и бизнес-результат — в **одной**
`DataSource.transaction`. `kafka/money-operations-double-protected` — money: двойная защита — `eventId` + `Idempotency-Key` на downstream HTTP.

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

`kafka/consumer-is-idempotent` — consumer без проверки `eventId` там, где дубль критичен. `kafka/consumer-is-idempotent` — Kafka offset как
dedup-ключ (зависит от group; новый group → всё «впервые»).

## 5. Retry topic + DLQ (`R-KFK-RTRY-*`)

`kafka/retry-topics-with-limits` — retry-топики с возрастающим delay (`orders.confirmed.retry.1m/10m`, заголовок `x-attempt`);
у kafkajs нет аналога `@RetryableTopic` — публикация в retry-топик из catch в `eachMessage` + отдельный
retry-consumer, который `consumer.pause()` до наступления due-времени. `kafka/retry-only-transient-failures` — retry только для transient
(timeout/5xx/брокер), не для контрактных/poison. `kafka/dlq-monitored-and-manually-replayed` — alert на размер DLQ. `kafka/dlq-monitored-and-manually-replayed` — replay из
DLQ — ручная админ-операция.

`kafka/retry-topics-with-limits` — blocking retry через `setTimeout`-цикл в `eachMessage` (держит партицию). `kafka/no-swallowing-in-listener` —
`catch (e) { logger.error(e); }` + commit (событие потеряно). `kafka/retry-topics-with-limits` — retry-топик без max-attempts
(проверка `x-attempt` обязательна). `kafka/dlq-monitored-and-manually-replayed` — DLQ без monitoring.

## 6. Event design (`R-KFK-EVT-*`)

`kafka/event-named-in-past-tense` — имя в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderConfirmation`). `kafka/event-payload-hygiene` —
payload: `eventId`, `eventType` (версионированный), `occurredAt`, `aggregateType`/`aggregateId`, бизнес-значения;
без PII в broad-топиках. `kafka/event-schema-forward-compatible` — forward-compatible: добавление полей non-breaking; удаление/переименование →
`eventType.v2`. `kafka/event-payload-hygiene` — событие — immutable-класс/`readonly`-интерфейс в `core/<bc>/domain/event/`;
на границе consumer — **zod-схема** для валидации payload (`orderConfirmedSchema.parse(...)`).

`kafka/event-named-in-past-tense` — имя-команда. `kafka/event-payload-hygiene` — агрегат/Entity целиком в payload (нестабильные поля, ломает
forward-compat). `kafka/event-payload-hygiene` — PII в широковещательных топиках (только `customerId`, full PII — запросом).
`kafka/event-schema-forward-compatible` — breaking change без версии в `eventType`.

## 7. Конфигурация (`R-KFK-CFG-*`)

`kafka/settings-are-typed-and-external` — параметры через типизированный валидируемый конфиг (`KafkaConfig` + zod/class-validator,
`nest-bootstrap/config-validated-at-startup`). `kafka/settings-are-typed-and-external` — клиент собирается из конфига: `new Kafka({ clientId, brokers, ssl, sasl })`,
producer/consumer-опции — из тех же настроек, не разбросаны по коду. `kafka/deserialization-allow-list` — десериализация — через
**статический реестр `eventType → zod-схема`** (allow-list), не «инстанцировать класс по имени из payload».
`kafka/missing-topics-are-fatal` — fail-fast на старте: `admin.fetchTopicMetadata({ topics })` в `onApplicationBootstrap`, ожидаемый
топик отсутствует → сервис не стартует.

`kafka/deserialization-allow-list` — динамический `require`/lookup класса по строке из payload (аналог `trusted.packages: '*'`) —
только статический реестр схем. `kafka/settings-are-typed-and-external` — `brokers` хардкодом без env.

## 8. Observability (`R-KFK-OBS-*`)

`kafka/consumer-lag-alerting` — метрики через `prom-client`: kafkajs instrumentation-события (`consumer.events.END_BATCH_PROCESS`,
`producer.events.REQUEST`) → counters/histograms; consumer lag — экспортером на стороне кластера или по
`fetchOffsets` vs latest. `kafka/consumer-lag-alerting` — **alert на consumer lag** для критичных топиков. `kafka/trace-context-in-headers` — tracing:
producer кладёт `traceparent` в `message.headers`, consumer извлекает и продолжает trace
(`@opentelemetry/instrumentation-kafkajs`). `kafka/dlq-monitored-and-manually-replayed` — DLQ-size alert.

`kafka/consumer-lag-alerting` — отсутствие consumer-lag alert.

## 9. Security (`R-KFK-SEC-*`)

`kafka/transport-security-and-acls` — в проде TLS: `new Kafka({ ssl: true, sasl: { mechanism: 'scram-sha-512', username, password } })`,
не plaintext. `kafka/transport-security-and-acls` — ACL на топики per-сервис (`clientId` в `KafkaConfig`). `kafka/event-payload-hygiene` — PII — отдельные
restricted-топики либо «слабая ссылка» (`customerId` + запрос PII у Customer-сервиса).

`kafka/transport-security-and-acls` — `PLAINTEXT` в проде. `kafka/transport-security-and-acls` — один service-account на весь кластер.

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
