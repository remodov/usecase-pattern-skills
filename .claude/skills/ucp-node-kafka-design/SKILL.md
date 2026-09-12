---
name: ucp-node-kafka-design
lang: node
description: Спроектировать работу с Kafka на Node/NestJS (kafkajs) по UCP — идемпотентный producer с partition key, outbox-relay через FOR UPDATE SKIP LOCKED, consumer с autoCommit:false и processed_event, retry-топики + DLQ, zod-реестр событий.
when_to_use: Триггеры — «publish событие X в Kafka», «consumer для Y», «outbox-relay на NestJS». При добавлении producer/consumer/outbox.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(pnpm*) Bash(npx*)
---

# Kafka — проектирование (Node / NestJS / kafkajs)

Ты проектируешь работу с Kafka по **контракту** `backend/kafka/spec.md` (`R-KFK-*`) и **Node-реализации** `backend/kafka/references/node/implementation.md` (kafkajs в обёртке-провайдере; Nest microservices Kafka-transport не даёт ручного управления offset'ами — не для бизнес-consumer'ов).

## Инструкции

1. **Прочитай** требования `node-style/*`. Коды в обосновании, не в коде. Связанные: `backend/ddd-tactical/node/...` (событие — immutable в `core/<bc>/domain/event/`), `cqrs` (sync read-model через outbox), `pg-runtime` (outbox-relay `FOR UPDATE SKIP LOCKED`), `resilience` (CB для HTTP из consumer), `backend/node/nest-bootstrap/spec.md` (`nest-bootstrap/config-validated-at-startup` конфиг, `nest-bootstrap/broker-and-cache-are-conditional` гейтинг consumer'ов по профилю).

2. **Producer** (`R-KFK-PROD-*`): `kafka.producer({ idempotent: true, maxInFlightRequests: 5 })` + `acks: -1`, `key`=aggregate id, JSON (`JSON.stringify(event)`); domain-события — **через outbox**, не прямой `producer.send` из handler (`kafka/publish-via-outbox`).

3. **Outbox-relay** (`R-KFK-OBX-*`): запись в `outbox` в той же `DataSource.transaction`, что бизнес-изменение; relay — отдельный `@Injectable` с `@Interval` (`@nestjs/schedule`): QueryBuilder `setLock('pessimistic_write').setOnLocked('skip_locked')`, batch 10–50, публикует, ставит `published_at`; partial-индекс `WHERE published_at IS NULL`.

4. **Consumer** (`R-KFK-CONS-*`): уникальный `groupId: '<service>-<purpose>'`, `consumer.run({ autoCommit: false })` + `commitOffsets` (offset+1) после обработки, `fromBeginning: true`, `partitionsConsumedConcurrently` ≤ числа партиций, `await heartbeat()` в долгих `eachMessage`, идемпотентен.

5. **Idempotent consumer** (`R-KFK-IDEM-*`): `eventId` (UUID v7); таблица `processed_event` (PK на `event_id`); insert `orIgnore` + бизнес-результат в одной `DataSource.transaction`; для money — `eventId` + `Idempotency-Key` на downstream HTTP.

6. **Retry + DLQ** (`R-KFK-RTRY-*`): retry-топики с возрастающим delay и заголовком `x-attempt` (не blocking-retry; retry-consumer с `consumer.pause()` до due-времени), max-attempts, DLQ + alert.

7. **Event design** (`R-KFK-EVT-*`): immutable-класс/`readonly`-интерфейс в `core/<bc>/domain/event/`, прошедшее время, `eventId`/`occurredAt`/`aggregateId`/версия в `eventType`, без агрегата/PII; на границе consumer — валидация payload через статический реестр `eventType → zod-схема`.

8. **Config/Security** (`R-KFK-CFG/SEC-*`): типизированный `KafkaConfig` (zod/class-validator, `nest-bootstrap/config-validated-at-startup`), brokers через env, fail-fast `admin.fetchTopicMetadata` в `onApplicationBootstrap`, SSL/SASL (scram), per-service ACL. **Observability**: lag/DLQ alerts, `traceparent` в `message.headers` (`@opentelemetry/instrumentation-kafkajs`).

9. **Самопроверка** (§10) + предложи `ucp-node-kafka-review`. Outbox-таблица DDL — `ucp-pg-schema-design`.

## Антипаттерны, которые НЕ генерировать

- `idempotent: false`/`acks: 0|1` (`R-KFK-PROD-X1/X2`); send без key (`kafka/partition-key-required`); `producer.send` из транзакции с DB (`kafka/publish-via-outbox`/`kafka/publish-via-outbox`).
- `autoCommit: true` — дефолт kafkajs! (`kafka/manual-offset-commit`); блокировка event loop / `sleep`>1s в `eachMessage` без `heartbeat()` (`kafka/listener-does-not-block-poll-loop`); HTTP из `eachMessage` без CB (`kafka/listener-does-not-block-poll-loop`).
- Consumer без dedup по `eventId` (`kafka/consumer-is-idempotent`); offset как dedup-ключ (`kafka/consumer-is-idempotent`); `setTimeout`-retry в `eachMessage` (`kafka/retry-topics-with-limits`); проглатывание исключения + commit (`kafka/no-swallowing-in-listener`).
- Имя-команда у события (`kafka/event-named-in-past-tense`); агрегат/PII в payload (`R-KFK-EVT-X2/X3`); breaking без версии (`kafka/event-schema-forward-compatible`); динамический `require`/lookup класса по `eventType` (`kafka/deserialization-allow-list`); `PLAINTEXT` в проде (`kafka/transport-security-and-acls`).

После работы скилла — обязательно `ucp-node-kafka-review`.

$ARGUMENTS
