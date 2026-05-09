# Kafka Style Guide

Свод правил работы с Kafka в Java/Spring-сервисах команды UCP: producer (idempotence, partition key), consumer (groups, offset, listener), outbox-relay для надёжной публикации, idempotent consumer с dedup, retry topic + DLQ вместо blocking retry, event design, observability lag. Каждое правило идентифицируется кодом (`R-KFK-PROD-1`, `R-KFK-CONS-X1`) — скилл `ucp-kafka-review` цитирует эти коды в findings.

Гайд опирается на [Apache Kafka 3.x](https://kafka.apache.org/) + [spring-kafka](https://docs.spring.io/spring-kafka/reference/) (Spring Boot 3+). Не покрывает: Kafka cluster admin (broker config, replication, MirrorMaker — это инфра-уровень), Kafka Streams (`R-KFK-STREAM-*` — отдельная тема), ksqlDB.

Связанные стандарты:
- `PG-L-020`/`PG-L-021` (PG runtime) — outbox-relay через `FOR UPDATE SKIP LOCKED`.
- `R-RES-*` (Resilience) — Kafka producer/consumer тоже outbound, имеют свои timeout/retry стратегии.
- `R-ENT-*`/`R-AGG-*`/`R-EVT-*` (DDD tactical) — Domain Events как payload Kafka-сообщений.
- `AUTH-19` (Auth) — money-операции через Kafka требуют идемпотентности.
- `R-VLD-CFG-*` (Validation) — KafkaSettings обязательно `@Validated`.

---

## Содержание

1. [Producer — `R-KFK-PROD-*`](#1-producer)
2. [Consumer — `R-KFK-CONS-*`](#2-consumer)
3. [Outbox publishing — `R-KFK-OBX-*`](#3-outbox-publishing)
4. [Idempotent consumer — `R-KFK-IDEM-*`](#4-idempotent-consumer)
5. [Retry topic + DLQ — `R-KFK-RTRY-*`](#5-retry-topic--dlq)
6. [Event design — `R-KFK-EVT-*`](#6-event-design)
7. [Конфигурация — `R-KFK-CFG-*`](#7-конфигурация)
8. [Observability — `R-KFK-OBS-*`](#8-observability)
9. [Security — `R-KFK-SEC-*`](#9-security)
10. [Антипаттерны — сводка `R-KFK-*-X*`](#10-антипаттерны)

---

## 1. Producer

### 1.1 Обязательно

- **R-KFK-PROD-1.** Producer **всегда** идемпотентный: `enable.idempotence: true`. Это автоматически: `acks=all`, `retries=Integer.MAX_VALUE`, `max.in.flight.requests.per.connection ≤ 5`. Гарантирует exactly-once на уровне partition (по producer-id).
  ```yaml
  spring.kafka.producer:
    properties:
      enable.idempotence: true
    acks: all
  ```

- **R-KFK-PROD-2.** **Partition key** — обязателен для всех бизнес-событий. Без ключа сообщения распределяются round-robin → теряется ordering для одного aggregate. Дефолтный ключ — **aggregate id**:
  ```java
  kafkaTemplate.send("orders.confirmed", order.getId().toString(), event);
  ```
  Это гарантирует что все события одного `order.id` приходят на один partition в правильном порядке.

- **R-KFK-PROD-3.** Сериализация — **JSON** (`JsonSerializer`) по умолчанию. Для bandwidth-чувствительных топиков — Avro/Protobuf через Schema Registry (но это отдельная инфра, по умолчанию не настраивается).

- **R-KFK-PROD-4.** **Не используй `KafkaTemplate.send(...)` напрямую из use-case handler-а** для domain-событий. События идут через **outbox pattern** (`R-KFK-OBX-*`) — иначе при rollback транзакции события уже отправлены, появляются «несуществующие» события.

  Допустимо прямой `kafkaTemplate.send(...)` только для:
  - Технических событий (audit-log в дополнение к `*_audit_log` таблице).
  - Метрик / health-сигналов.
  - Команд другим сервисам, **не имеющих транзакционного контекста** (например запрос на отчёт от admin-инструмента).

### 1.2 Запрещено

- **R-KFK-PROD-X1.** **`enable.idempotence: false`** в проде. Без идемпотентности retry на стороне producer создаёт дубликаты.

- **R-KFK-PROD-X2.** **`acks: 0`** или **`acks: 1`**. `0` = fire-and-forget (потеря данных при broker rebalance); `1` = ack от leader без репликации (потеря при failure leader до replication). Только `acks: all`.

- **R-KFK-PROD-X3.** **Send без partition key** для бизнес-событий. Round-robin = потеря порядка для aggregate.

- **R-KFK-PROD-X4.** **`KafkaTemplate.send(...)` из use-case handler в одной транзакции с DB-операцией.** Kafka и Postgres не могут участвовать в одной 2PC-транзакции (Kafka не поддерживает XA). При rollback БД событие в Kafka уже опубликовано — несоответствие. Используй outbox.

---

## 2. Consumer

### 2.1 Обязательно

- **R-KFK-CONS-1.** Каждый consumer имеет уникальный **`group.id`** в формате `<service>-<consumer-purpose>`:
  ```yaml
  spring.kafka.consumer:
    group-id: order-service-payments-listener
  ```
  Один consumer-group = одна логическая роль. Не делай общий `group.id: order-service` для всех listener-ов сервиса — потеряется ребалансинг по конкретной задаче.

- **R-KFK-CONS-2.** **Manual ack** — `spring.kafka.listener.ack-mode: MANUAL_IMMEDIATE` (или `MANUAL`). Auto-commit (`enable.auto.commit: true`) опасен: offset коммитится по таймеру независимо от успеха обработки → при крэше consumer теряет события или дублирует. Manual ack = коммитим только после успешной обработки.

  ```java
  @KafkaListener(topics = "orders.confirmed", groupId = "billing-service")
  public void handle(ConsumerRecord<String, OrderConfirmedEvent> record, Acknowledgment ack) {
      try {
          processEvent(record.value());
          ack.acknowledge();   // только после успешной обработки
      } catch (RetryableException e) {
          // не ack-аем — событие повторно дойдёт после next poll
          throw e;
      } catch (NonRetryableException e) {
          ack.acknowledge();   // ack-аем чтобы не зацикливаться, но шлём в DLQ (R-KFK-RTRY-*)
          dlqProducer.send(e, record);
      }
  }
  ```

- **R-KFK-CONS-3.** Listener-метод обязательно **idempotent** (см. `R-KFK-IDEM-*`). Сообщение может прийти 2+ раз — это норма Kafka (at-least-once); duplicate-detection — на стороне consumer.

- **R-KFK-CONS-4.** **`auto.offset.reset: earliest`** для critical-consumer'ов. `latest` (дефолт Spring) пропускает события если consumer-group новая или сильно отстал — недопустимо для денег / orders. `earliest` — начинать с самого старого retained-сообщения.

- **R-KFK-CONS-5.** **Concurrency** — настраивается per-listener:
  ```java
  @KafkaListener(topics = "orders.confirmed", groupId = "billing", concurrency = "3")
  ```
  `concurrency` ≤ числа partition'ов топика. Иначе лишние consumer-instance бездействуют.

- **R-KFK-CONS-6.** **`max.poll.interval.ms`** ≥ ожидаемого времени обработки batch + buffer. Default 5 минут. Если обработка одного сообщения может занять > 5 минут — увеличить, иначе Kafka считает consumer dead и rebalance-ит.

### 2.2 Запрещено

- **R-KFK-CONS-X1.** **`enable.auto.commit: true`** в проде. Авто-коммит = offset продвигается до того, как обработка завершилась. Crash → потеря данных.

- **R-KFK-CONS-X2.** **Listener вызывает `Thread.sleep(...)`** или другие blocking-операции > 1s в одном цикле обработки. Блокирует poll-цикл, может привести к rebalance.

- **R-KFK-CONS-X3.** **`group.id` отсутствует** или одинаковый для двух разных listener-методов в одном сервисе. Без явного `group.id` Spring создаёт случайный — нет ребалансинга между pods.

- **R-KFK-CONS-X4.** **HTTP-вызов к внешней системе из listener** без CB/Bulkhead (`R-RES-WHERE-1`). Если внешняя система лежит, listener зависает → rebalance → дубликаты.

---

## 3. Outbox publishing

Транзакционная публикация событий: запись в БД и публикация в Kafka — **атомарны**. Реализуется через outbox pattern (см. `ucp-pg-runtime-design` — `outbox-relay` сценарий).

### 3.1 Обязательно

- **R-KFK-OBX-1.** **Domain events** публикуются через outbox-relay, **не** напрямую `kafkaTemplate.send(...)` из handler. В handler:
  ```java
  @Transactional
  public Order handle(ConfirmOrderCommand cmd) {
      var order = orderRepository.findById(cmd.orderId(), SelectMode.FOR_UPDATE).orElseThrow();
      order.confirm();
      orderRepository.save(order);

      // Запись в outbox в той же транзакции:
      outboxRepository.append(OutboxEvent.builder()
          .aggregateType("Order")
          .aggregateId(order.getId())
          .eventType("OrderConfirmedEvent")
          .payload(jsonbHelper.serialize(new OrderConfirmedEvent(order)))
          .build());

      return order;
  }
  ```
  Атомарность: либо обе записи коммитятся (БД commit), либо обе откатываются (БД rollback). Kafka сам публикуется отдельно — outbox-relay (см. `R-KFK-OBX-2`).

- **R-KFK-OBX-2.** **Outbox-relay** — отдельный `@Component` с `@Scheduled`, который читает unpublished events с `FOR UPDATE SKIP LOCKED` (см. `PG-L-021`), публикует в Kafka через `KafkaTemplate.send(...)`, помечает `published_at`. Реализация — `ucp-pg-runtime-design` (`outbox` сценарий).

- **R-KFK-OBX-3.** **Topic name** в outbox derives от `eventType` или `aggregateType`:
  - Дефолт: `<service>.<aggregate-type>.<event-name>` — `order-service.order.confirmed`.
  - Альтернативно: один topic на aggregate с разными event-types в payload — нагляднее для consumer-side filtering.

- **R-KFK-OBX-4.** Outbox-relay обрабатывает batch (10–50 events за раз), **не** по одному. Это снижает overhead на DB-poll и Kafka-roundtrip. См. пример в `pg-runtime-style-guide.md`.

### 3.2 Запрещено

- **R-KFK-OBX-X1.** **`kafkaTemplate.send(...)` из `@Transactional`-метода**, особенно где есть DB-операция. Kafka commit не откатывается с DB rollback → inconsistent published events.

- **R-KFK-OBX-X2.** **`@TransactionalEventListener` для отправки в Kafka** без outbox. Обработчик срабатывает после commit → если процесс упал между commit и publish, событие потерялось.

- **R-KFK-OBX-X3.** **Outbox без `published_at` колонки** или без partial-индекса `WHERE published_at IS NULL`. Полный scan таблицы — тормоза.

---

## 4. Idempotent consumer

Kafka гарантирует **at-least-once** delivery. Consumer должен сам справляться с дубликатами.

### 4.1 Обязательно

- **R-KFK-IDEM-1.** Каждое событие имеет **уникальный `eventId`** (UUID v7) в payload или header'е. Consumer проверяет, обрабатывалось ли уже:
  ```java
  @KafkaListener(...)
  public void handle(OrderConfirmedEvent event, Acknowledgment ack) {
      if (processedEventRepository.exists(event.eventId())) {
          ack.acknowledge();
          return;       // duplicate, skip
      }
      processOrder(event);
      processedEventRepository.markProcessed(event.eventId(), Instant.now());
      ack.acknowledge();
  }
  ```

- **R-KFK-IDEM-2.** **`processed_event` таблица** — DDL под `PG-T-*`:
  ```sql
  CREATE TABLE processed_event (
      event_id      uuid PRIMARY KEY,
      consumer_group text NOT NULL,
      processed_at  timestamptz NOT NULL DEFAULT now()
  );
  ```
  PRIMARY KEY на `event_id` — UNIQUE constraint обеспечивает дедупликацию даже под race conditions. **TTL** через partition + drop_old (для долгоживущих топиков) или background-job, удаляющий старые записи.

- **R-KFK-IDEM-3.** **Записи в `processed_event` и бизнес-результат** — в **одной транзакции**. Если процесс упал между бизнес-update и mark-processed → следующий poll увидит «не processed» и обработает повторно (что ОК, потому что бизнес-операция была идемпотентной по `event_id`).

  Альтернатива: использовать `event_id` как `Idempotency-Key` для downstream-команды (см. `AUTH-19`).

- **R-KFK-IDEM-4.** Для **money-операций** — двойная защита: `event_id` + `Idempotency-Key` на downstream HTTP вызовах. Любая retry-петля не должна привести к двойному списанию.

### 4.2 Запрещено

- **R-KFK-IDEM-X1.** **Listener без проверки `eventId`** для consumer'ов, где duplicate приведёт к проблеме. Default Kafka — at-least-once; полагаться на «обычно срабатывает один раз» опасно.

- **R-KFK-IDEM-X2.** Использовать **Kafka offset как dedup-ключ**. Offset зависит от consumer-group; при добавлении нового consumer-group все события приходят как «впервые».

---

## 5. Retry topic + DLQ

Blocking-retry в listener (`Thread.sleep(...)` + retry в цикле) — антипаттерн. Используй **non-blocking retry topic + DLQ**.

### 5.1 Обязательно

- **R-KFK-RTRY-1.** **Retry topics** — отдельные топики с возрастающим delay:
  - `orders.confirmed` — основной.
  - `orders.confirmed.retry-1m` — retry через 1 мин.
  - `orders.confirmed.retry-10m` — retry через 10 мин.
  - `orders.confirmed.dlq` — окончательный fail после N попыток.

  Spring Kafka supports это через `@RetryableTopic`:
  ```java
  @RetryableTopic(
      attempts = "4",
      backoff = @Backoff(delay = 60_000, multiplier = 10),
      autoCreateTopics = "false",      // топики создаются явно через Liquibase-аналог или admin
      include = {RetryableException.class},
      exclude = {NonRetryableException.class}
  )
  @KafkaListener(topics = "orders.confirmed")
  public void handle(OrderConfirmedEvent event, Acknowledgment ack) { ... }
  ```

- **R-KFK-RTRY-2.** Retry **только для transient failures**:
  - Сетевые ошибки (`IOException`, `ConnectException`).
  - 5xx от downstream HTTP.
  - Database timeout.

  **Не retry**:
  - 4xx от downstream (контрактная ошибка).
  - `IllegalArgumentException` / `NullPointerException` — баг, retry не поможет.
  - Validation failures.

- **R-KFK-RTRY-3.** **DLQ-monitoring** — alert если в DLQ за час > N сообщений. Без алерта DLQ становится свалкой, и проблемы не замечают.

- **R-KFK-RTRY-4.** **Replay из DLQ** — отдельная админская операция (manual review + re-publish в основной топик). Не автоматическая (могут быть genuine bug).

### 5.2 Запрещено

- **R-KFK-RTRY-X1.** **Blocking retry в listener** через `Thread.sleep(N)` или `@Retryable` Spring-Retry с большой задержкой. Блокирует poll-цикл.

- **R-KFK-RTRY-X2.** **Игнорирование исключения** в listener (`try { ... } catch (Exception e) { log.error(...); ack.acknowledge(); }`). Событие потеряно, никто не узнает что не обработали.

- **R-KFK-RTRY-X3.** **Retry topic без max-attempts**. Бесконечный retry = lock-step с проблемной системой.

- **R-KFK-RTRY-X4.** **DLQ без monitoring**. Alert на размер очереди — обязательно.

---

## 6. Event design

### 6.1 Обязательно

- **R-KFK-EVT-1.** **Имя события** — глагол в прошедшем времени: `OrderConfirmed`, `PaymentFailed`, `UserRegistered`. Не `ConfirmOrder` (это команда), не `OrderConfirmation` (это noun).

- **R-KFK-EVT-2.** Payload содержит:
  - `eventId` — UUID v7, уникален.
  - `eventType` — string id, версионированный (`order.confirmed.v1`).
  - `occurredAt` — `OffsetDateTime` (когда произошло событие, не когда опубликовано).
  - `aggregateType`, `aggregateId` — для маршрутизации/дедупа.
  - **Бизнес-данные** — необходимые consumer-у для обработки.
  - **Не PII в payload** для топиков с broad consumer-base. Если PII — отдельный «full event» topic с restricted access (см. `R-KFK-SEC-2`).

- **R-KFK-EVT-3.** **Forward-compatible schema:** добавление новых полей — non-breaking. Удаление / переименование — breaking, требует нового `eventType.v2`. См. `R-VER-5` (REST forward-compat).

- **R-KFK-EVT-4.** **Domain event как Java record** в `core/<bc>/domain/event/`:
  ```java
  public record OrderConfirmedEvent(
      UUID eventId,
      String eventType,
      OffsetDateTime occurredAt,
      Long orderId,
      Long customerId,
      Money totalAmount
  ) {
      public static OrderConfirmedEvent from(Order order) {
          return new OrderConfirmedEvent(
              UuidV7.generate(),
              "order.confirmed.v1",
              order.getConfirmedAt(),
              order.getId(),
              order.getCustomerId(),
              order.getTotalAmount()
          );
      }
  }
  ```

### 6.2 Запрещено

- **R-KFK-EVT-X1.** **Имя события — команда** (`ConfirmOrder` вместо `OrderConfirmed`). Команды и события — разные концепты в DDD.

- **R-KFK-EVT-X2.** **Внутренние объекты в payload** (`Aggregate`, `Entity` целиком). Сериализация может включить нестабильные внутренние поля, ломает forward-compat.

- **R-KFK-EVT-X3.** **PII в широковещательных топиках** (`orders.confirmed` — все consumer'ы видят email, phone). Нужен отдельный restricted-topic или по `customerId` подгрузка PII через сервис.

- **R-KFK-EVT-X4.** **Breaking change без версии в `eventType`**. Старые consumer'ы при regenerate схемы перестанут работать.

---

## 7. Конфигурация

### 7.1 Обязательно

- **R-KFK-CFG-1.** Через `@ConfigurationProperties` + `@Validated` (`R-VLD-CFG-*`):
  ```java
  @ConfigurationProperties("kafka")
  @Validated
  public record KafkaSettings(
      @NotBlank String bootstrapServers,
      @NotNull Producer producer,
      @NotEmpty Map<String, ConsumerConfig> consumers
  ) {
      public record Producer(
          @NotNull Duration requestTimeout,
          @Min(0) int retryBackoffMs
      ) {}

      public record ConsumerConfig(
          @NotBlank String groupId,
          @NotEmpty List<@NotBlank String> topics,
          @Min(1) int concurrency,
          @NotNull Duration maxPollInterval
      ) {}
  }
  ```

- **R-KFK-CFG-2.** `application.yml`:
  ```yaml
  spring.kafka:
    bootstrap-servers: ${KAFKA_BROKERS:localhost:9092}
    producer:
      acks: all
      properties:
        enable.idempotence: true
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
    consumer:
      auto-offset-reset: earliest
      enable-auto-commit: false
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      properties:
        spring.json.trusted.packages: ru.example.events.*
    listener:
      ack-mode: MANUAL_IMMEDIATE
      missing-topics-fatal: true       # fail-fast если топика нет
  ```

- **R-KFK-CFG-3.** **`spring.json.trusted.packages`** — explicit allow-list. По умолчанию Spring блокирует deserialization (security). Указывай только пакеты с event-records.

- **R-KFK-CFG-4.** **`missing-topics-fatal: true`** в проде. Сервис не должен стартовать если ожидаемый топик не существует — ловим конфигурационные ошибки на старте.

### 7.2 Запрещено

- **R-KFK-CFG-X1.** **`spring.json.trusted.packages: '*'`** — security risk (deserialization gadgets из произвольных классов).

- **R-KFK-CFG-X2.** **`bootstrap-servers` hard-coded** в коде или yml без env-substitution. Нельзя катить разные кластеры (test/prod).

---

## 8. Observability

### 8.1 Обязательно

- **R-KFK-OBS-1.** Spring Kafka автоматически экспортирует через Micrometer:
  - `kafka_consumer_records_consumed_total{client_id,topic}`
  - `kafka_consumer_lag` (records behind) — **главный health-сигнал**.
  - `kafka_consumer_records_lag_max{topic,partition}`
  - `kafka_producer_record_send_total{topic}`
  - `kafka_producer_record_error_total{topic}`

- **R-KFK-OBS-2.** **Alert на consumer lag**: если `kafka_consumer_lag > N` для критичных topic'ов в течение 5 минут → инцидент. Threshold зависит от пропускной способности (для money-events — 1000; для analytics — 100000).

- **R-KFK-OBS-3.** **Tracing через `traceparent`** (см. `R-HDR-4` REST). Producer кладёт current `traceparent` в Kafka headers; consumer извлекает и продолжает trace. Spring Kafka + OTel автоконфиг это делает.

- **R-KFK-OBS-4.** **DLQ-size alert** (см. `R-KFK-RTRY-3`).

### 8.2 Запрещено

- **R-KFK-OBS-X1.** **Отсутствие consumer-lag alerts**. Без них «пропадание» сообщений замечается через жалобы пользователей.

---

## 9. Security

### 9.1 Обязательно

- **R-KFK-SEC-1.** В прод-кластере **TLS** (`security.protocol: SSL`) — обязательно для cross-network communication. SASL/PLAIN over plaintext запрещено.

- **R-KFK-SEC-2.** **ACL'ы на топики** — каждый сервис имеет ACL на чтение/запись только тех топиков, что ему нужны. Проектирование — DevOps/SRE, использование — clientId per-сервис в `KafkaSettings`.

- **R-KFK-SEC-3.** **PII-данные** — отдельные топики с restricted ACL, либо паттерн «слабая ссылка»: в широком топике только `customerId`, full PII consumer запрашивает у Customer-сервиса.

### 9.2 Запрещено

- **R-KFK-SEC-X1.** **`PLAINTEXT` в проде**. Только в локальной разработке.

- **R-KFK-SEC-X2.** **Один service-account** на весь кластер. ACL'ы по сервисам — для blast-radius containment.

---

## 10. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| `enable.idempotence: false` | `R-KFK-PROD-X1` | `true` всегда |
| `acks: 0` или `acks: 1` | `R-KFK-PROD-X2` | `acks: all` |
| Send без partition key | `R-KFK-PROD-X3` | aggregate id как key |
| `kafkaTemplate.send` в `@Transactional` с DB-операцией | `R-KFK-PROD-X4`, `R-KFK-OBX-X1` | через outbox |
| `@TransactionalEventListener` для Kafka | `R-KFK-OBX-X2` | outbox-relay |
| Outbox без partial-index | `R-KFK-OBX-X3` | `WHERE published_at IS NULL` |
| `enable.auto.commit: true` | `R-KFK-CONS-X1` | `MANUAL_IMMEDIATE` ack |
| `Thread.sleep(N)` в listener | `R-KFK-CONS-X2`, `R-KFK-RTRY-X1` | retry topic |
| `group.id` отсутствует/общий | `R-KFK-CONS-X3` | `<service>-<purpose>` |
| HTTP к внешней системе из listener без CB | `R-KFK-CONS-X4` | `@CircuitBreaker` |
| Listener без проверки `eventId` | `R-KFK-IDEM-X1` | dedup через `processed_event` |
| Offset как dedup-ключ | `R-KFK-IDEM-X2` | `eventId` UUID v7 |
| Retry topic без max-attempts | `R-KFK-RTRY-X3` | 3-5 attempts → DLQ |
| DLQ без monitoring | `R-KFK-RTRY-X4`, `R-KFK-OBS-X1` | alert на размер |
| Игнорирование exception в listener | `R-KFK-RTRY-X2` | DLQ + alert |
| Имя события — команда (`ConfirmOrder`) | `R-KFK-EVT-X1` | `OrderConfirmed` |
| Aggregate целиком в payload | `R-KFK-EVT-X2` | бизнес-поля + IDs |
| PII в широковещательных топиках | `R-KFK-EVT-X3`, `R-KFK-SEC-3` | restricted topic / по ID |
| Breaking change без версии | `R-KFK-EVT-X4` | `eventType.v2` |
| `spring.json.trusted.packages: '*'` | `R-KFK-CFG-X1` | explicit allow-list |
| Hard-coded `bootstrap-servers` | `R-KFK-CFG-X2` | env-substitution |
| `PLAINTEXT` в проде | `R-KFK-SEC-X1` | TLS / SASL |
| Один service-account на кластер | `R-KFK-SEC-X2` | per-сервис ACLs |

Финальная сводка: правил «Обязательно» — около 30, «Запрещено» — около 25.
