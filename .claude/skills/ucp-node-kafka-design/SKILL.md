---
name: ucp-node-kafka-design
lang: node
description: Спроектировать работу с Kafka на Node/NestJS (kafkajs) по UCP (коды R-KFK-*) — идемпотентный producer с partition key, outbox-relay через FOR UPDATE SKIP LOCKED, consumer с autoCommit:false и processed_event, retry-топики + DLQ, zod-реестр событий.
when_to_use: Триггеры — «publish событие X в Kafka», «consumer для Y», «outbox-relay на NestJS». При добавлении producer/consumer/outbox.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(pnpm*) Bash(npx*)
---

# Kafka — проектирование (Node / NestJS / kafkajs)

Ты проектируешь работу с Kafka по **контракту** `backend/kafka/kafka-rules.md` (`R-KFK-*`) и **Node-реализации** `backend/kafka/node/kafka-style-guide.md` (kafkajs в обёртке-провайдере; Nest microservices Kafka-transport не даёт ручного управления offset'ами — не для бизнес-consumer'ов).

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `backend/ddd-tactical/node/...` (событие — immutable в `core/<bc>/domain/event/`), `cqrs` (sync read-model через outbox), `pg-runtime` (outbox-relay `FOR UPDATE SKIP LOCKED`), `resilience` (CB для HTTP из consumer), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-4` конфиг, `NESTBOOT-11` гейтинг consumer'ов по профилю).

2. **Producer** (`R-KFK-PROD-*`): `kafka.producer({ idempotent: true, maxInFlightRequests: 5 })` + `acks: -1`, `key`=aggregate id, JSON (`JSON.stringify(event)`); domain-события — **через outbox**, не прямой `producer.send` из handler (`R-KFK-PROD-X4`).

3. **Outbox-relay** (`R-KFK-OBX-*`): запись в `outbox` в той же `DataSource.transaction`, что бизнес-изменение; relay — отдельный `@Injectable` с `@Interval` (`@nestjs/schedule`): QueryBuilder `setLock('pessimistic_write').setOnLocked('skip_locked')`, batch 10–50, публикует, ставит `published_at`; partial-индекс `WHERE published_at IS NULL`.

4. **Consumer** (`R-KFK-CONS-*`): уникальный `groupId: '<service>-<purpose>'`, `consumer.run({ autoCommit: false })` + `commitOffsets` (offset+1) после обработки, `fromBeginning: true`, `partitionsConsumedConcurrently` ≤ числа партиций, `await heartbeat()` в долгих `eachMessage`, идемпотентен.

5. **Idempotent consumer** (`R-KFK-IDEM-*`): `eventId` (UUID v7); таблица `processed_event` (PK на `event_id`); insert `orIgnore` + бизнес-результат в одной `DataSource.transaction`; для money — `eventId` + `Idempotency-Key` на downstream HTTP.

6. **Retry + DLQ** (`R-KFK-RTRY-*`): retry-топики с возрастающим delay и заголовком `x-attempt` (не blocking-retry; retry-consumer с `consumer.pause()` до due-времени), max-attempts, DLQ + alert.

7. **Event design** (`R-KFK-EVT-*`): immutable-класс/`readonly`-интерфейс в `core/<bc>/domain/event/`, прошедшее время, `eventId`/`occurredAt`/`aggregateId`/версия в `eventType`, без агрегата/PII; на границе consumer — валидация payload через статический реестр `eventType → zod-схема`.

8. **Config/Security** (`R-KFK-CFG/SEC-*`): типизированный `KafkaConfig` (zod/class-validator, `NESTBOOT-4`), brokers через env, fail-fast `admin.fetchTopicMetadata` в `onApplicationBootstrap`, SSL/SASL (scram), per-service ACL. **Observability**: lag/DLQ alerts, `traceparent` в `message.headers` (`@opentelemetry/instrumentation-kafkajs`).

9. **Самопроверка** (§10) + предложи `ucp-node-kafka-review`. Outbox-таблица DDL — `ucp-pg-schema-design`.

## Антипаттерны, которые НЕ генерировать

- `idempotent: false`/`acks: 0|1` (`R-KFK-PROD-X1/X2`); send без key (`R-KFK-PROD-X3`); `producer.send` из транзакции с DB (`R-KFK-PROD-X4`/`R-KFK-OBX-X1`).
- `autoCommit: true` — дефолт kafkajs! (`R-KFK-CONS-X1`); блокировка event loop / `sleep`>1s в `eachMessage` без `heartbeat()` (`R-KFK-CONS-X2`); HTTP из `eachMessage` без CB (`R-KFK-CONS-X4`).
- Consumer без dedup по `eventId` (`R-KFK-IDEM-X1`); offset как dedup-ключ (`R-KFK-IDEM-X2`); `setTimeout`-retry в `eachMessage` (`R-KFK-RTRY-X1`); проглатывание исключения + commit (`R-KFK-RTRY-X2`).
- Имя-команда у события (`R-KFK-EVT-X1`); агрегат/PII в payload (`R-KFK-EVT-X2/X3`); breaking без версии (`R-KFK-EVT-X4`); динамический `require`/lookup класса по `eventType` (`R-KFK-CFG-X1`); `PLAINTEXT` в проде (`R-KFK-SEC-X1`).

После работы скилла — обязательно `ucp-node-kafka-review`.

$ARGUMENTS
