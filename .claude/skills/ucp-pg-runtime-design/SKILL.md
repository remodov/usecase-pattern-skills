---
name: ucp-pg-runtime-design
description: Сгенерировать runtime-инфраструктуру для типовых PG-сценариев под pg-runtime-style-guide — outbox-relay (publishing pattern с FOR UPDATE SKIP LOCKED), task-queue (durable retry для адаптеров), advisory-lock для singleton scheduled-job, optimistic-lock через version-колонку с retry на CannotAcquireLockException. Создаёт Liquibase-таблицу, Java-классы scheduler + handler, конфиг lock_timeout. Применяется когда нужен outbox для doмен-событий, task-queue для resilience-fallback, distributed scheduling. Триггеры: «нужен outbox-relay», «scheduler с SKIP LOCKED», «task-queue для платежей», «advisory lock для singleton job», «optimistic locking для агрегата X».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# PostgreSQL Runtime — проектирование

Ты генерируешь runtime-инфраструктуру для типовых PG-сценариев по `pg-runtime-style-guide.md` (`PG-W-*`, `PG-V-*`, `PG-L-*`, `PG-CP-*`, `PG-IS-*`). Это узкий скилл — покрывает 4 паттерна:

1. **Outbox-relay** — durable publishing доменных событий.
2. **Task-queue** — durable retry для resilience-fallback (см. `R-RES-FB-1`).
3. **Advisory lock** — singleton scheduled-job в кластере (`PG-L-060`).
4. **Optimistic locking** — через `version`-колонку с Spring `@Retryable` (`PG-L-051`, `PG-L-072`).

Каждый сценарий = отдельный invoke с одним из этих параметров.

## Инструкции

1. **Прочитай:**
   - `.claude/docs/pg-runtime-style-guide.md` — главный (правила `PG-W-*`, `PG-L-*`).
   - `.claude/docs/pg-types-style-guide.md` — типы под `PG-T-*` (для DDL outbox-таблицы).
   - `.claude/docs/jooq-rules.md` — `R-JOOQ-LCK-1`, `R-JOOQ-MS-3` (для запросов SKIP LOCKED).

2. **Уточни сценарий.** Один из:
   - `outbox` — outbox-relay для доменных событий.
   - `task-queue` — durable retry для outbound (платежи, фискализация).
   - `advisory-lock` — singleton scheduled-job.
   - `optimistic-lock` — для конкретного агрегата.

3. **Сценарий 1 — Outbox-relay**

   ### 3.1. DDL (Liquibase changeset)

   ```yaml
   # migrations/db/changelog/v-1.x/<NNN>-create-outbox-event.yaml
   - changeSet:
       id: <NNN>-create-outbox-event
       changes:
         - createTable:
             tableName: outbox_event
             columns:
               - column: { name: id, type: bigint, autoIncrement: true,
                           constraints: { primaryKey: true, primaryKeyName: outbox_event_pk } }
               - column: { name: aggregate_type, type: text, constraints: { nullable: false } }
               - column: { name: aggregate_id, type: bigint, constraints: { nullable: false } }
               - column: { name: event_type, type: text, constraints: { nullable: false } }
               - column: { name: payload, type: jsonb, constraints: { nullable: false } }
               - column: { name: created_at, type: timestamptz,
                           defaultValueComputed: now(), constraints: { nullable: false } }
               - column: { name: published_at, type: timestamptz }
               - column: { name: attempts, type: int, defaultValue: '0' }
               - column: { name: last_error, type: text }
         - createIndex:
             tableName: outbox_event
             indexName: outbox_event_unpublished_idx
             columns:
               - column: { name: created_at }
             where: published_at IS NULL
   ```

   ### 3.2. Java — Outbox-publisher
   ```java
   // adapter/out/outbox/OutboxPublisher.java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class OutboxPublisher {

       private final DSLContext dslContext;
       private final OutboxEventDispatcher dispatcher;  // знает, как послать в Kafka/RabbitMQ

       @Scheduled(fixedDelay = 1000)
       @Transactional
       public void publishBatch() {
           var unpublished = dslContext
               .selectFrom(OUTBOX_EVENT)
               .where(OUTBOX_EVENT.PUBLISHED_AT.isNull())
               .orderBy(OUTBOX_EVENT.CREATED_AT)
               .limit(50)
               .forUpdate()
               .skipLocked()                       // PG-L-021: при многих инстансах не дублирует
               .fetchInto(OutboxEventPojo.class);

           for (var event : unpublished) {
               try {
                   dispatcher.publish(event);
                   dslContext.update(OUTBOX_EVENT)
                       .set(OUTBOX_EVENT.PUBLISHED_AT, OffsetDateTime.now())
                       .where(OUTBOX_EVENT.ID.eq(event.getId()))
                       .execute();
               } catch (Exception e) {
                   dslContext.update(OUTBOX_EVENT)
                       .set(OUTBOX_EVENT.ATTEMPTS, OUTBOX_EVENT.ATTEMPTS.plus(1))
                       .set(OUTBOX_EVENT.LAST_ERROR, e.getMessage())
                       .where(OUTBOX_EVENT.ID.eq(event.getId()))
                       .execute();
                   log.warn("Failed to publish outbox event id={}", event.getId(), e);
               }
           }
       }
   }
   ```

   ### 3.3. Запись в outbox из Handler
   ```java
   // В Command Handler (ucp-pattern-design):
   @Transactional
   public Order handle(ConfirmOrderCommand cmd) {
       var order = orderRepository.findById(cmd.orderId(), SelectMode.FOR_UPDATE).orElseThrow();
       order.confirm();
       orderRepository.save(order);
       outboxRepository.append(new OrderConfirmedEvent(order.getId(), order.getStatus()));
       return order;
   }
   ```
   — событие пишется в outbox_event в той же транзакции, что и UPDATE order. **Атомарность:** либо обе записи коммитятся, либо обе откатываются.

4. **Сценарий 2 — Task-queue (durable retry для resilience)**

   ### 4.1. DDL
   ```yaml
   - changeSet:
       id: <NNN>-create-<x>-task
       changes:
         - createTable:
             tableName: <x>_task
             columns:
               - column: { name: id, type: bigint, autoIncrement: true, constraints: { primaryKey: true } }
               - column: { name: payload, type: jsonb, constraints: { nullable: false } }
               - column: { name: status, type: text, defaultValue: 'IN_PROGRESS' }   # CHECK in...
               - column: { name: retry_count, type: int, defaultValue: '0' }
               - column: { name: next_attempt_at, type: timestamptz,
                           defaultValueComputed: now(), constraints: { nullable: false } }
               - column: { name: max_retries, type: int, defaultValue: '5' }
               - column: { name: created_at, type: timestamptz,
                           defaultValueComputed: now(), constraints: { nullable: false } }
               - column: { name: completed_at, type: timestamptz }
               - column: { name: last_error, type: text }
         - addCheckConstraint:
             constraintName: <x>_task_status_chk
             tableName: <x>_task
             constraintBody: "status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')"
         - createIndex:
             tableName: <x>_task
             indexName: <x>_task_pending_idx
             columns:
               - column: { name: next_attempt_at }
             where: "status = 'IN_PROGRESS'"
   ```

   ### 4.2. Scheduler
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class <X>TaskProcessor {

       private final UseCaseDispatcher dispatcher;
       private final DSLContext dslContext;

       @Scheduled(fixedDelay = 5000)
       public void processBatch() {
           var taskIds = dslContext
               .select(<X>_TASK.ID)
               .from(<X>_TASK)
               .where(<X>_TASK.STATUS.eq("IN_PROGRESS")
                   .and(<X>_TASK.NEXT_ATTEMPT_AT.le(OffsetDateTime.now())))
               .orderBy(<X>_TASK.NEXT_ATTEMPT_AT)
               .limit(10)
               .forUpdate()
               .skipLocked()                       // PG-L-021
               .fetch(<X>_TASK.ID);

           for (var taskId : taskIds) {
               try {
                   dispatcher.dispatch(new Process<X>TaskCommand(taskId));
               } catch (Exception e) {
                   log.warn("Task {} failed, will retry", taskId, e);
               }
           }
       }
   }
   ```

   ### 4.3. Process<X>TaskCommandHandler — retry policy
   ```java
   @Component
   @RequiredArgsConstructor
   @Transactional
   public class Process<X>TaskCommandHandler implements UseCaseHandler<Process<X>TaskCommand, UseCaseEmptyResult> {

       private final <X>TaskRepository taskRepository;
       private final <X>Port externalPort;
       private final RetryPolicy retryPolicy;       // в config — max-retries, base-delay, multiplier

       @Override
       public UseCaseEmptyResult handle(Process<X>TaskCommand cmd) {
           var task = taskRepository.findById(cmd.taskId(), SelectMode.FOR_UPDATE).orElseThrow();
           try {
               externalPort.execute(task.getPayload());
               task.markCompleted();
           } catch (Exception e) {
               if (task.getRetryCount() >= task.getMaxRetries()) {
                   task.markFailed(e.getMessage());
               } else {
                   task.scheduleRetry(retryPolicy.nextAttempt(task.getRetryCount()), e.getMessage());
               }
           }
           taskRepository.save(task);
           return UseCaseEmptyResult.INSTANCE;
       }
   }
   ```

5. **Сценарий 3 — Advisory lock для singleton scheduled-job**

   ```java
   @Component
   @RequiredArgsConstructor
   public class DailyReportJob {

       private final DSLContext dslContext;
       private final ReportService reportService;
       private static final long LOCK_KEY = 0xDA17_RE_PORT_BIG_INT;  // фиксированный bigint

       @Scheduled(cron = "0 0 3 * * *")
       @Transactional
       public void run() {
           // PG-L-060: pg_try_advisory_xact_lock — отпускается в конце транзакции
           var locked = dslContext.fetchValue(
               "SELECT pg_try_advisory_xact_lock(?)", LOCK_KEY);
           if (!Boolean.TRUE.equals(locked)) {
               log.info("Daily report job locked by another instance, skipping");
               return;
           }
           reportService.generateDaily();
       }
   }
   ```

6. **Сценарий 4 — Optimistic locking**

   ### 6.1. DDL — добавить version-колонку (`PG-L-051`)
   ```yaml
   - changeSet:
       id: <NNN>-add-version-to-<table>
       changes:
         - addColumn:
             tableName: <table>
             columns:
               - column: { name: version, type: bigint, defaultValue: '0',
                           constraints: { nullable: false } }
   ```

   ### 6.2. UPDATE с проверкой версии в repository
   ```java
   public void save(<X> entity) {
       int updated = dslContext.update(<X>_TABLE)
           .set(<X>_TABLE.STATUS, entity.getStatus().toJooq())
           .set(<X>_TABLE.VERSION, entity.getVersion() + 1)   // increment
           .where(<X>_TABLE.ID.eq(entity.getId())
               .and(<X>_TABLE.VERSION.eq(entity.getVersion())))   // optimistic-check
           .execute();
       if (updated == 0) {
           throw new OptimisticLockException("Concurrent modification of <X> id=" + entity.getId());
       }
   }
   ```

   ### 6.3. Spring `@Retryable` (`PG-L-072`)
   ```java
   @Component
   public class <X>UpdateService {

       @Retryable(
           retryFor = OptimisticLockException.class,
           maxAttempts = 3,
           backoff = @Backoff(delay = 50, multiplier = 2.0)
       )
       public <X> updateWithRetry(<X>UpdateCommand cmd) {
           // ... load aggregate, mutate, save
       }
   }
   ```

7. **Самопроверка перед выдачей.** Пройди по правилам:
   - **Outbox**: `FOR UPDATE SKIP LOCKED` (`PG-L-020`/`PG-L-021`), partial-index по `published_at IS NULL`, scheduler внутри `@Transactional`.
   - **Task-queue**: тот же `SKIP LOCKED`, partial-index по `status = 'IN_PROGRESS'`, retry policy с exp backoff (`PG-L-051` для in-memory transient, task-queue для долгих), max-retries.
   - **Advisory lock**: `pg_try_advisory_xact_lock` (xact-вариант — отпускается на коммите), не `pg_advisory_lock` (session-вариант — может протечь).
   - **Optimistic**: `version`-колонка явно в схеме, UPDATE с проверкой `version`, increment в том же UPDATE, `@Retryable` на `OptimisticLockException` (1–3 попытки).
   - Все scheduler-методы с `forUpdate()` обёрнуты в `@Transactional` (`PG-L-041`, `R-JOOQ-LCK-3`).

8. **Структура вывода:**
   1. **Решения** — какой сценарий выбран, почему, какой retry-policy.
   2. **Дерево новых файлов** — DDL changeset, Java-классы.
   3. **Каждый файл — отдельный code block** с путём.
   4. **Patch для existing-файлов** — `application.yml` (retry-policy properties, scheduler enable), `bootstrap/build.gradle.kts` (если нужен `spring-boot-starter-aop` или `spring-retry`).
   5. **Заметки по реализации:**
      - Команды: `./gradlew liquibaseUpdate`, `./gradlew generateJooq`, `./gradlew test`.
      - **TODO:** определить exact LOCK_KEY (`pg_try_advisory_xact_lock`); настроить мониторинг очереди (alert если `outbox_event` где `published_at IS NULL` старше N минут).
   6. **Финальный шаг:** «после генерации — `ucp-pg-runtime-review` для проверки PG-W/PG-L правил, `ucp-jooq-review` для проверки запросов».

## Что НЕ делает

- Не генерирует Aggregate Root / события (`ucp-ddd-tactical-design`).
- Не создаёт UseCase / Handler с бизнес-логикой (`ucp-pattern-design`) — только scheduler-обёртку и пример process-handler.
- Не настраивает Kafka / RabbitMQ — outbox-relay генерирует только publishing pattern, dispatcher.publish() = stub.
- Не пишет Resilience4j-обвязку для адаптеров — это `ucp-resilience-design`.
- Не модифицирует схему extending tables — это `ucp-pg-migration-design` для breaking changes.

После — обязательно `ucp-pg-runtime-review` для верификации lock-safety, `ucp-jooq-review` для верификации запросов.

$ARGUMENTS
