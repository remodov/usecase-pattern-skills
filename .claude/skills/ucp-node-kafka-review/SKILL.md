---
name: ucp-node-kafka-review
lang: node
description: Ревью работы с Kafka в NestJS-сервисе на kafkajs по UCP (требования kafka/*) — producer idempotence/acks/key, consumer autoCommit:false и идемпотентность, outbox-relay (SKIP LOCKED), retry-топики + DLQ, zod-реестр событий, конфиг и безопасность.
when_to_use: Ревью producer/consumer-кода на kafkajs, KafkaConfig, outbox-relay, processed_event, event-классов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Kafka (Node / NestJS / kafkajs)

Ты ревьюишь работу с Kafka на соответствие **контракту** `backend/kafka/spec.md` (`R-KFK-*`) и **Node-реализации** `backend/kafka/references/node/implementation.md` (kafkajs в обёртке-провайдере; Nest microservices Kafka-transport не даёт ручного управления offset'ами — не применяем для бизнес-consumer'ов).

## Зависимости

- **`.claude/docs/backend/kafka/spec.md`** + **`backend/kafka/references/node/implementation.md`**.
- Парные: `backend/ddd-tactical/node/...` (событие — immutable в `core/<bc>/domain/event/`), `cqrs` (outbox sync), `pg-runtime` (`FOR UPDATE SKIP LOCKED`), `resilience` (CB в consumer через cockatiel).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`kafka/manual-offset-commit`, `kafka/publish-via-outbox`), не префикс.

2. **Скоп.** Producer/consumer-код (`kafkajs`), `KafkaConfig`, outbox-relay, `processed_event`, event-классы; `git diff`.

3. **Прогон.**
   - **Producer (`R-KFK-PROD-*`):** `kafka.producer({ idempotent: true, maxInFlightRequests: 5 })` + `acks: -1` (false/0/1→`kafka/producer-is-idempotent`/`X2`); `key`=aggregate id (нет→`kafka/partition-key-required`); domain-события через outbox, не прямой `producer.send` из handler (`kafka/publish-via-outbox`).
   - **Consumer (`R-KFK-CONS-*`):** уникальный `groupId: '<service>-<purpose>'` (нет/общий→`kafka/consumer-group-per-purpose`); `consumer.run({ autoCommit: false })` + `commitOffsets` после обработки (true→`kafka/manual-offset-commit`); `fromBeginning: true`; нет `await sleep(...)` >1s без `heartbeat()` (`kafka/listener-does-not-block-poll-loop`); HTTP из `eachMessage` с CB (без→`kafka/listener-does-not-block-poll-loop`).
   - **Outbox (`R-KFK-OBX-*`):** `producer.send` из транзакции с DB → `kafka/publish-via-outbox`; публикация после commit без outbox → `kafka/publish-via-outbox`; нет `published_at`/partial-индекса → `kafka/outbox-table-shape`; relay через QueryBuilder `setLock('pessimistic_write').setOnLocked('skip_locked')`, batch 10–50.
   - **Idempotent (`R-KFK-IDEM-*`):** `processed_event` PK на `event_id`, dedup через `orIgnore` + бизнес-результат в одной `DataSource.transaction`. Нет проверки `eventId` → `kafka/consumer-is-idempotent`. Kafka offset как dedup-ключ → `kafka/consumer-is-idempotent`.
   - **Retry/DLQ (`R-KFK-RTRY-*`):** retry-топики с заголовком `x-attempt` и `consumer.pause()` до due-времени (не `setTimeout`-цикл→`kafka/retry-topics-with-limits`); проглатывание+commit→`kafka/no-swallowing-in-listener`; max-attempts (`kafka/retry-topics-with-limits`); DLQ monitoring (`kafka/dlq-monitored-and-manually-replayed`).
   - **Event (`R-KFK-EVT-*`):** прошедшее время (команда→`kafka/event-named-in-past-tense`); без агрегата целиком (`kafka/event-payload-hygiene`)/PII (`kafka/event-payload-hygiene`); версия в `eventType` (`kafka/event-schema-forward-compatible`); payload валидируется через статический реестр `eventType → zod-схема` (`orderConfirmedSchema.parse(...)`).
   - **Config (`R-KFK-CFG-*`):** десериализация через статический zod-реестр; динамический `require`/lookup класса по строке из payload → `kafka/deserialization-allow-list` (аналог `trusted.packages: '*'`); brokers через env (`kafka/settings-are-typed-and-external`); fail-fast `admin.fetchTopicMetadata` в `onApplicationBootstrap`.
   - **Security/Obs (`R-KFK-SEC/OBS-*`):** TLS/SASL в проде (plaintext→`kafka/transport-security-and-acls`); per-service ACL (`kafka/transport-security-and-acls`); consumer-lag alerts (нет→`kafka/consumer-lag-alerting`); `traceparent` в `message.headers` (`@opentelemetry/instrumentation-kafkajs`); DLQ-size alert.

4. **Cross-check:** событие как immutable readonly-интерфейс в `core/<bc>/domain/event/` — `ucp-node-ddd-tactical-review`; outbox-таблица/`SKIP LOCKED` — `ucp-pg-runtime-review`; CB (cockatiel) для HTTP из consumer — `ucp-node-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `producer.send` из транзакции с DB/без outbox (`kafka/publish-via-outbox`/`kafka/publish-via-outbox`), `autoCommit: true` (`kafka/manual-offset-commit`), нет dedup по `eventId` (`kafka/consumer-is-idempotent`), проглатывание исключения+commit (`kafka/no-swallowing-in-listener`), динамический `require` по `eventType` (`kafka/deserialization-allow-list`), plaintext в проде (`kafka/transport-security-and-acls`).
   - **Предупреждение** — `idempotent: false`/`acks: 0|1` (`kafka/producer-is-idempotent`/`X2`), send без key (`kafka/partition-key-required`), `setTimeout`-retry (`kafka/retry-topics-with-limits`), агрегат/PII в payload (`kafka/event-payload-hygiene`/`X3`), нет lag-alerts (`kafka/consumer-lag-alerting`).
   - **Замечание** — имя-команда события (`kafka/event-named-in-past-tense`), нет версии в `eventType` (`kafka/event-schema-forward-compatible`), общий service-account (`kafka/transport-security-and-acls`).

## Что не входит

- Событие как immutable класс/интерфейс — `ucp-node-ddd-tactical-review`. Outbox-таблица/locks — `ucp-pg-runtime-review`.
- CB (cockatiel) для HTTP из consumer — `ucp-node-resilience-review`. CQRS read-model sync — `ucp-node-cqrs-review`.

$ARGUMENTS
