# Distributed Patterns Style Guide

Свод правил применения распределённых паттернов (saga, eventual consistency, idempotency, distributed transactions, two-phase alternatives) в Java/Spring-сервисах команды UCP. Каждое правило идентифицируется кодом (`R-DIST-SAGA-1`, `R-DIST-IDEM-X1`) — скилл `ucp-distributed-review` цитирует эти коды в findings.

Гайд опирается на ранее покрытые темы: outbox через `R-KFK-OBX-*` и `PG-L-021`, idempotent consumer `R-KFK-IDEM-*`, retry topics `R-KFK-RTRY-*`, CQRS sync `R-CQRS-SYNC-*`, AUTH-19 (Idempotency-Key для money). Этот гайд **связывает** их в единый набор правил для cross-service flows.

Не покрывает: Service Mesh (Istio routing — отдельная тема), CRDT data structures (rare для прикладного бэкенда), specific consensus algorithms (Raft / Paxos — это инфра-уровень).

Связанные стандарты:
- `R-KFK-OBX-*` / `R-KFK-IDEM-*` (Kafka) — outbox publishing + idempotent consumer.
- `R-CQRS-SYNC-*` — eventual consistency через события.
- `AUTH-19` — Idempotency-Key для money.
- `R-RES-*` — CB/Bulkhead/Retry для outbound.
- `PG-L-051` (PG runtime) — optimistic locking через version.
- `PG-L-060` — advisory locks.

---

## Содержание

1. [Когда нужны распределённые паттерны — `R-DIST-WHEN-*`](#1-когда-нужны-распределённые-паттерны)
2. [Saga — оркестрация vs хореография — `R-DIST-SAGA-*`](#2-saga--оркестрация-vs-хореография)
3. [Idempotency — `R-DIST-IDEM-*`](#3-idempotency)
4. [Eventual consistency — `R-DIST-EC-*`](#4-eventual-consistency)
5. [Outbox + Inbox — `R-DIST-OBX-*`](#5-outbox--inbox)
6. [Compensation — `R-DIST-COMP-*`](#6-compensation)
7. [Distributed transactions — что НЕ делать — `R-DIST-TX-*`](#7-distributed-transactions--что-не-делать)
8. [Антипаттерны — сводка `R-DIST-*-X*`](#8-антипаттерны)

---

## 1. Когда нужны распределённые паттерны

### 1.1 Обязательно

- **R-DIST-WHEN-1.** Распределённые паттерны нужны когда **бизнес-операция охватывает 2+ микросервиса** и нельзя завершить её одной локальной транзакцией:
  - «Создать заказ» = order-service + payment-service + inventory-service.
  - «Перевод между счетами разных банков» = bank-A + bank-B (через clearing).
  - «Отправить уведомление при изменении статуса» = order-service → notification-service.

- **R-DIST-WHEN-2.** Если операция **в одном сервисе и одном PG** — не нужны распределённые паттерны. Используй обычный `@Transactional` (`R-JOOQ-TX-1`) и атомарность БД.

- **R-DIST-WHEN-3.** Перед введением распределённого паттерна — **проверь альтернативы:**
  - **Объединение сервисов** — если два сервиса всегда меняются вместе (тесная связность), возможно это один bounded context.
  - **Modular monolith** — несколько BC в одном процессе, но логически разделённых. Локальные транзакции работают, distributed-сложность не нужна.
  - **Eventual consistency без саги** — если нет необходимости в rollback'ах; просто write + событие + read-side обновление.

### 1.2 Запрещено

- **R-DIST-WHEN-X1.** **Распределённые паттерны для одного сервиса.** Saga для двух операций в одной БД = self-orchestrated сложность.

- **R-DIST-WHEN-X2.** **Микросервисы из амбиций.** Распределение всегда дорогое: увеличивает latency, усложняет debugging, требует distributed tracing, добавляет failure modes. Если бизнес не требует — лучше modular monolith.

---

## 2. Saga — оркестрация vs хореография

Saga — паттерн для управления long-running cross-service business transaction через серию локальных транзакций + compensation.

### 2.1 Обязательно

- **R-DIST-SAGA-1.** Saga применяется когда:
  - Операция охватывает 2+ сервиса.
  - Каждый шаг должен быть transactional локально.
  - Нужна возможность compensation (rollback) при сбое промежуточного шага.

- **R-DIST-SAGA-2.** **Orchestration** (центральный координатор) — рекомендуется для **complex sagas** с 4+ шагов или sagas с branching.
  - Orchestrator (`OrderSagaOrchestrator`) знает все шаги и условия.
  - Каждый шаг — отдельная команда сервису.
  - При failure — orchestrator запускает compensation в обратном порядке.

  ```java
  @Component
  @RequiredArgsConstructor
  public class OrderSagaOrchestrator {

      public void run(OrderRequest request) {
          var sagaId = UUID.randomUUID();
          try {
              var orderId = orderService.create(sagaId, request);
              var paymentId = paymentService.charge(sagaId, orderId, request.amount());
              try {
                  inventoryService.reserve(sagaId, orderId, request.items());
                  orderService.confirm(sagaId, orderId);
              } catch (Exception e) {
                  paymentService.refund(sagaId, paymentId);   // compensation
                  orderService.cancel(sagaId, orderId);
                  throw e;
              }
          } catch (Exception e) {
              log.error("Saga {} failed", sagaId, e);
              throw new SagaFailedException(sagaId, e);
          }
      }
  }
  ```

- **R-DIST-SAGA-3.** **Choreography** (события без координатора) — для **simple sagas** 2-3 шага без branching.
  - Каждый сервис подписан на события других и реагирует.
  - При failure — сервис публикует compensation-event.
  - Меньше центральной сложности, но логику саги тяжелее проследить.

  ```
  order.created → payment-service charges → payment.charged → order-service confirms
                                          ↘ payment.failed → order-service cancels
  ```

- **R-DIST-SAGA-4.** **Saga state** хранится в БД (`saga_<name>` таблица):
  ```sql
  CREATE TABLE saga_order_creation (
      saga_id uuid PRIMARY KEY,
      status text NOT NULL,                    -- IN_PROGRESS, COMPLETED, FAILED, COMPENSATING
      current_step text NOT NULL,
      payload jsonb NOT NULL,
      started_at timestamptz NOT NULL,
      completed_at timestamptz,
      last_error text
  );
  ```
  Это даёт видимость («какие saga в процессе»), recovery (если orchestrator упал), audit.

- **R-DIST-SAGA-5.** **Saga ID в каждом сообщении** — сквозной ID для трассировки, связывает все шаги.

### 2.2 Запрещено

- **R-DIST-SAGA-X1.** **Distributed transaction (2PC, XA)** через JTA вместо saga. JTA не работает для большинства не-XA брокеров (Kafka), не масштабируется, добавляет single point of failure.

- **R-DIST-SAGA-X2.** **Saga без compensation logic.** Если шаг 3 упал, а шаги 1-2 уже committed — без compensation у нас «полусделанная» транзакция в проде.

- **R-DIST-SAGA-X3.** **Saga state только in-memory.** При рестарте orchestrator теряется состояние всех in-flight sagas → процессы зависают.

- **R-DIST-SAGA-X4.** **Saga смешана с use case** в одном handler-е. Saga — отдельный orchestrator-компонент; use cases — отдельные локальные транзакции.

---

## 3. Idempotency

Распределённые системы — at-least-once (сообщения могут дублироваться). Каждый consumer обязан быть идемпотентным.

### 3.1 Обязательно

- **R-DIST-IDEM-1.** **Каждое cross-service сообщение** имеет уникальный ID:
  - Kafka events — `eventId UUID v7` (см. `R-KFK-EVT-2`).
  - HTTP money-команды — `Idempotency-Key` header (см. `AUTH-19`).
  - Saga steps — `sagaId + stepName` уникальный ключ.

- **R-DIST-IDEM-2.** **Receiver хранит processed-events** в БД (`processed_event` таблица, см. `R-KFK-IDEM-2`). Перед обработкой — проверка наличия. После — запись в той же транзакции.

- **R-DIST-IDEM-3.** Для **HTTP-команд** receiver хранит `(idempotency_key, response)` пару в БД:
  ```sql
  CREATE TABLE idempotency_record (
      idempotency_key text PRIMARY KEY,
      command_hash text NOT NULL,
      response jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
  );
  ```
  Повторный запрос с тем же ключом возвращает сохранённый response. Если `command_hash` отличается (тот же ключ, другая команда) — `409 Conflict`.

- **R-DIST-IDEM-4.** **Money-операции — двойная защита**: `Idempotency-Key` от клиента + внутренняя дедупликация по `(payment_provider_id, external_payment_id)` уникальный constraint.

- **R-DIST-IDEM-5.** **TTL для idempotency-records** — типично 24-72 часа. Дольше — таблица растёт; короче — реальный retry клиента (через час) не проходит дедупликацию.

### 3.2 Запрещено

- **R-DIST-IDEM-X1.** **Receiver без dedup** для money / critical-команд. «Обычно дублируется редко» = дважды списанные деньги в инциденте.

- **R-DIST-IDEM-X2.** **Полагаться на receiver-side только**. Sender (producer) тоже должен иметь exactly-once гарантии (Kafka `enable.idempotence: true`, см. `R-KFK-PROD-1`).

- **R-DIST-IDEM-X3.** **`Idempotency-Key = UUID каждый раз`**. Клиент должен генерировать ключ **один раз** на бизнес-операцию, retry'ить с тем же ключом. Иначе дедупликация бессмысленна.

---

## 4. Eventual consistency

В распределённой системе данные между сервисами обновляются с задержкой. Это норма, но требует явного контракта.

### 4.1 Обязательно

- **R-DIST-EC-1.** **Декларация в API** — для endpoint, который читает eventual-consistent данные, в OpenAPI описании указывать ожидаемую задержку:
  ```yaml
  description: |
    Возвращает summary заказа.
    Eventual consistency: задержка обычно < 1s после изменения в order-service.
  ```

- **R-DIST-EC-2.** **Read-your-writes** — если критично — реализуется одним из способов:
  - Sticky session: запросы клиента маршрутизируются на тот же pod, где был его write.
  - Polling в client до появления update в read-model.
  - Synchronous wait в command-handler с polling read-model (для критичных flows).
  - Альтернативный endpoint, читающий из write-side (полный агрегат через `<X>Repository`).

- **R-DIST-EC-3.** **Bounded staleness** — у каждой read-model явный SLO на максимальную задержку: «не более 5 секунд между write и появлением в read-проекции». Алерт если превышается.

- **R-DIST-EC-4.** **Causal consistency** через `vector clocks` или `version`-поля — для cases где порядок событий важен. Receiver проверяет: `event.version > current_version` перед применением; иначе skip.

### 4.2 Запрещено

- **R-DIST-EC-X1.** **Молчаливая eventual consistency.** Endpoint возвращает stale-data без декларации; клиент удивляется «я только что write сделал, почему не вижу».

- **R-DIST-EC-X2.** **Strict immediate consistency через 2PC** в распределённой системе с большой нагрузкой. Не масштабируется. Перепроектируй boundary либо прими EC.

---

## 5. Outbox + Inbox

Outbox решает проблему «БД commit + message publish атомарно». Inbox — обратное: «message receive + БД update атомарно».

### 5.1 Обязательно

- **R-DIST-OBX-1.** **Outbox pattern** для исходящих событий — обязателен (см. `R-KFK-OBX-*`):
  - Команда commits в БД + INSERT в `outbox_event` атомарно.
  - Outbox-relay (`@Scheduled` с `FOR UPDATE SKIP LOCKED`) публикует в Kafka.
  - Помечает `published_at` после успеха.

- **R-DIST-OBX-2.** **Inbox pattern** для входящих сообщений (опционально, для critical-сценариев):
  - Consumer пишет полученное сообщение в `inbox_event` таблицу + `processed=false`.
  - Отдельный handler берёт unprocessed inbox-rows + обрабатывает их в локальной транзакции.
  - Это даёт «receive-and-store» отдельно от «process» — recovery возможен.
  - Большинство случаев — inbox избыточен, достаточно `processed_event` dedup-таблицы (см. `R-KFK-IDEM-2`).

- **R-DIST-OBX-3.** **Single source of truth** — БД сервиса. Kafka — транспорт сообщений, не источник правды. При потере Kafka-данных — outbox-таблица продолжает накапливать, после восстановления Kafka — публикует.

### 5.2 Запрещено

- **R-DIST-OBX-X1.** **Direct send из command-handler** без outbox. См. `R-KFK-PROD-X4`.

- **R-DIST-OBX-X2.** **`@TransactionalEventListener`** для отправки в Kafka. См. `R-KFK-OBX-X2`.

---

## 6. Compensation

Compensation — отмена действия, выполненного в предыдущем шаге саги.

### 6.1 Обязательно

- **R-DIST-COMP-1.** **Каждая command, участвующая в саге, имеет compensation-команду**:
  - `chargePayment` ↔ `refundPayment`.
  - `reserveInventory` ↔ `releaseInventory`.
  - `createOrder` ↔ `cancelOrder` (или `markOrderFailed`).

- **R-DIST-COMP-2.** **Compensation идемпотентен** — saga может повторить compensation несколько раз при retry. См. `R-DIST-IDEM-*`.

- **R-DIST-COMP-3.** **Semantic compensation, не технический rollback.** Если был платёж — compensation = refund (новая транзакция), не «откат» (ничего не откатывается, деньги уже у банка).

- **R-DIST-COMP-4.** **Compensation в БД оставляет audit trail** — статус «refunded» с reference к оригинальной транзакции. Не DELETE, не UPDATE с потерей истории.

### 6.2 Запрещено

- **R-DIST-COMP-X1.** **Saga без compensation** (см. `R-DIST-SAGA-X2`).

- **R-DIST-COMP-X2.** **DELETE как compensation**. Если было «создан заказ» → compensation должно быть «cancelled order» (state-change), не `DELETE FROM orders`. Иначе теряется audit + реальные данные (refund к зомби-заказу).

- **R-DIST-COMP-X3.** **Compensation, которое снова может упасть и не имеет повторного compensation.** Если refund упал — у нас «висящие деньги». Нужен dead-letter queue + manual review.

---

## 7. Distributed transactions — что НЕ делать

### 7.1 Запрещено

- **R-DIST-TX-X1.** **JTA / 2PC / XA транзакции** в нашем стеке. Причины:
  - Kafka (наш main message broker) не поддерживает XA.
  - 2PC = synchronous block — не масштабируется.
  - Single point of failure (transaction coordinator).
  - Сложно operate в Kubernetes.

- **R-DIST-TX-X2.** **Single distributed transaction через Spring `JtaTransactionManager`** для multi-datasource. Используй modular monolith с одним PG, либо разделение на сервисы с saga.

- **R-DIST-TX-X3.** **`PlatformTransactionManager` over multiple datasources** через `ChainedTransactionManager` — best-effort, **не** атомарность. При failure между commit'ами — inconsistency, без recovery-плана.

### 7.2 Альтернативы (Обязательно)

- **R-DIST-TX-1.** **Saga с локальными транзакциями** — стандарт UCP (см. `R-DIST-SAGA-*`).
- **R-DIST-TX-2.** **Outbox + Idempotent consumer** для cross-service event-driven sync.
- **R-DIST-TX-3.** **Modular monolith** для tight coupling — несколько BC в одном процессе с одним PG. Локальные `@Transactional` работают.

---

## 8. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Распределённые паттерны для one-сервиса | `R-DIST-WHEN-X1` | `@Transactional` |
| Микросервисы из амбиций | `R-DIST-WHEN-X2` | modular monolith |
| 2PC / JTA вместо saga | `R-DIST-SAGA-X1`, `R-DIST-TX-X1` | saga с compensation |
| Saga без compensation | `R-DIST-SAGA-X2`, `R-DIST-COMP-X1` | каждый шаг — compensation |
| Saga state in-memory | `R-DIST-SAGA-X3` | `saga_<name>` таблица |
| Saga смешана с use case | `R-DIST-SAGA-X4` | отдельный orchestrator |
| Receiver без dedup для money | `R-DIST-IDEM-X1` | processed_event + Idempotency-Key |
| Только receiver-side dedup | `R-DIST-IDEM-X2` | producer enable.idempotence + receiver dedup |
| Idempotency-Key = новый UUID каждый раз | `R-DIST-IDEM-X3` | один ключ на бизнес-операцию |
| Молчаливая eventual consistency | `R-DIST-EC-X1` | в OpenAPI description |
| 2PC для immediate consistency | `R-DIST-EC-X2`, `R-DIST-TX-X1` | redesign boundary либо EC |
| Direct send из command без outbox | `R-DIST-OBX-X1` | outbox pattern |
| @TransactionalEventListener для Kafka | `R-DIST-OBX-X2` | outbox-relay |
| DELETE как compensation | `R-DIST-COMP-X2` | semantic state-change (`cancelled`) |
| Compensation без DLQ при failure | `R-DIST-COMP-X3` | DLQ + manual review |
| ChainedTransactionManager multi-DS | `R-DIST-TX-X3` | один PG или saga |

Финальная сводка: правил «Обязательно» — около 25, «Запрещено» — около 20.
