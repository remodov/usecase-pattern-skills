---
name: ucp-kafka-review
description: Ревью работы с Kafka — producer (idempotence, acks=all, partition key), consumer (manual ack, group.id per-purpose, idempotent с processed_event таблицей), outbox publishing вместо @TransactionalEventListener, retry topic + DLQ вместо blocking retry, event design (имя в past tense, eventId UUID v7, eventType версионированный), конфигурация (trusted.packages explicit allow-list, missing-topics-fatal), security (TLS, ACLs per-сервис), observability (consumer lag alerts). Проверяет KafkaTemplate.send из @Transactional с DB, enable.auto.commit, отсутствие partition key, listener без CB на HTTP, blocking retry через Thread.sleep, отсутствие eventId dedup, PII в широковещательных топиках. Применяется при ревью KafkaListener-классов, KafkaConfig, application.yml kafka-блока, outbox-relay реализаций. Опирается на коды R-KFK-*.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Kafka

Ты ревьюишь работу с Kafka в Java/Spring-сервисе на соответствие Kafka Style Guide. Главные точки контроля: producer-идемпотентность и outbox publishing, consumer manual-ack и idempotent dedup, retry topic вместо blocking retry, event design.

## Зависимости

- **`.claude/docs/kafka-style-guide.md`** — единственный источник правил. Подгруппы: `R-KFK-PROD-*` (producer), `R-KFK-CONS-*` (consumer), `R-KFK-OBX-*` (outbox), `R-KFK-IDEM-*` (idempotency), `R-KFK-RTRY-*` (retry+DLQ), `R-KFK-EVT-*` (event design), `R-KFK-CFG-*` (config), `R-KFK-OBS-*` (observability), `R-KFK-SEC-*` (security).
- Парные документы: `pg-runtime-style-guide.md` (`PG-L-021` — outbox-relay через SKIP LOCKED), `auth-patterns-style-guide.md` (`AUTH-19` — money-операции через Idempotency-Key), `resilience-style-guide.md` (CB вокруг HTTP-вызовов из listener), `ddd-tactical-style-guide.md` (`R-EVT-*` — domain events как payload).

## Инструкции

1. **Прочти style guide** из `.claude/docs/kafka-style-guide.md`. Цитируй конкретные коды (`R-KFK-PROD-X1`, `R-KFK-OBX-X1`).

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на `*KafkaListener*`, `*KafkaConfig*`, `*KafkaTemplate*`, `*OutboxRelay*`, `*OutboxPublisher*`.
   - `application*.yml` с блоком `spring.kafka:` или `kafka:`.
   - Файлы с импортами `org.apache.kafka.*`, `org.springframework.kafka.*`.
   - DDL changeset с `outbox_event` или `processed_event` таблицами.

3. **Прогон по подгруппам:**
   - **`R-KFK-PROD-*`** — `enable.idempotence: true`, `acks: all`, partition key явный (aggregate id), `KafkaTemplate.send` НЕ из `@Transactional` с DB-операцией.
   - **`R-KFK-CONS-*`** — `group.id` уникальный per-purpose, manual ack (`MANUAL_IMMEDIATE`), `auto-offset-reset: earliest` для critical, listener idempotent, нет `Thread.sleep`/blocking, HTTP-вызовы обёрнуты в CB.
   - **`R-KFK-OBX-*`** — domain events через outbox-relay; `outbox_event` таблица с partial-индексом `WHERE published_at IS NULL`; нет `@TransactionalEventListener` для отправки в Kafka напрямую.
   - **`R-KFK-IDEM-*`** — `eventId` UUID v7 в payload; `processed_event` таблица с PK на `event_id`; mark-processed в той же транзакции что и бизнес-результат; для money — двойная защита (eventId + Idempotency-Key).
   - **`R-KFK-RTRY-*`** — `@RetryableTopic` с явным max-attempts; retry только на transient-errors (5xx, IOException), не на 4xx и runtime-баги; DLQ-monitoring и alert на размер; replay из DLQ — manual.
   - **`R-KFK-EVT-*`** — имя событий в past tense (`OrderConfirmed`, не `ConfirmOrder`); record с `eventId`/`eventType` версионированный/`occurredAt`/`aggregateType`/`aggregateId`; нет PII в широковещательных топиках; нет Aggregate-объектов целиком в payload.
   - **`R-KFK-CFG-*`** — `@ConfigurationProperties` + `@Validated` для KafkaSettings; `spring.json.trusted.packages` явный allow-list (не `'*'`); `missing-topics-fatal: true` в проде; `bootstrap-servers` через env-substitution.
   - **`R-KFK-OBS-*`** — Spring Kafka Micrometer-metrics включены; alert на `kafka_consumer_lag` для критичных топиков; OTel `traceparent` пропагирует через Kafka headers; DLQ-size alert.
   - **`R-KFK-SEC-*`** — TLS/SASL для прод-кластера; ACL'ы per-сервис; PII через restricted-topic или по `customerId`.

4. **Ищи паттерны-нарушения:**
   - `kafkaTemplate.send(...)` в `@Transactional`-методе с `repository.save(...)` рядом — `R-KFK-PROD-X4` / `R-KFK-OBX-X1`.
   - `enable.idempotence: false` или отсутствие в producer-config — `R-KFK-PROD-X1`.
   - `acks: 0` / `acks: 1` — `R-KFK-PROD-X2`.
   - `kafkaTemplate.send(topic, value)` без key (двух-аргументный send) для бизнес-событий — `R-KFK-PROD-X3`.
   - `enable.auto.commit: true` или дефолтное значение — `R-KFK-CONS-X1`.
   - `Thread.sleep` в `@KafkaListener`-методе — `R-KFK-CONS-X2` / `R-KFK-RTRY-X1`.
   - `@KafkaListener` без `groupId` или с одинаковым `groupId` для разных listener-методов — `R-KFK-CONS-X3`.
   - Listener делает `restTemplate.exchange(...)` или `restClient.get(...)` без `@CircuitBreaker` — `R-KFK-CONS-X4`.
   - Listener без проверки `eventId` через `processed_event` или подобное — `R-KFK-IDEM-X1`.
   - `@TransactionalEventListener(phase = AFTER_COMMIT)` с `kafkaTemplate.send` внутри — `R-KFK-OBX-X2`.
   - `outbox_event` таблица без `WHERE published_at IS NULL` partial-индекса — `R-KFK-OBX-X3`.
   - `try { ... } catch (Exception e) { log.error(...); ack.acknowledge(); }` без отправки в DLQ — `R-KFK-RTRY-X2`.
   - `@RetryableTopic` без `attempts` или с `attempts = "Integer.MAX_VALUE"` — `R-KFK-RTRY-X3`.
   - Имя события в коде: `ConfirmOrderEvent`, `CreateUserCommand` — `R-KFK-EVT-X1`.
   - Payload event-record содержит `Order order` или другой Aggregate целиком — `R-KFK-EVT-X2`.
   - `email` / `phone` / `passport` в payload event'а топика типа `customer.profile.updated` — `R-KFK-EVT-X3`.
   - `spring.json.trusted.packages: '*'` — `R-KFK-CFG-X1`.
   - `bootstrap-servers: localhost:9092` (hardcoded) — `R-KFK-CFG-X2`.
   - `security.protocol: PLAINTEXT` в `application-prod.yml` — `R-KFK-SEC-X1`.

5. **При ревью `application.yml`:**
   - `spring.kafka.producer.properties.enable.idempotence: true`.
   - `spring.kafka.producer.acks: all`.
   - `spring.kafka.consumer.enable-auto-commit: false`.
   - `spring.kafka.consumer.auto-offset-reset: earliest` (для critical).
   - `spring.kafka.listener.ack-mode: MANUAL_IMMEDIATE` или `MANUAL`.
   - `spring.kafka.listener.missing-topics-fatal: true`.
   - `spring.kafka.consumer.properties.spring.json.trusted.packages: 'ru.example.events.*'` (explicit, не `*`).
   - `spring.kafka.bootstrap-servers: ${KAFKA_BROKERS:...}` — env-substitution.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-*`).

7. **Доменные ориентиры серьёзности** (`RFF-12`):
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
