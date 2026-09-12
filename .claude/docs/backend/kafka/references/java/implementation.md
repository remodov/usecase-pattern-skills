# Kafka — реализация

Свод правил работы с Kafka в Java/Spring-сервисах команды UCP: producer (idempotence, partition key), consumer (groups, offset, listener), outbox-relay для надёжной публикации, idempotent consumer с dedup, retry topic + DLQ вместо blocking retry, event design, observability lag. Каждое правило идентифицируется кодом (`kafka/producer-is-idempotent`, `kafka/manual-offset-commit`) — скилл `ucp-kafka-review` цитирует эти коды в findings.

Гайд опирается на [Apache Kafka 3.x](https://kafka.apache.org/) + [spring-kafka](https://docs.spring.io/spring-kafka/reference/) (Spring Boot 3+). Не покрывает: Kafka cluster admin (broker config, replication, MirrorMaker — это инфра-уровень), Kafka Streams (`R-KFK-STREAM-*` — отдельная тема), ksqlDB.

Связанные стандарты:
- `pg-runtime/skip-locked-for-queues`/`pg-runtime/skip-locked-for-queues` (PG runtime) — outbox-relay через `FOR UPDATE SKIP LOCKED`.
- `R-RES-*` (Resilience) — Kafka producer/consumer тоже outbound, имеют свои timeout/retry стратегии.
- `R-ENT-*`/`R-AGG-*`/`R-EVT-*` (DDD tactical) — Domain Events как payload Kafka-сообщений.
- `auth-patterns/money-commands-need-idempotency-key` (`auth-patterns/money-commands-need-idempotency-key`) (Auth) — money-операции через Kafka требуют идемпотентности.
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

- **R-KFK-CONS-2.** **Коммит только после успешной обработки записи.** `enable.auto.commit: false` всегда; способ подтверждения — один из двух, на сервис:
  - **`AckMode.RECORD`** (эталон partnerapi-hub) — контейнер коммитит после каждой успешно обработанной записи; в сигнатуре listener'а `Acknowledgment` нет, исключение уходит в `DefaultErrorHandler` (§5, вариант B), который сам решает — повторить или в DLQ:
    ```java
    @KafkaListener(topics = "#{@kafkaTopicNamesConfiguration.tariffsFactStateV1}")
    public void onMessage(ConsumerRecord<String, String> record) throws JsonProcessingException {
        EntityStateMessage<TariffStateMessage> message = objectMapper.readValue(record.value(), new TypeReference<>() {});
        dispatcher.dispatch(mapper.toCommand(message.payload()));
    }
    ```
    `factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.RECORD)` в `KafkaConfiguration`; listener ничего не ловит и ничего не подтверждает сам.
  - **`MANUAL_IMMEDIATE`** — listener получает `Acknowledgment` и зовёт `ack.acknowledge()` строго после обработки; удобно, когда одно сообщение обрабатывается несколькими шагами и подтверждать нужно между ними.

  Auto-commit (`enable.auto.commit: true`) опасен в обоих случаях: offset коммитится по таймеру независимо от успеха → при крэше события теряются или дублируются.

- **R-KFK-CONS-3.** Listener-метод обязательно **idempotent** (см. `R-KFK-IDEM-*`). Сообщение может прийти 2+ раз — это норма Kafka (at-least-once); duplicate-detection — на стороне consumer.

- **R-KFK-CONS-4.** **`auto.offset.reset: earliest`** для critical-consumer'ов. `latest` (дефолт Spring) пропускает события если consumer-group новая или сильно отстал — недопустимо для денег / orders. `earliest` — начинать с самого старого retained-сообщения.

- **R-KFK-CONS-5.** **Concurrency** — настраивается per-listener:
  ```java
  @KafkaListener(topics = "orders.confirmed", groupId = "billing", concurrency = "3")
  ```
  `concurrency` ≤ числа partition'ов топика. Иначе лишние consumer-instance бездействуют.

- **R-KFK-CONS-6.** **`max.poll.interval.ms`** ≥ ожидаемого времени обработки batch + buffer. Default 5 минут. Если обработка одного сообщения может занять > 5 минут — увеличить, иначе Kafka считает consumer dead и rebalance-ит.

- **R-KFK-CONS-7.** **Справочники из шины — с наливом через API источника** (`kafka/reference-data-backfilled-via-api`). Retention топика — дни (`retention.ms` у эталона 7 суток), реплика живёт годами: новый экземпляр, новая группа или простой дольше retention не соберут состояние из топика, `auto.offset.reset: earliest` это не лечит. Форма из эталона: отдельный `<source>-rest-out-adapter` с клиентом к API источника, `*BootstrapProcessing` под ShedLock, который при пустой реплике (`replicaEmpty`-guard) наливает справочники командами обновления — тихо, без публикации событий наружу, — после чего поток снимков из Kafka держит реплику актуальной.

### 2.2 Запрещено

- **R-KFK-CONS-X1.** **`enable.auto.commit: true`** в проде. Авто-коммит = offset продвигается до того, как обработка завершилась. Crash → потеря данных.

- **R-KFK-CONS-X2.** **Listener вызывает `Thread.sleep(...)`** или другие blocking-операции > 1s в одном цикле обработки. Блокирует poll-цикл, может привести к rebalance.

- **R-KFK-CONS-X3.** **`group.id` отсутствует** или одинаковый для двух разных listener-методов в одном сервисе. Без явного `group.id` Spring создаёт случайный — нет ребалансинга между pods.

- **R-KFK-CONS-X4.** **HTTP-вызов к внешней системе из listener** без CB/Bulkhead (`resilience/outbound-calls-fully-protected`). Если внешняя система лежит, listener зависает → rebalance → дубликаты.

---

## 3. Outbox publishing

Транзакционная публикация событий: запись в БД и публикация в Kafka — **атомарны**. Реализуется через outbox pattern (см. `ucp-pg-runtime-design` — `outbox-relay` сценарий).

### 3.1 Обязательно

- **R-KFK-OBX-1.** **Domain events** публикуются через outbox, **не** напрямую `kafkaTemplate.send(...)` из handler. Handler об outbox не знает: агрегат регистрирует событие (`registerEvent`), а jOOQ-репозиторий при `save()` через `OutboxDomainEventAppender` превращает каждое событие в запись outbox — в той же транзакции:
  ```java
  public <E extends DomainEvent> void appendEvents(
          AggregateRoot<UUID> aggregate, Class<E> eventClass, DomainEventContractMapper<E> contractMapper) {
      for (DomainEvent domainEvent : aggregate.getEvents()) {
          E event = eventClass.cast(domainEvent);
          OutboxDomainEvent outboxEvent = OutboxDomainEventFactory.create(event.eventType(), aggregate.getId());
          outboxEvent.attachPayload(contractMapper.toPayload(outboxEvent, event));
          outboxDomainEventRepository.save(outboxEvent);
      }
      aggregate.clearDomainEvents();
  }
  ```
  Outbox — сам агрегат (`OutboxDomainEvent`) со статусом и `attempts`, а не «таблица с колонкой»; payload собирает `DomainEventContractMapper` — порт в `core/port/out/publisher`, реализованный в `kafka-out-adapter`, где живут wire-модели. Атомарность: либо агрегат и его outbox-записи коммитятся вместе, либо откатываются вместе.

- **R-KFK-OBX-2.** **Outbox-relay** — use case, а не `@Component` с логикой: `*Processing` в `scheduler-in-adapter` диспатчит `SendOutboxDomainEventsCommand(batchSize, reclaimAfter)`, а handler в core захватывает пачку `FOR UPDATE SKIP LOCKED` (см. `pg-runtime/skip-locked-for-queues`), для каждой записи открывает свою транзакцию через `TransactionTemplate`, зовёт порт публикации и помечает отправленной; зависшие захваты старше `reclaimAfter` возвращаются в работу. Отметка «отправлено» — только после ack брокера (`R-KFK-OBX-5`).

- **R-KFK-OBX-3.** **Topic name** в outbox derives от `eventType` или `aggregateType`:
  - Дефолт: `<service>.<aggregate-type>.<event-name>` — `order-service.order.confirmed`.
  - Альтернативно: один topic на aggregate с разными event-types в payload — нагляднее для consumer-side filtering.

- **R-KFK-OBX-4.** Outbox-relay обрабатывает batch (10–100 events за раз), **не** по одному. Это снижает overhead на DB-poll и Kafka-roundtrip. См. пример в `backend/pg-runtime/references/implementation.md`.

- **R-KFK-OBX-5.** **Отметка об отправке — только после подтверждения брокера.** Порт публикации возвращает управление после ack: `kafkaTemplate.send(topic, key, json).get(timeout)` для одиночной записи; для пачки — отправить все, дождаться future'ов с таймаутом (`delivery.timeout.ms` — верхняя граница), отметить отправленными только подтверждённые. Цена — throughput relay-потока (round-trip на сообщение); за неё покупается гарантия, что `published_at` не встанет раньше, чем брокер записал. Отметка сразу после `send(...)` без ожидания — потеря сообщения при недоступном брокере, молча.

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

  Альтернатива: использовать `event_id` как `Idempotency-Key` для downstream-команды (см. `auth-patterns/money-commands-need-idempotency-key`).

- **R-KFK-IDEM-4.** Для **money-операций** — двойная защита: `event_id` + `Idempotency-Key` на downstream HTTP вызовах. Любая retry-петля не должна привести к двойному списанию.

### 4.2 Запрещено

- **R-KFK-IDEM-X1.** **Listener без проверки `eventId`** для consumer'ов, где duplicate приведёт к проблеме. Default Kafka — at-least-once; полагаться на «обычно срабатывает один раз» опасно.

- **R-KFK-IDEM-X2.** Использовать **Kafka offset как dedup-ключ**. Offset зависит от consumer-group; при добавлении нового consumer-group все события приходят как «впервые».

**Отступление для потоков снимков состояния.** Если по топику летят не события, а полные снимки сущности с меткой версии (`updatedAt`), dedup по `eventId` теряет смысл — важен не факт повтора, а порядок: агрегат сам отбрасывает снимок старше уже применённого (`isStale(incoming.updatedAt)` → `update()` возвращает `false`, handler логирует и выходит). Так устроена CSMS-синхронизация эталона. Это решение конкретного потока, а не норма: оно фиксируется в `CLAUDE.md` сервиса, требование `kafka/consumer-is-idempotent` остаётся про `eventId`.

Поток снимков справочника обрабатывается тем же listener'ом, но **без проверок формы**: копия чужих данных сохраняется как пришла, на приёме проверяются идентификатор и метка версии (`validation/replica-is-stored-as-received`). Иначе запись владельца, не прошедшая нашу проверку, уходит в DLQ, и справочник в сервисе оказывается неполным молча.

---

## 5. Повторы и DLQ — два варианта

Blocking-retry в коде listener'а (`Thread.sleep(...)` + retry в цикле, `@Retryable` с большой паузой) — антипаттерн. Повторы делает инфраструктура, одним из двух способов на сервис:

- **Вариант A — retry-топики** (`@RetryableTopic`): non-blocking, повтор уходит в отдельный топик с задержкой, партиция основного топика не ждёт. Цена — по два-три топика на каждый входной и `@DltHandler`.
- **Вариант B — `DefaultErrorHandler` с backoff** (эталон partnerapi-hub): контейнер повторяет запись на месте с растущей паузой, ограниченной так, чтобы суммарно быть много меньше `max.poll.interval.ms`; исчерпал — recoverer пишет в DLQ и коммитит смещение (`setCommitRecovered(true)`). Партиция стоит секунды, зато ни одного лишнего топика:
  ```java
  @Bean
  public DefaultErrorHandler kafkaErrorHandler(KafkaErrorHandlerProperties properties, KafkaDlqRecorder dlqRecorder) {
      ExponentialBackOffWithMaxRetries backOff = new ExponentialBackOffWithMaxRetries(properties.getMaxAttempts());
      backOff.setInitialInterval(properties.getInterval());
      backOff.setMultiplier(properties.getMultiplier());
      backOff.setMaxInterval(properties.getMaxInterval());
      DefaultErrorHandler errorHandler = new DefaultErrorHandler(dlqRecorder::record, backOff);
      errorHandler.setCommitRecovered(true);
      errorHandler.setRetryListeners(dlqRecorder::onRetry);
      errorHandler.addNotRetryableExceptions(IllegalArgumentException.class, JsonProcessingException.class);
      errorHandler.addNotRetryableExceptions(SessionException.NotFound.class);
      return errorHandler;
  }
  ```
  `addNotRetryableExceptions` — обязательная часть: контрактные ошибки (невалидное тело, неизвестная сущность, аргумент) уходят в DLQ сразу, без трёх пауз (`R-KFK-RTRY-2`). Параметры — `@ConfigurationProperties` (`interval`, `max-attempts`, `multiplier`, `max-interval`), у эталона 3 попытки: 1 с → 2 с → 4 с, потолок 10 с.

DLQ в обоих вариантах — либо топик `.dlq`, либо **таблица в базе** (`R-KFK-RTRY-5`).

### 5.1 Обязательно

- **R-KFK-RTRY-1.** **Retry topics** (вариант A) — отдельные топики с возрастающим delay:
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

- **R-KFK-RTRY-5.** **DLQ в базе** — равноправная альтернатива `.dlq`-топику, когда у сервиса уже есть PostgreSQL: неразобранное сообщение видно обычным SQL, retention делает тот же cleanup-процессинг, что чистит outbox. Форма из эталона — таблица `kafka_errors` и recoverer:
  ```yaml
  - createTable:
      tableName: kafka_errors
      columns:
        - column: { name: id, type: uuid, constraints: { primaryKey: true } }
        - column: { name: topic, type: text, constraints: { nullable: false } }
        - column: { name: partition, type: int, constraints: { nullable: false } }
        - column: { name: message_offset, type: bigint, constraints: { nullable: false } }
        - column: { name: key, type: text }
        - column: { name: value, type: text }
        - column: { name: error_message, type: text }
        - column: { name: stack_trace, type: text }
        - column: { name: created_at, type: timestamptz, constraints: { nullable: false } }
  - createIndex: { tableName: kafka_errors, indexName: idx_kafka_errors_created_at, columns: [ { column: { name: created_at } } ] }
  ```
  ```java
  public void record(ConsumerRecord<?, ?> record, Exception exception) {
      Throwable rootCause = ExceptionUtils.getRootCause(exception);
      kafkaErrorRepository.save(new KafkaErrorsPojo()
          .setId(UUID.randomUUID())
          .setTopic(record.topic())
          .setPartition(record.partition())
          .setMessageOffset(record.offset())
          .setKey(record.key() != null ? record.key().toString() : null)
          .setValue(record.value() != null ? record.value().toString() : null)
          .setErrorMessage(rootCause != null ? rootCause.getMessage() : exception.getMessage())
          .setStackTrace(ExceptionUtils.getStackTrace(exception))
          .setCreatedAt(DateTimeUtil.currentDateTime()));
      meterRegistry.counter("kafka.dlq", "topic", record.topic()).increment();
  }
  ```
  Репозиторий DLQ — порт в `core/port/out/repository` (`KafkaErrorsRepository`), реализация в persistence-адаптере. Метрика `kafka.dlq` по топику + счётчик повторов `kafka.retry` из `setRetryListeners` — то, на что вешается оповещение (`R-KFK-RTRY-3`); retention (у эталона 30 суток) — отдельным прогоном cleanup. Падение записи в DLQ пробрасывается: сообщение не подтверждается и придёт снова — терять его тише нельзя.

### 5.2 Запрещено

- **R-KFK-RTRY-X1.** **Blocking retry в коде listener'а** через `Thread.sleep(N)` или `@Retryable` Spring-Retry с большой задержкой. Блокирует poll-цикл. Backoff в `DefaultErrorHandler` — не это: он ограничен настройкой и живёт в контейнере, а не в обработчике; но и его суммарная пауза обязана быть много меньше `max.poll.interval.ms`.

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
  - **Не PII в payload** для топиков с broad consumer-base. Если PII — отдельный «full event» topic с restricted access (см. `kafka/transport-security-and-acls`).

- **R-KFK-EVT-3.** **Forward-compatible schema:** добавление новых полей — non-breaking. Удаление / переименование — breaking, требует нового `eventType.v2`. См. `rest-api/client-tolerates-unknown-values` (REST forward-compat).

- **R-KFK-EVT-4.** **Domain event как Java record** в `core/domain/event/`:
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

- **R-KFK-EVT-5.** **Два вида сообщений — событие-факт и снимок состояния.** Событие-факт (`OrderConfirmed`) несёт `eventId`, `eventType`, `occurredAt` и минимум полей; потребитель дедуплицирует по `eventId` (§4). Снимок состояния (`EntityStateMessage<TariffStateMessage>` в эталоне — топики `<prefix>.<entity>.fact.state.<v>`) несёт полное текущее состояние сущности и метку версии `updatedAt`; потребитель применяет его через `update(...)` агрегата, и порядок важнее факта повтора (stale-guard, отступление в §4). Вид сообщения — решение на топик, не смешивать в одном. Модели сообщений между сервисами — общий артефакт (`ru.metro.energy:kafka-models`), а не копия record'ов у каждого потребителя: в `core` он не попадает — маппинг в команду делает `*KafkaMapper` в `kafka-in-adapter`, payload наружу собирает `*EventContractMapper` в `kafka-out-adapter`. Имена топиков — `<prefix-окружения>.<entity>.<fact|commands>.<version>`, и версия — часть имени, а не поля.

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

- **R-KFK-CFG-2.** `application.yml` — форма из эталона, все значения через `${ENV:default}`:
  ```yaml
  spring.kafka:
    bootstrap-servers: ${KAFKA_BOOTSTRAP_SERVERS:localhost:29092}
    security:
      protocol: ${KAFKA_SECURITY_PROTOCOL:SASL_PLAINTEXT}
    properties:
      sasl.mechanism: ${KAFKA_SASL_MECHANISM:PLAIN}
      sasl.jaas.config: org.apache.kafka.common.security.plain.PlainLoginModule required username="${KAFKA_USERNAME}" password="${KAFKA_PASSWORD}";
    producer:
      acks: all
      compression-type: ${KAFKA_PRODUCER_COMPRESSION:zstd}
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer   # payload уже JSON-строка
      properties:
        enable.idempotence: true
        max.in.flight.requests.per.connection: 5
        delivery-timeout-ms: ${KAFKA_PRODUCER_DELIVERY_TIMEOUT:120000}
    consumer:
      group-id: ${KAFKA_CONSUMER_GROUP}                 # per-purpose, R-KFK-CONS-1
      auto-offset-reset: earliest
      enable-auto-commit: false
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.apache.kafka.common.serialization.StringDeserializer   # разбор в тип — в listener'е
      properties:
        allow.auto.create.topics: false                 # чужие топики не создаём
        max.poll.interval.ms: ${KAFKA_MAX_POLL_INTERVAL:300000}
    listener:
      ack-mode: RECORD                                   # либо MANUAL_IMMEDIATE, R-KFK-CONS-2
      missing-topics-fatal: true                         # fail-fast, если топика нет
      concurrency: ${KAFKA_LISTENER_CONCURRENCY:3}
      error-handler:                                     # свои свойства для DefaultErrorHandler, §5 B
        interval: ${KAFKA_ERROR_HANDLER_INTERVAL:1000}
        max-attempts: ${KAFKA_ERROR_HANDLER_MAX_ATTEMPTS:3}
        multiplier: ${KAFKA_ERROR_HANDLER_MULTIPLIER:2.0}
        max-interval: ${KAFKA_ERROR_HANDLER_MAX_INTERVAL:10000}
    topic-defaults:                                      # для своих топиков, R-KFK-CFG-5
      partitions: ${KAFKA_TOPIC_PARTITIONS:3}
      replicas: ${KAFKA_TOPIC_REPLICAS:1}
      configuration:
        cleanup.policy: delete
        retention.ms: ${KAFKA_TOPIC_RETENTION:604800000}
        min.insync.replicas: ${KAFKA_TOPIC_MIN_INSYNC_REPLICAS:1}
    topic-names:                                         # имена — через префикс окружения
      tariffs-fact-state-v1: ${KAFKA_TOPIC_PREFIX:local}.tariffs.fact.state.1
      partnerapi-locations-fact-v1: ${KAFKA_TOPIC_PREFIX:local}.partnerapi-locations.fact.1
  ```
  Имена топиков в listener'ах — через бин: `@KafkaListener(topics = "#{@kafkaTopicNamesConfiguration.tariffsFactStateV1}")`; `KafkaTopicNamesConfiguration` — `@ConfigurationProperties("spring.kafka.topic-names")`, реализует порт `KafkaTopicNames` из `core/port/in`, так что имена не расползаются строками по коду. Если value-десериализатор — `JsonDeserializer`, добавляется `spring.json.trusted.packages` с явным списком пакетов.

- **R-KFK-CFG-3.** **Десериализация — только в явно заданный тип.** Либо `JsonDeserializer` + `spring.json.trusted.packages` с явным списком пакетов event-records, либо `StringDeserializer` и `objectMapper.readValue(record.value(), new TypeReference<EntityStateMessage<TariffStateMessage>>() {})` прямо в listener'е — целевой тип задан кодом, allow-list не нужен. Оба закрывают `kafka/deserialization-allow-list`; `'*'` — нет.

- **R-KFK-CFG-4.** **`missing-topics-fatal: true`** в проде. Сервис не должен стартовать если ожидаемый топик не существует — ловим конфигурационные ошибки на старте: опечатка в `KAFKA_TOPIC_PREFIX` иначе даёт здоровый сервис, который молча ничего не читает. Со своими топиками (`R-KFK-CFG-5`) не конфликтует — `KafkaAdmin` создаёт их до старта контейнеров.

- **R-KFK-CFG-5.** **Свои топики сервис создаёт сам, чужие — никогда.** `allow.auto.create.topics: false` у consumer'а, а топики, которые сервис публикует, объявлены бином `KafkaAdmin.NewTopics` с параметрами из `topic-defaults`:
  ```java
  @Bean
  public KafkaAdmin.NewTopics ownedTopics(KafkaTopicNamesConfiguration names, KafkaTopicDefaultsProperties defaults) {
      return new KafkaAdmin.NewTopics(
          topic(names.getPartnerLocationsFactV1(), defaults),
          topic(names.getHubConnectionsFactV1(), defaults));
  }

  private NewTopic topic(String name, KafkaTopicDefaultsProperties defaults) {
      return TopicBuilder.name(name)
          .partitions(defaults.getPartitions())
          .replicas(defaults.getReplicas())
          .configs(defaults.getConfiguration())
          .build();
  }
  ```
  Compact-топики не используются; retention — явный, а не дефолт брокера.

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

- **R-KFK-OBS-3.** **Tracing через `traceparent`** (см. `rest-api/trace-context-header` REST). Producer кладёт current `traceparent` в Kafka headers; consumer извлекает и продолжает trace. Spring Kafka + OTel автоконфиг это делает.

- **R-KFK-OBS-4.** **DLQ-size alert** (см. `kafka/dlq-monitored-and-manually-replayed`).

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
| `enable.idempotence: false` | `kafka/producer-is-idempotent` | `true` всегда |
| `acks: 0` или `acks: 1` | `kafka/producer-is-idempotent` | `acks: all` |
| Send без partition key | `kafka/partition-key-required` | aggregate id как key |
| `kafkaTemplate.send` в `@Transactional` с DB-операцией | `kafka/publish-via-outbox`, `kafka/publish-via-outbox` | через outbox |
| `@TransactionalEventListener` для Kafka | `kafka/publish-via-outbox` | outbox-relay |
| Outbox без partial-index | `kafka/outbox-table-shape` | `WHERE published_at IS NULL` |
| `enable.auto.commit: true` | `kafka/manual-offset-commit` | `MANUAL_IMMEDIATE` ack |
| `Thread.sleep(N)` в listener | `kafka/listener-does-not-block-poll-loop`, `kafka/retry-topics-with-limits` | retry topic |
| `group.id` отсутствует/общий | `kafka/consumer-group-per-purpose` | `<service>-<purpose>` |
| HTTP к внешней системе из listener без CB | `kafka/listener-does-not-block-poll-loop` | `@CircuitBreaker` |
| Listener без проверки `eventId` | `kafka/consumer-is-idempotent` | dedup через `processed_event` |
| Offset как dedup-ключ | `kafka/consumer-is-idempotent` | `eventId` UUID v7 |
| Retry topic без max-attempts | `kafka/retry-topics-with-limits` | 3-5 attempts → DLQ |
| DLQ без monitoring | `kafka/dlq-monitored-and-manually-replayed`, `kafka/consumer-lag-alerting` | alert на размер |
| Игнорирование exception в listener | `kafka/no-swallowing-in-listener` | DLQ + alert |
| Имя события — команда (`ConfirmOrder`) | `kafka/event-named-in-past-tense` | `OrderConfirmed` |
| Aggregate целиком в payload | `kafka/event-payload-hygiene` | бизнес-поля + IDs |
| PII в широковещательных топиках | `kafka/event-payload-hygiene`, `kafka/event-payload-hygiene` | restricted topic / по ID |
| Breaking change без версии | `kafka/event-schema-forward-compatible` | `eventType.v2` |
| `spring.json.trusted.packages: '*'` | `kafka/deserialization-allow-list` | explicit allow-list |
| Hard-coded `bootstrap-servers` | `kafka/settings-are-typed-and-external` | env-substitution |
| `PLAINTEXT` в проде | `kafka/transport-security-and-acls` | TLS / SASL |
| Один service-account на кластер | `kafka/transport-security-and-acls` | per-сервис ACLs |

Финальная сводка: правил «Обязательно» — около 30, «Запрещено» — около 25.
