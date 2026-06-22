---
name: ucp-node-kafka-review
lang: node
description: Ревью работы с Kafka в NestJS-сервисе на kafkajs по UCP (коды R-KFK-*) — producer idempotence/acks/key, consumer autoCommit:false и идемпотентность, outbox-relay (SKIP LOCKED), retry-топики + DLQ, zod-реестр событий, конфиг и безопасность.
when_to_use: Ревью producer/consumer-кода на kafkajs, KafkaConfig, outbox-relay, processed_event, event-классов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Kafka (Node / NestJS / kafkajs)

Ты ревьюишь работу с Kafka на соответствие **контракту** `backend/kafka/kafka-rules.md` (`R-KFK-*`) и **Node-реализации** `backend/kafka/node/kafka-style-guide.md` (kafkajs в обёртке-провайдере; Nest microservices Kafka-transport не даёт ручного управления offset'ами — не применяем для бизнес-consumer'ов).

## Зависимости

- **`.claude/docs/backend/kafka/kafka-rules.md`** + **`backend/kafka/node/kafka-style-guide.md`**.
- Парные: `backend/ddd-tactical/node/...` (событие — immutable в `core/<bc>/domain/event/`), `cqrs` (outbox sync), `pg-runtime` (`FOR UPDATE SKIP LOCKED`), `resilience` (CB в consumer через cockatiel).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-KFK-CONS-X1`, `R-KFK-OBX-X1`), не префикс.

2. **Скоп.** Producer/consumer-код (`kafkajs`), `KafkaConfig`, outbox-relay, `processed_event`, event-классы; `git diff`.

3. **Прогон.**
   - **Producer (`R-KFK-PROD-*`):** `kafka.producer({ idempotent: true, maxInFlightRequests: 5 })` + `acks: -1` (false/0/1→`R-KFK-PROD-X1`/`X2`); `key`=aggregate id (нет→`R-KFK-PROD-X3`); domain-события через outbox, не прямой `producer.send` из handler (`R-KFK-PROD-X4`).
   - **Consumer (`R-KFK-CONS-*`):** уникальный `groupId: '<service>-<purpose>'` (нет/общий→`R-KFK-CONS-X3`); `consumer.run({ autoCommit: false })` + `commitOffsets` после обработки (true→`R-KFK-CONS-X1`); `fromBeginning: true`; нет `await sleep(...)` >1s без `heartbeat()` (`R-KFK-CONS-X2`); HTTP из `eachMessage` с CB (без→`R-KFK-CONS-X4`).
   - **Outbox (`R-KFK-OBX-*`):** `producer.send` из транзакции с DB → `R-KFK-OBX-X1`; публикация после commit без outbox → `R-KFK-OBX-X2`; нет `published_at`/partial-индекса → `R-KFK-OBX-X3`; relay через QueryBuilder `setLock('pessimistic_write').setOnLocked('skip_locked')`, batch 10–50.
   - **Idempotent (`R-KFK-IDEM-*`):** `processed_event` PK на `event_id`, dedup через `orIgnore` + бизнес-результат в одной `DataSource.transaction`. Нет проверки `eventId` → `R-KFK-IDEM-X1`. Kafka offset как dedup-ключ → `R-KFK-IDEM-X2`.
   - **Retry/DLQ (`R-KFK-RTRY-*`):** retry-топики с заголовком `x-attempt` и `consumer.pause()` до due-времени (не `setTimeout`-цикл→`R-KFK-RTRY-X1`); проглатывание+commit→`R-KFK-RTRY-X2`; max-attempts (`R-KFK-RTRY-X3`); DLQ monitoring (`R-KFK-RTRY-X4`).
   - **Event (`R-KFK-EVT-*`):** прошедшее время (команда→`R-KFK-EVT-X1`); без агрегата целиком (`R-KFK-EVT-X2`)/PII (`R-KFK-EVT-X3`); версия в `eventType` (`R-KFK-EVT-X4`); payload валидируется через статический реестр `eventType → zod-схема` (`orderConfirmedSchema.parse(...)`).
   - **Config (`R-KFK-CFG-*`):** десериализация через статический zod-реестр; динамический `require`/lookup класса по строке из payload → `R-KFK-CFG-X1` (аналог `trusted.packages: '*'`); brokers через env (`R-KFK-CFG-X2`); fail-fast `admin.fetchTopicMetadata` в `onApplicationBootstrap`.
   - **Security/Obs (`R-KFK-SEC/OBS-*`):** TLS/SASL в проде (plaintext→`R-KFK-SEC-X1`); per-service ACL (`R-KFK-SEC-X2`); consumer-lag alerts (нет→`R-KFK-OBS-X1`); `traceparent` в `message.headers` (`@opentelemetry/instrumentation-kafkajs`); DLQ-size alert.

4. **Cross-check:** событие как immutable readonly-интерфейс в `core/<bc>/domain/event/` — `ucp-node-ddd-tactical-review`; outbox-таблица/`SKIP LOCKED` — `ucp-pg-runtime-review`; CB (cockatiel) для HTTP из consumer — `ucp-node-resilience-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `producer.send` из транзакции с DB/без outbox (`R-KFK-OBX-X1`/`R-KFK-PROD-X4`), `autoCommit: true` (`R-KFK-CONS-X1`), нет dedup по `eventId` (`R-KFK-IDEM-X1`), проглатывание исключения+commit (`R-KFK-RTRY-X2`), динамический `require` по `eventType` (`R-KFK-CFG-X1`), plaintext в проде (`R-KFK-SEC-X1`).
   - **Предупреждение** — `idempotent: false`/`acks: 0|1` (`R-KFK-PROD-X1`/`X2`), send без key (`R-KFK-PROD-X3`), `setTimeout`-retry (`R-KFK-RTRY-X1`), агрегат/PII в payload (`R-KFK-EVT-X2`/`X3`), нет lag-alerts (`R-KFK-OBS-X1`).
   - **Замечание** — имя-команда события (`R-KFK-EVT-X1`), нет версии в `eventType` (`R-KFK-EVT-X4`), общий service-account (`R-KFK-SEC-X2`).

## Что не входит

- Событие как immutable класс/интерфейс — `ucp-node-ddd-tactical-review`. Outbox-таблица/locks — `ucp-pg-runtime-review`.
- CB (cockatiel) для HTTP из consumer — `ucp-node-resilience-review`. CQRS read-model sync — `ucp-node-cqrs-review`.

$ARGUMENTS
