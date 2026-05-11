---
name: ucp-kafka-design
description: Сгенерировать Kafka producer/consumer обвязку под Kafka Style Guide — KafkaConfig (idempotent producer + JsonSerializer + manual-ack consumer), KafkaSettings @ConfigurationProperties + @Validated, @KafkaListener с правильным groupId/concurrency/retry-topic, idempotent consumer с processed_event таблицей, event-record в past tense, application.yml блок. Решает: outbox vs direct send (если есть DB-операция → outbox через ucp-pg-runtime-design); retry topic vs DLQ (max-attempts, backoff); idempotency через eventId UUID v7 + dedup-таблица; partition key (aggregate id); event design (имя в past tense, версионирование eventType). Применяется при добавлении нового producer / consumer / event-flow в сервис. Триггеры: «настрой Kafka producer», «нужен listener для X», «event-driven flow для Y», «outbox для Order».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Kafka — проектирование

Ты генерируешь Kafka-обвязку (producer config, consumer config, listener-классы, event-records, processed_event DDL) по Kafka Style Guide. Цель — компоненты, проходящие `ucp-kafka-review` без findings.

## Инструкции

1. **Прочитай** `.claude/docs/kafka-rules.md` (`R-KFK-*`). Опционально — `pg-runtime-style-guide.md` (для outbox), `auth-patterns-style-guide.md` (`AUTH-19` для money), `ddd-tactical-rules.md` (`R-EVT-*`).

2. **Уточни сценарий:**
   - **Producer-only** — сервис публикует events, других сервисов потребители.
   - **Consumer-only** — сервис подписан на events других сервисов.
   - **Both** — сервис как producer, так и consumer.
   - **Outbox-relay** — генерируется отдельно через `ucp-pg-runtime-design` (`outbox` сценарий); этот скилл — сама публикация и сами listener'ы.

3. **Уточни параметры:**
   - **Имя events** — past tense (`OrderConfirmed`, `PaymentFailed`, `UserRegistered`). Версионированный `eventType`: `order.confirmed.v1`.
   - **Topic name** — `<service>.<aggregate>.<event-name>` (`order-service.order.confirmed`) или single topic с разными eventType в payload.
   - **Partition key** — обычно aggregate id (Long → toString). Должен сохранять ordering для одного агрегата.
   - **Money / critical** — двойная защита: outbox + idempotent consumer + Idempotency-Key для downstream HTTP. Failure rate threshold ниже.
   - **Retry strategy** — стандарт: 3-4 attempts с exponential backoff (1s, 10s, 100s, 1000s) → DLQ.
   - **Idempotency** — нужен ли `processed_event` таблица для consumer? **Да для критичных, опционально для analytics.**

4. **Произведи код.** Lombok-defaults обязательны (`JS-6.1`–`JS-6.7`). Не цитируй коды правил в комментариях кода (`JS-7.3`).

   ### 4.1. KafkaSettings (`@ConfigurationProperties`)

   ```java
   // bootstrap/src/main/java/<pkg>/config/KafkaSettings.java
   @ConfigurationProperties("app.kafka")
   @Validated
   public record KafkaSettings(
       @NotNull TopicSettings topics,
       @NotNull RetrySettings retry
   ) {
       public record TopicSettings(
           @NotBlank String orderConfirmed,
           @NotBlank String paymentFailed,
           @NotBlank String orderConfirmedRetry1m,
           @NotBlank String orderConfirmedDlq
       ) {}

       public record RetrySettings(
           @Min(1) @Max(10) int maxAttempts,
           @NotNull Duration baseBackoff,
           @Min(2) double multiplier
       ) {}
   }
   ```

   `application.yml`:
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
       missing-topics-fatal: true

   app.kafka:
     topics:
       order-confirmed: order-service.order.confirmed
       payment-failed: payment-service.payment.failed
       order-confirmed-retry-1m: order-service.order.confirmed.retry-1m
       order-confirmed-dlq: order-service.order.confirmed.dlq
     retry:
       max-attempts: 4
       base-backoff: 60s
       multiplier: 10.0
   ```

   ### 4.2. Event-record

   ```java
   // core/<bc>/domain/event/OrderConfirmedEvent.java
   public record OrderConfirmedEvent(
       UUID eventId,
       String eventType,
       OffsetDateTime occurredAt,
       String aggregateType,
       Long aggregateId,
       Long customerId,
       Money totalAmount
   ) {
       public static final String TYPE = "order.confirmed.v1";

       public static OrderConfirmedEvent from(Order order) {
           return new OrderConfirmedEvent(
               UuidV7.generate(),
               TYPE,
               order.getConfirmedAt(),
               "Order",
               order.getId(),
               order.getCustomerId(),
               order.getTotalAmount()
           );
       }
   }
   ```

   ### 4.3. Producer (через outbox — рекомендуется)

   В handler — запись в outbox в той же транзакции:
   ```java
   @Component
   @RequiredArgsConstructor
   @Transactional
   public class ConfirmOrderCommandHandler implements UseCaseHandler<ConfirmOrderCommand, Order> {

       private final OrderRepository orderRepository;
       private final OutboxRepository outboxRepository;
       private final JooqJsonbHelper jsonb;

       @Override
       public Order handle(ConfirmOrderCommand cmd) {
           var order = orderRepository.findById(cmd.orderId(), SelectMode.FOR_UPDATE).orElseThrow();
           order.confirm();
           orderRepository.save(order);

           outboxRepository.append(OutboxEvent.builder()
               .aggregateType("Order")
               .aggregateId(order.getId())
               .eventType(OrderConfirmedEvent.TYPE)
               .payload(jsonb.serialize(OrderConfirmedEvent.from(order)))
               .build());

           return order;
       }
   }
   ```

   Outbox-relay (если ещё нет в проекте) — генерируется через `ucp-pg-runtime-design` отдельным запуском. Здесь вызов команды для пользователя в заметках.

   ### 4.4. Producer (direct — только для технических событий)

   Если событие **не** связано с DB-транзакцией (audit-log в дополнение к таблице, метрика):
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class AuditEventPublisher {

       private final KafkaTemplate<String, Object> kafkaTemplate;
       private final KafkaSettings settings;

       public void publishAdminAction(AdminActionEvent event) {
           kafkaTemplate.send(settings.topics().adminActions(), event.actorId().toString(), event)
               .whenComplete((result, ex) -> {
                   if (ex != null) log.warn("Failed to publish admin event {}", event.eventId(), ex);
               });
       }
   }
   ```

   ### 4.5. Consumer с idempotent-dedup и retry topic

   DDL `processed_event`:
   ```yaml
   # migrations/db/changelog/v-1.x/<NNN>-create-processed-event.yaml
   - changeSet:
       id: <NNN>-create-processed-event
       changes:
         - createTable:
             tableName: processed_event
             columns:
               - column: { name: event_id, type: uuid,
                           constraints: { primaryKey: true, primaryKeyName: processed_event_pk } }
               - column: { name: consumer_group, type: text,
                           constraints: { nullable: false } }
               - column: { name: processed_at, type: timestamptz,
                           defaultValueComputed: now(),
                           constraints: { nullable: false } }
   ```

   Listener:
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class OrderConfirmedListener {

       private final ProcessedEventRepository processedRepo;
       private final UseCaseDispatcher dispatcher;
       private static final String GROUP = "billing-service-order-confirmed";

       @RetryableTopic(
           attempts = "4",
           backoff = @Backoff(delay = 60_000, multiplier = 10),
           autoCreateTopics = "false",
           include = {RetryableException.class},
           exclude = {NonRetryableException.class}
       )
       @KafkaListener(
           topics = "${app.kafka.topics.order-confirmed}",
           groupId = GROUP,
           concurrency = "3"
       )
       @Transactional
       public void handle(OrderConfirmedEvent event, Acknowledgment ack) {
           if (processedRepo.exists(event.eventId(), GROUP)) {
               log.debug("Duplicate event {}, skipping", event.eventId());
               ack.acknowledge();
               return;
           }

           dispatcher.dispatch(new ChargeForOrderCommand(event.aggregateId(), event.totalAmount()));

           processedRepo.markProcessed(event.eventId(), GROUP);
           ack.acknowledge();
       }

       @DltHandler
       public void handleDlt(OrderConfirmedEvent event,
                              @Header(KafkaHeaders.EXCEPTION_FQCN) String exceptionType,
                              @Header(KafkaHeaders.EXCEPTION_MESSAGE) String message) {
           log.error("Event {} sent to DLQ. Type: {}, Reason: {}",
               event.eventId(), exceptionType, message);
           // alert через monitoring; manual replay через admin API
       }
   }
   ```

   ### 4.6. Custom exceptions для retry/no-retry разделения

   ```java
   // core/<bc>/exception/RetryableException.java
   public abstract class RetryableException extends RuntimeException {
       protected RetryableException(String msg, Throwable cause) { super(msg, cause); }
   }

   public class TransientServiceException extends RetryableException { ... }   // 5xx, IOException

   public abstract class NonRetryableException extends RuntimeException {
       protected NonRetryableException(String msg) { super(msg); }
   }

   public class ValidationException extends NonRetryableException { ... }      // 4xx, contract issues
   ```

5. **Самопроверка перед выдачей** (`R-KFK-*`):
   - Producer: `enable.idempotence: true`, `acks: all`, partition key явный, нет direct send из `@Transactional` с DB.
   - Consumer: `groupId` уникальный per-purpose, manual ack, `auto-offset-reset: earliest`, listener idempotent через `processed_event`.
   - Outbox: для domain events — через outbox-relay, не direct send.
   - Retry topic: `@RetryableTopic` с явным max-attempts и backoff; `@DltHandler` для DLQ.
   - Event-design: имя в past tense, `eventId` UUID v7, версионированный `eventType`, без PII в payload.
   - Config: `@Validated KafkaSettings`, `trusted.packages` explicit (не `*`), `missing-topics-fatal: true`.

6. **Структура вывода:**
   1. **Решения** — сценарий (producer/consumer/both), outbox vs direct, retry-стратегия, idempotency.
   2. **Дерево новых файлов** — config, settings, event-records, listener, processed_event DDL.
   3. **Каждый файл — отдельный code block** с путём.
   4. **Patch для существующих файлов** — `application.yml`, `bootstrap/build.gradle.kts` (`spring-kafka`).
   5. **Заметки по реализации:**
      - Команды: `./gradlew compileJava`, `docker-compose up kafka`, `./gradlew test --tests *KafkaListenerTest`.
      - **TODO для пользователя:** создать topics через `KafkaAdmin` или infra-скрипт (`order-confirmed`, `order-confirmed.retry-1m`, `order-confirmed.dlq`); настроить ACL'ы для service-account; alerts на `kafka_consumer_lag` для критичных топиков.
      - Если outbox ещё нет — отдельно запустить `ucp-pg-runtime-design` с параметром `outbox`.
   6. **Финальный шаг:** «после генерации запусти `ucp-kafka-review` для верификации; добавь интеграционный тест с `Testcontainers` Kafka».

## Что НЕ делает

- Outbox-relay реализация (DDL `outbox_event` + scheduler-publisher) — `ucp-pg-runtime-design` (`outbox` сценарий).
- Domain events как класс / Aggregate-методы для emit — `ucp-ddd-tactical-design` (`R-EVT-*`).
- HTTP к downstream-системам из listener (CB-обёртка) — `ucp-integration-design`.
- Schema Registry / Avro setup — отдельная инфра, в этом скилле не покрывается.
- Kafka cluster admin / topic provisioning — DevOps/SRE.

После — обязательно `ucp-kafka-review` для верификации.

$ARGUMENTS
