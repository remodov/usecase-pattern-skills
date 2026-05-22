---
name: ucp-cqrs-design
description: Сгенерировать CQRS-разделение для агрегата под CQRS Style Guide — Command + CommandHandler пара (через UseCaseCommand маркер, FOR UPDATE load aggregate, outbox event), Query + QueryHandler пара (через UseCaseQuery маркер, ViewRepository, read-DTO record), <X>ViewRepository интерфейс в core/ и Jooq<X>ViewRepository в persistence/, read-model schema (Liquibase changeset для денормализованной таблицы), read-side consumer (KafkaListener с idempotent dedup), bootstrap-задача для rebuild read-model из write-side. Решает: какой вариант CQRS (lightweight маркеры на Уровне 2 или full split с отдельной read-таблицей на Уровне 3), синхронизация (sync через outbox+Kafka, не TX UPDATE), eventual consistency декларация в OpenAPI. Применяется при добавлении нового read-flow к existing-агрегату или при росте read-нагрузки. Триггеры: «нужна read-проекция для X», «CQRS для агрегата Y», «отдельная read-model».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# CQRS — проектирование

Ты генерируешь CQRS-разделение (write-side через aggregate, read-side через ViewRepository + read-model) по CQRS Style Guide.

## Инструкции

1. **Прочитай** `.claude/docs/cqrs-rules.md` (`R-CQRS-*`). Опционально — `usecase-pattern-rules.md` (`R-UC-*`), `jooq-rules.md` (`R-JOOQ-VIEW-*`), `kafka-rules.md` (`R-KFK-OBX-*`).

2. **Уточни параметры:**
   - **Aggregate** — имя (`Order`), есть ли write-handlers (`<X>CommandHandler`), есть ли уже `<X>Repository`.
   - **Read-сценарий** — что читаем (один объект, список с фильтрацией, summary, отчёт), форма read-DTO (`OrderSummary` vs `OrderListItem` vs `OrderReport`).
   - **Вариант CQRS** (CQRS — опция Уровня 2, а её глубина растёт с уровнем зрелости):
     - lightweight (Уровень 2) — read через тот же `<X>Repository.findById(id, NO_LOCK)`, read-DTO просто как маппинг.
     - split (Уровень 3) — отдельный `<X>ViewRepository` в core/ + `Jooq<X>ViewRepository` в persistence/, та же БД но разные методы.
     - event-driven (Уровень 3) — отдельная read-таблица `<x>_summary` (DDL changeset), sync через outbox+Kafka, read-side consumer.
   - **Read-нагрузка** — оценить read:write ratio. Если ≥ 10:1 — event-driven оправдан; иначе — split.
   - **RYW** (read-your-writes) — критично или нет? Если да — sticky session или sync-wait в command-handler.

3. **Произведи код** в зависимости от выбранного варианта CQRS.

   ### 3.1. lightweight (Уровень 2) — read через тот же repository

   ```java
   // core/<bc>/usecase/query/GetOrderSummaryQuery.java
   public record GetOrderSummaryQuery(Long orderId)
       implements UseCaseQuery<OrderSummary> {}

   // core/<bc>/dto/view/OrderSummary.java
   public record OrderSummary(
       Long orderId,
       OrderStatus status,
       Money totalAmount,
       int itemCount,
       OffsetDateTime createdAt
   ) {
       public static OrderSummary from(Order order) {
           return new OrderSummary(
               order.getId(), order.getStatus(),
               order.getTotalAmount(), order.getItems().size(),
               order.getCreatedAt()
           );
       }
   }

   // core/<bc>/usecase/query/GetOrderSummaryQueryHandler.java
   @Component
   @RequiredArgsConstructor
   @Transactional(readOnly = true)
   public class GetOrderSummaryQueryHandler
       implements UseCaseHandler<GetOrderSummaryQuery, OrderSummary> {

       private final OrderRepository repository;

       @Override
       public OrderSummary handle(GetOrderSummaryQuery query) {
           return repository.findById(query.orderId(), SelectMode.NO_LOCK)
               .map(OrderSummary::from)
               .orElseThrow(() -> new OrderNotFoundException(query.orderId()));
       }

       @Override
       public Class<GetOrderSummaryQuery> useCaseType() {
           return GetOrderSummaryQuery.class;
       }
   }
   ```

   ### 3.2. split (Уровень 3) — отдельный ViewRepository

   В дополнение к варианту lightweight:

   ```java
   // core/<bc>/domain/repository/OrderViewRepository.java
   public interface OrderViewRepository {
       Optional<OrderSummary> findSummaryById(Long orderId);
       PaginationView<OrderSummary> findSummaries(OrderFilter filter, int page, int size);
   }
   ```

   `Jooq<X>ViewRepository` — генерируется через `ucp-jooq-design` (отдельный шаг).

   Query handler меняется на использование view-repository:
   ```java
   @Component
   @RequiredArgsConstructor
   @Transactional(readOnly = true)
   public class GetOrderSummaryQueryHandler
       implements UseCaseHandler<GetOrderSummaryQuery, OrderSummary> {

       private final OrderViewRepository viewRepository;     // отдельный, не основной

       @Override
       public OrderSummary handle(GetOrderSummaryQuery query) {
           return viewRepository.findSummaryById(query.orderId())
               .orElseThrow(() -> new OrderNotFoundException(query.orderId()));
       }
   }
   ```

   ### 3.3. event-driven (Уровень 3) — отдельная read-таблица + sync

   В дополнение к варианту split:

   #### 3.3.1. Read-model DDL (Liquibase)
   ```yaml
   - changeSet:
       id: <NNN>-create-order-summary
       changes:
         - createTable:
             tableName: order_summary
             columns:
               - column: { name: order_id, type: bigint,
                           constraints: { primaryKey: true, primaryKeyName: order_summary_pk } }
               - column: { name: status, type: text, constraints: { nullable: false } }
               - column: { name: total_amount, type: numeric(19, 2), constraints: { nullable: false } }
               - column: { name: customer_name, type: text }     # денормализовано
               - column: { name: item_count, type: int, constraints: { nullable: false } }
               - column: { name: created_at, type: timestamptz, constraints: { nullable: false } }
               - column: { name: updated_at, type: timestamptz, constraints: { nullable: false } }
               - column: { name: source_event_id, type: uuid }    # для idempotency
               - column: { name: version, type: bigint, defaultValue: '0' }   # optimistic
         - createIndex:
             tableName: order_summary
             indexName: order_summary_status_created_at_idx
             columns:
               - column: { name: status }
               - column: { name: created_at, descending: true }
   ```

   #### 3.3.2. Read-side consumer (subscribes to OrderConfirmedEvent etc.)
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class OrderSummaryProjector {

       private final OrderSummaryRepository projectionRepo;
       private final ProcessedEventRepository processedRepo;
       private static final String GROUP = "order-summary-projector";

       @KafkaListener(topics = "order-service.order.confirmed", groupId = GROUP)
       @Transactional
       public void onOrderConfirmed(OrderConfirmedEvent event, Acknowledgment ack) {
           if (processedRepo.exists(event.eventId(), GROUP)) {
               ack.acknowledge();
               return;
           }
           // UPSERT в order_summary
           projectionRepo.upsert(OrderSummaryProjection.from(event));
           processedRepo.markProcessed(event.eventId(), GROUP);
           ack.acknowledge();
       }
   }
   ```

   #### 3.3.3. Bootstrap-задача для rebuild
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class OrderSummaryRebuildJob {

       private final OrderRepository orderRepository;        // источник правды
       private final OrderSummaryRepository projectionRepo;

       /** Вызывается явно через admin-endpoint или при первом запуске. */
       public void rebuildAll() {
           log.info("Rebuilding order_summary projection from write-side");
           int batch = 1000;
           long lastId = 0;
           while (true) {
               var batchOrders = orderRepository.findAllAfterId(lastId, batch);
               if (batchOrders.isEmpty()) break;
               for (var order : batchOrders) {
                   projectionRepo.upsert(OrderSummaryProjection.from(order));
                   lastId = order.getId();
               }
           }
           log.info("Rebuild complete");
       }
   }
   ```

   #### 3.3.4. OpenAPI patch — eventual consistency declaration
   ```yaml
   /api/v1/orders/{id}/summary:
     get:
       summary: 'Сводка по заказу (read-projection)'
       description: |
         Возвращает оптимизированную read-проекцию заказа.
         Данные обновляются eventual consistency через события — задержка
         от write до отображения в этой проекции обычно < 1 секунды.
         Для immediate consistency используйте GET /api/v1/orders/{id}.
   ```

4. **Самопроверка перед выдачей** (`R-CQRS-*`):
   - Command — `record implements UseCaseCommand<R>`.
   - Query — `record implements UseCaseQuery<R>`.
   - QueryHandler — `@Transactional(readOnly = true)`.
   - Read-DTO — record, не агрегат.
   - event-driven: read-model DDL + consumer + bootstrap-задача все вместе (нельзя только одно).
   - Sync через outbox/Kafka, не sync UPDATE в TX.
   - Idempotent consumer (`processed_event`).
   - OpenAPI description упоминает eventual consistency.

5. **Структура вывода:**
   1. **Решения** — вариант CQRS (lightweight / split / event-driven), почему. Read-model location (та же БД / Redis / новая таблица).
   2. **Дерево новых файлов** — Query/Handler/DTO; ViewRepository (split); DDL + Consumer + RebuildJob (event-driven).
   3. **Каждый файл — отдельный code block** с путём.
   4. **Patch для existing файлов** — application.yml (Kafka topic configs если C+), OpenAPI YAML.
   5. **Заметки по реализации:**
      - Команды: `./gradlew compileJava`, `liquibaseUpdate` если C+.
      - **TODO для пользователя:** запустить `OrderSummaryRebuildJob` при первом deploy (admin endpoint или migration script); создать Kafka topic; настроить алерты на consumer lag.
      - Если split — сначала `ucp-jooq-design` для `Jooq<X>ViewRepository`.
      - Если event-driven — сначала `ucp-pg-schema-design` для `<x>_summary` DDL + `ucp-kafka-design` для consumer.
   6. **Финальный шаг:** «после генерации запусти `ucp-cqrs-review` для верификации».

## Что НЕ делает

- Доменные методы агрегата — `ucp-ddd-tactical-design`.
- jOOQ-имплементация ViewRepository — `ucp-jooq-design`.
- Liquibase changeset для read-таблицы — `ucp-pg-schema-design`.
- Outbox-relay инфраструктура — `ucp-pg-runtime-design` (`outbox` сценарий).
- Kafka producer/consumer config + processed_event DDL — `ucp-kafka-design`.

После — обязательно `ucp-cqrs-review` для верификации.

$ARGUMENTS
