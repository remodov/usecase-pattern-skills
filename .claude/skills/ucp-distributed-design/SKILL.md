---
name: ucp-distributed-design
description: Сгенерировать распределённый паттерн под Distributed Patterns Style Guide — saga (orchestration или choreography с saga_<name> таблицей в БД, sagaId сквозной, каждый шаг — отдельная command + compensation), idempotency-инфраструктура (processed_event таблица для Kafka dedup, idempotency_record таблица для HTTP money-команд), inbox pattern (опционально), compensation-команды для каждого шага (semantic state-change не DELETE, идемпотентны), eventual consistency декларация в OpenAPI. Решает: orchestration vs choreography (по числу шагов и branching), inbox vs только processed_event (по criticality), TTL для idempotency-records, что делать при failed compensation (DLQ + alert). Применяется при добавлении cross-service flow или замене 2PC на saga. Триггеры: «нужна сага для X», «cross-service сценарий Y», «idempotency для money-API».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Distributed Patterns — проектирование

Ты генерируешь распределённый паттерн (saga, idempotency-инфра, compensation) по Distributed Patterns Style Guide.

## Инструкции

1. **Прочитай** `.claude/docs/distributed-patterns-style-guide.md` (`R-DIST-*`). Опционально — `kafka-style-guide.md` (`R-KFK-OBX-*`/`R-KFK-IDEM-*`), `auth-patterns-style-guide.md` (`AUTH-19`).

2. **Уточни параметры:**
   - **Тип паттерна**: saga / только idempotency-обвязка / inbox.
   - **Saga complexity**: 2-3 шага → choreography; 4+ или branching → orchestration.
   - **Money / critical**: двойная защита (eventId + Idempotency-Key); более строгий TTL и monitoring.
   - **Сервисы-участники**: список в правильном порядке; каждый имеет compensation-команду.
   - **Failure-mode**: что делать при failed compensation? DLQ + manual review (стандарт).

3. **Произведи код.**

   ### 3.1. Saga orchestration (4+ steps, branching)

   **Saga state DDL:**
   ```yaml
   - changeSet:
       id: <NNN>-create-saga-<name>
       changes:
         - createTable:
             tableName: saga_order_creation
             columns:
               - column: { name: saga_id, type: uuid, constraints: { primaryKey: true } }
               - column: { name: status, type: text, constraints: { nullable: false } }
               - column: { name: current_step, type: text, constraints: { nullable: false } }
               - column: { name: payload, type: jsonb, constraints: { nullable: false } }
               - column: { name: started_at, type: timestamptz,
                           defaultValueComputed: now(),
                           constraints: { nullable: false } }
               - column: { name: completed_at, type: timestamptz }
               - column: { name: last_error, type: text }
         - addCheckConstraint:
             constraintName: saga_order_creation_status_chk
             tableName: saga_order_creation
             constraintBody: "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED', 'COMPENSATING')"
         - createIndex:
             tableName: saga_order_creation
             indexName: saga_order_creation_in_progress_idx
             columns:
               - column: { name: started_at }
             where: "status IN ('IN_PROGRESS', 'COMPENSATING')"
   ```

   **Orchestrator:**
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class OrderCreationSaga {

       private final SagaStateRepository sagaRepo;
       private final OrderPort orderPort;
       private final PaymentPort paymentPort;
       private final InventoryPort inventoryPort;

       @Transactional
       public Long execute(OrderCreationRequest request) {
           var sagaId = UuidV7.generate();
           var state = SagaState.start(sagaId, "OrderCreation", request);
           sagaRepo.save(state);

           try {
               state = stepCreateOrder(state, request);
               state = stepChargePayment(state, request);
               state = stepReserveInventory(state, request);
               state = stepConfirmOrder(state);
               sagaRepo.markCompleted(sagaId);
               return state.payload().get("orderId").asLong();
           } catch (SagaStepException e) {
               compensate(state, e);
               throw new SagaFailedException(sagaId, e);
           }
       }

       private SagaState stepCreateOrder(SagaState state, OrderCreationRequest request) {
           var orderId = orderPort.create(state.sagaId(), request);
           var updated = state.withStep("createOrder", Map.of("orderId", orderId));
           sagaRepo.save(updated);
           return updated;
       }

       // ... остальные шаги аналогично

       private void compensate(SagaState state, SagaStepException failed) {
           sagaRepo.markCompensating(state.sagaId(), failed.getMessage());
           try {
               // Compensate в обратном порядке. Каждое compensation идемпотентно.
               if (state.completed("chargePayment")) paymentPort.refund(state.sagaId(), state.payload().get("paymentId"));
               if (state.completed("createOrder")) orderPort.cancel(state.sagaId(), state.payload().get("orderId"));
               sagaRepo.markFailed(state.sagaId(), failed.getMessage());
           } catch (Exception compensationFailed) {
               log.error("Compensation failed for saga {}", state.sagaId(), compensationFailed);
               sagaRepo.markFailedWithCompensationError(state.sagaId(), compensationFailed);
               // alert через monitoring; manual review требуется
           }
       }
   }
   ```

   **Recovery scheduler** (для in-flight sagas если orchestrator упал):
   ```java
   @Component
   @RequiredArgsConstructor
   public class SagaRecoveryScheduler {

       private final SagaStateRepository sagaRepo;
       private final OrderCreationSaga saga;

       @Scheduled(fixedDelay = 60_000)
       public void recoverInProgress() {
           var stale = sagaRepo.findInProgressOlderThan(Duration.ofMinutes(10));
           for (var state : stale) {
               // resume или compensate в зависимости от current_step
               saga.resume(state);
           }
       }
   }
   ```

   ### 3.2. Saga choreography (2-3 шага без branching)

   Не нужен orchestrator. Каждый сервис подписан на event'ы и реагирует.

   ```
   Order-service:
     command CreateOrder → save Order + outbox event order.created
   
   Payment-service:
     KafkaListener on order.created → command ChargePayment
       → save Payment + outbox event payment.charged ИЛИ payment.failed
   
   Order-service:
     KafkaListener on payment.charged → command ConfirmOrder (Order CONFIRMED)
     KafkaListener on payment.failed → command CancelOrder (compensation)
   ```

   Реализация — обычные `@KafkaListener` (см. `R-KFK-CONS-*`) с `processed_event` dedup. Без отдельного saga-orchestrator.

   ### 3.3. Idempotency-инфраструктура (без саги)

   **Для Kafka consumer** (`processed_event` таблица — генерируется через `ucp-kafka-design`).

   **Для HTTP money-команд** (`idempotency_record`):
   ```yaml
   - changeSet:
       id: <NNN>-create-idempotency-record
       changes:
         - createTable:
             tableName: idempotency_record
             columns:
               - column: { name: idempotency_key, type: text, constraints: { primaryKey: true } }
               - column: { name: command_hash, type: text, constraints: { nullable: false } }
               - column: { name: response, type: jsonb, constraints: { nullable: false } }
               - column: { name: created_at, type: timestamptz,
                           defaultValueComputed: now(),
                           constraints: { nullable: false } }
         - createIndex:
             tableName: idempotency_record
             indexName: idempotency_record_created_at_idx
             columns:
               - column: { name: created_at }
   ```

   **IdempotencyInterceptor** (Spring `HandlerInterceptor`):
   ```java
   @Component
   @RequiredArgsConstructor
   public class IdempotencyInterceptor implements HandlerInterceptor {

       private final IdempotencyRepository repo;
       private final ObjectMapper mapper;

       @Override
       public boolean preHandle(HttpServletRequest req, HttpServletResponse resp, Object handler) {
           var key = req.getHeader("Idempotency-Key");
           if (key == null) return true;   // не money-команда

           var existing = repo.findByKey(key);
           if (existing.isPresent()) {
               var commandHash = computeHash(req);
               if (!existing.get().commandHash().equals(commandHash)) {
                   resp.sendError(409, "Idempotency-Key reused with different command");
                   return false;
               }
               // вернуть сохранённый response
               resp.setStatus(200);
               resp.setContentType("application/json");
               resp.getWriter().write(mapper.writeValueAsString(existing.get().response()));
               return false;
           }
           // request будет обработан, ResponseInterceptor сохранит
           return true;
       }
   }
   ```

   ### 3.4. Compensation-команды

   Для каждой команды в саге — semantic compensation:
   ```java
   public record RefundPaymentCommand(UUID sagaId, Long paymentId, String reason)
       implements UseCaseCommand<UseCaseEmptyResult> {}

   @Component
   @RequiredArgsConstructor
   @Transactional
   public class RefundPaymentCommandHandler implements UseCaseHandler<RefundPaymentCommand, UseCaseEmptyResult> {

       private final PaymentRepository paymentRepository;
       private final ProcessedEventRepository processedRepo;

       @Override
       public UseCaseEmptyResult handle(RefundPaymentCommand cmd) {
           // Idempotent: проверяем не обрабатывали ли уже эту compensation
           var dedupKey = "refund:" + cmd.sagaId() + ":" + cmd.paymentId();
           if (processedRepo.exists(dedupKey)) return UseCaseEmptyResult.INSTANCE;

           var payment = paymentRepository.findById(cmd.paymentId(), SelectMode.FOR_UPDATE)
               .orElseThrow(() -> new PaymentNotFoundException(cmd.paymentId()));
           payment.refund(cmd.reason());           // semantic state-change, не DELETE
           paymentRepository.save(payment);

           processedRepo.markProcessed(dedupKey);
           return UseCaseEmptyResult.INSTANCE;
       }
   }
   ```

   ### 3.5. OpenAPI patch для money-endpoint

   ```yaml
   /api/v1/orders:
     post:
       summary: 'Создать заказ'
       parameters:
         - name: Idempotency-Key
           in: header
           required: true
           schema:
             type: string
             format: uuid
           description: |
             Уникальный ключ операции для идемпотентности.
             Повторный POST с тем же ключом возвращает прежний ответ.
             Один ключ должен использоваться один раз на бизнес-операцию (не генерировать новый при retry).
   ```

4. **Самопроверка перед выдачей** (`R-DIST-*`):
   - Saga state в `saga_<name>` таблице (не in-memory).
   - Каждая command в саге имеет compensation-method (semantic, не DELETE).
   - Compensation идемпотентна (dedup через `processed_event` или `(sagaId, step)` ключ).
   - Idempotency-инфра для money: `processed_event` (Kafka) + `idempotency_record` (HTTP) одновременно.
   - Recovery-scheduler для in-flight sagas (если orchestrator).
   - DLQ + alert при failed compensation.
   - OpenAPI описание eventual consistency для read-endpoint'ов.
   - **Никакого** JTA / XADataSource / ChainedTransactionManager.

5. **Структура вывода:**
   1. **Решения** — orchestration vs choreography, money/critical (двойная защита), TTL для dedup-tables.
   2. **Дерево новых файлов** — DDL для saga_/processed_event/idempotency_record + Saga orchestrator + Recovery scheduler + Compensation handlers.
   3. **Каждый файл — отдельный code block** с путём.
   4. **Patch для existing файлов** — `application.yml` (Kafka topic configs если applicable), OpenAPI YAML с Idempotency-Key header.
   5. **Заметки по реализации:**
      - Команды: `./gradlew compileJava`, `liquibaseUpdate`.
      - **TODO для пользователя:** alerts на размер DLQ; alerts на saga в state COMPENSATING > N; дашборд in-flight sagas; runbook для manual recovery failed compensation.
      - Если orchestration: dependency on `ucp-pg-runtime-design` (для recovery scheduler с SKIP LOCKED).
   6. **Финальный шаг:** «после генерации запусти `ucp-distributed-review` для верификации».

## Что НЕ делает

- Domain methods (`payment.refund()`) — `ucp-ddd-tactical-design`.
- Outbox-relay implementation — `ucp-pg-runtime-design` (`outbox` сценарий) / `ucp-kafka-design`.
- Kafka producer/consumer config — `ucp-kafka-design`.
- CQRS read-model sync — `ucp-cqrs-design`.
- Spring Security для admin saga-control endpoints — `ucp-auth-design`.

После — обязательно `ucp-distributed-review` для верификации.

$ARGUMENTS
