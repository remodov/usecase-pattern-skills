---
name: ucp-kafka-review
description: Ревью работы с Kafka в Java/Spring (требования kafka/*) — idempotent producer и partition key, ack после записи и dedup, outbox вместо @TransactionalEventListener, retry и DLQ (топик или таблица), event design, config.
when_to_use: Изменения в KafkaListener-классах, KafkaConfig, kafka-блоке application.yml, outbox-relay.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Kafka

Ты ревьюишь работу с Kafka в Java/Spring-сервисе на соответствие требованиям `kafka/*`. Главные точки контроля: producer-идемпотентность и outbox publishing, ack только после обработки записи и idempotent dedup, повторы инфраструктурой (retry-топики или `DefaultErrorHandler`) вместо blocking retry в коде listener'а, event design.

## Зависимости

- **`.claude/docs/backend/kafka/spec.md`** — индекс всех правил (полный текст с примерами — `references/<lang>/implementation.md`). Подгруппы: `R-KFK-PROD-*` (producer), `R-KFK-CONS-*` (consumer), `R-KFK-OBX-*` (outbox), `R-KFK-IDEM-*` (idempotency), `R-KFK-RTRY-*` (retry+DLQ), `R-KFK-EVT-*` (event design), `R-KFK-CFG-*` (config), `R-KFK-OBS-*` (observability), `R-KFK-SEC-*` (security).
- Парные документы: `backend/pg-runtime/spec.md` (`pg-runtime/skip-locked-for-queues` — outbox-relay через SKIP LOCKED), `backend/auth-patterns/spec.md` (`auth-patterns/money-commands-need-idempotency-key` — money-операции через Idempotency-Key), `backend/resilience/spec.md` (CB вокруг HTTP-вызовов из listener), `backend/ddd-tactical/spec.md` (`R-EVT-*` — domain events как payload).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/kafka/spec.md`. Цитируй конкретные коды (`kafka/producer-is-idempotent`, `kafka/publish-via-outbox`).

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на `*KafkaListener*`, `*KafkaConfig*`, `*KafkaTemplate*`, `*OutboxRelay*`, `*OutboxPublisher*`.
   - `application*.yml` с блоком `spring.kafka:` или `kafka:`.
   - Файлы с импортами `org.apache.kafka.*`, `org.springframework.kafka.*`.
   - DDL changeset с `outbox_event` или `processed_event` таблицами.

3. **Прогон по подгруппам:**
   - **`R-KFK-PROD-*`** — `enable.idempotence: true`, `acks: all`, partition key явный (aggregate id), `KafkaTemplate.send` НЕ из `@Transactional` с DB-операцией.
   - **`R-KFK-CONS-*`** — `group.id` уникальный per-purpose, ack только после записи (`RECORD` или `MANUAL_IMMEDIATE`, `enable-auto-commit: false`), `auto-offset-reset: earliest` для critical, справочники из шины — с наливом через API источника (`kafka/reference-data-backfilled-via-api`), listener idempotent, нет `Thread.sleep`/blocking, HTTP-вызовы обёрнуты в CB.
   - **`R-KFK-OBX-*`** — domain events через outbox-relay; `outbox_event` таблица с partial-индексом `WHERE published_at IS NULL`; нет `@TransactionalEventListener` для отправки в Kafka напрямую; `published_at` ставится только после ack брокера (`R-KFK-OBX-5`).
   - **`R-KFK-IDEM-*`** — `eventId` UUID v7 в payload; `processed_event` таблица с PK на `event_id`; mark-processed в той же транзакции что и бизнес-результат; для money — двойная защита (eventId + Idempotency-Key); поток снимков состояния со stale-guard по `updatedAt` — допустимо только как задокументированное отступление.
   - **`R-KFK-RTRY-*`** — `@RetryableTopic` с явным max-attempts либо `DefaultErrorHandler` с ограниченным backoff (суммарно ≪ `max.poll.interval`) и `addNotRetryableExceptions`; retry только на transient-errors (5xx, IOException), не на 4xx и runtime-баги; DLQ — топик или таблица `kafka_errors` с метрикой, alert и retention; replay из DLQ — manual; `Thread.sleep`/`@Retryable` в коде listener'а — критично.
   - **`R-KFK-EVT-*`** — имя событий в past tense (`OrderConfirmed`, не `ConfirmOrder`); record с `eventId`/`eventType` версионированный/`occurredAt`/`aggregateType`/`aggregateId`; нет PII в широковещательных топиках; нет Aggregate-объектов целиком в payload.
   - **`R-KFK-CFG-*`** — `@ConfigurationProperties` + `@Validated` для KafkaSettings; десериализация в явный тип — `spring.json.trusted.packages` явный allow-list (не `'*'`) либо `StringDeserializer` + `readValue` в конкретный тип; `allow.auto.create.topics: false`, свои топики через `KafkaAdmin.NewTopics`; `missing-topics-fatal: true` в проде; `bootstrap-servers` через env-substitution.
   - **`R-KFK-OBS-*`** — Spring Kafka Micrometer-metrics включены; alert на `kafka_consumer_lag` для критичных топиков; OTel `traceparent` пропагирует через Kafka headers; DLQ-size alert.
   - **`R-KFK-SEC-*`** — TLS/SASL для прод-кластера; ACL'ы per-сервис; PII через restricted-topic или по `customerId`.

4. **Ищи паттерны-нарушения:**
   - `kafkaTemplate.send(...)` в `@Transactional`-методе с `repository.save(...)` рядом — `kafka/publish-via-outbox` / `kafka/publish-via-outbox`.
   - `enable.idempotence: false` или отсутствие в producer-config — `kafka/producer-is-idempotent`.
   - `acks: 0` / `acks: 1` — `kafka/producer-is-idempotent`.
   - `kafkaTemplate.send(topic, value)` без key (двух-аргументный send) для бизнес-событий — `kafka/partition-key-required`.
   - `enable.auto.commit: true` или дефолтное значение — `kafka/manual-offset-commit`.
   - `Thread.sleep` в `@KafkaListener`-методе — `kafka/listener-does-not-block-poll-loop` / `kafka/retry-topics-with-limits`.
   - `@KafkaListener` без `groupId` или с одинаковым `groupId` для разных listener-методов — `kafka/consumer-group-per-purpose`.
   - Listener делает `restTemplate.exchange(...)` или `restClient.get(...)` без `@CircuitBreaker` — `kafka/listener-does-not-block-poll-loop`.
   - Listener без проверки `eventId` через `processed_event` или подобное — `kafka/consumer-is-idempotent`.
   - `@TransactionalEventListener(phase = AFTER_COMMIT)` с `kafkaTemplate.send` внутри — `kafka/publish-via-outbox`.
   - `outbox_event` таблица без `WHERE published_at IS NULL` partial-индекса — `kafka/outbox-table-shape`.
   - `try { ... } catch (Exception e) { log.error(...); ack.acknowledge(); }` без отправки в DLQ — `kafka/no-swallowing-in-listener`.
   - `@RetryableTopic` без `attempts` или с `attempts = "Integer.MAX_VALUE"` — `kafka/retry-topics-with-limits`.
   - Имя события в коде: `ConfirmOrderEvent`, `CreateUserCommand` — `kafka/event-named-in-past-tense`.
   - Payload event-record содержит `Order order` или другой Aggregate целиком — `kafka/event-payload-hygiene`.
   - `email` / `phone` / `passport` в payload event'а топика типа `customer.profile.updated` — `kafka/event-payload-hygiene`.
   - `spring.json.trusted.packages: '*'` — `kafka/deserialization-allow-list`.
   - `bootstrap-servers: localhost:9092` (hardcoded) — `kafka/settings-are-typed-and-external`.
   - `security.protocol: PLAINTEXT` в `application-prod.yml` — `kafka/transport-security-and-acls`.

5. **При ревью `application.yml`:**
   - `spring.kafka.producer.properties.enable.idempotence: true`.
   - `spring.kafka.producer.acks: all`.
   - `spring.kafka.consumer.enable-auto-commit: false`.
   - `spring.kafka.consumer.auto-offset-reset: earliest` (для critical).
   - `spring.kafka.listener.ack-mode: MANUAL_IMMEDIATE` или `MANUAL`.
   - `spring.kafka.listener.missing-topics-fatal: true`.
   - `spring.kafka.consumer.properties.spring.json.trusted.packages: 'ru.example.events.*'` (explicit, не `*`).
   - `spring.kafka.bootstrap-servers: ${KAFKA_BROKERS:...}` — env-substitution.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`).

7. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично:**
     - `KafkaTemplate.send` в одной транзакции с DB-операцией — потеря consistency (R-KFK-OBX-X1).
     - `enable.idempotence: false` — дубликаты в проде.
     - `enable.auto.commit: true` — потеря данных при крэше.
     - Listener без `eventId`-dedup для critical-consumer — двойная обработка.
     - `Thread.sleep` в listener — блокировка poll-цикла, rebalance.
     - `spring.json.trusted.packages: '*'` — security CVE.
     - Listener делает HTTP без CB — каскадный отказ при slow downstream.
   - **Предупреждение:**
     - Send без partition key — потеря ordering для агрегата.
     - `group.id` отсутствует или общий.
     - Catch + log + ack без DLQ — silent drop.
     - Aggregate целиком в payload — fragile schema.
     - PII в payload без restricted-topic.
   - **Замечание:**
     - Имя события не в past tense.
     - `bootstrap-servers` hardcoded.
     - Отсутствие consumer-lag alerts.

## Что не входит

- Kafka Streams (`R-KFK-STREAM-*` — отдельная тема, в этом скилле не покрывается).
- Schema Registry / Avro — упоминается, но не main focus.
- Kafka cluster admin (broker config, replication) — это инфра/SRE.
- Outbox-relay реализация целиком (DDL + Java) — генерация в `ucp-pg-runtime-design`.
- Resilience-обвязка адаптеров — `ucp-resilience-review`.
- Domain events как класс — `ucp-ddd-tactical-review` (`R-EVT-*`).
- Транзакционные границы handler — `ucp-pattern-review`.

$ARGUMENTS
