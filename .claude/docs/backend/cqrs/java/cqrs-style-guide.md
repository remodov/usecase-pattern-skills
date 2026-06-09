# CQRS Style Guide

Свод правил применения CQRS (Command Query Responsibility Segregation) в Java/Spring-сервисах команды UCP. Каждое правило идентифицируется кодом (`R-CQRS-CMD-1`, `R-CQRS-RM-X1`) — скилл `ucp-cqrs-review` цитирует эти коды в findings.

CQRS уже частично реализован в `usecase-pattern-style-guide.md` через маркеры `UseCaseCommand<R>` / `UseCaseQuery<R>` (правила `R-UC-*` и `R-CQRS-*` в Use Case Pattern). Этот гайд **углубляет** тему: когда CQRS оправдан, как разделять модели чтения и записи, что такое read-model и read-projection, как синхронизировать через события, антипаттерны.

Не покрывает: Event Sourcing (`R-ES-*` — отдельная тема, в планах), DDD-агрегаты (это `R-AGG-*`), persistence-слой (`R-JOOQ-*`).

Связанные стандарты:
- `R-UC-*` / `R-LAY-*` (Use Case Pattern) — `UseCaseCommand` / `UseCaseQuery` маркеры.
- `R-AGG-*` (DDD tactical) — write-side это агрегат.
- `R-JOOQ-VIEW-*` (jOOQ) — `*ViewRepository` для read-проекций.
- `R-KFK-OBX-*` / `R-KFK-EVT-*` (Kafka) — domain events для синхронизации read-model.
- `R-PG-MV-*` (PG materialized views) — для тяжёлых read-projection.

---

## Содержание

1. [Когда CQRS оправдан — `R-CQRS-WHEN-*`](#1-когда-cqrs-оправдан)
2. [Command side — `R-CQRS-CMD-*`](#2-command-side)
3. [Query side — `R-CQRS-QRY-*`](#3-query-side)
4. [Read-model — `R-CQRS-RM-*`](#4-read-model)
5. [Синхронизация через события — `R-CQRS-SYNC-*`](#5-синхронизация-через-события)
6. [Уровень и эволюция CQRS — `R-CQRS-TIER-*`](#6-уровень-и-эволюция-cqrs)
7. [Антипаттерны — сводка `R-CQRS-*-X*`](#7-антипаттерны)

---

## 1. Когда CQRS оправдан

CQRS — паттерн, который добавляет сложность. Применять только когда выгода покрывает цену.

### 1.1 Обязательно

- **R-CQRS-WHEN-1.** **Lightweight CQRS на маркерах** (`UseCaseCommand` / `UseCaseQuery`) — обязателен на Уровне 2+. Это бесплатное разделение: один и тот же интерфейс, два маркера, разные `@Transactional`-свойства, разная валидация. Не требует отдельной read-БД. CQRS — опция Уровня 2 (Use Case Pattern), не отдельный уровень зрелости.

- **R-CQRS-WHEN-2.** **Полный CQRS с разделением хранилищ** (write-DB + read-DB / search-engine / cache) оправдан при:
  - Read:write ratio ≥ 10:1 (типичный e-commerce frontend).
  - Read-проекции принципиально отличаются от агрегата (search, аналитика, сводки).
  - Read-нагрузка превышает write-throughput write-DB.
  - Need for read scaling без vertical scaling write-DB.

- **R-CQRS-WHEN-3.** **Денормализованная read-model** (отдельная PG-таблица в той же БД) — middle-ground. Подходит когда:
  - Запросы требуют join'ов 5+ таблиц.
  - Сводки / отчёты с тяжёлыми aggregations (GROUP BY миллионов строк).
  - Search по text-полям → ElasticSearch / pg_trgm в отдельной materialized view.

### 1.2 Запрещено

- **R-CQRS-WHEN-X1.** **Полный CQRS «just in case»** для нового сервиса без явной проблемы read-нагрузки. Стартуем с lightweight (маркеры + один и тот же `Repository`), эволюционируем к full CQRS когда метрики покажут необходимость.

- **R-CQRS-WHEN-X2.** **Разделение баз без явной причины.** Read-DB + write-DB добавляют sync complexity, eventual consistency, инфра-стоимость. Должна быть конкретная боль.

---

## 2. Command side

Command side — изменение состояния. Это write-handler'ы, агрегаты, события.

### 2.1 Обязательно

- **R-CQRS-CMD-1.** Command — record, реализует `UseCaseCommand<R>` (см. `R-UC-1`):
  ```java
  public record ConfirmOrderCommand(Long orderId, String idempotencyKey)
      implements UseCaseCommand<Order> {}
  ```

- **R-CQRS-CMD-2.** Command **меняет state одного агрегата**. Если меняет несколько — это либо saga (см. `R-DIST-SAGA-*`), либо неправильно нарезаны границы агрегатов (`R-AGG-*`).

- **R-CQRS-CMD-3.** Command handler:
  - `@Component` + `@Transactional` (RW по умолчанию, см. `R-JOOQ-TX-1`).
  - Загружает агрегат через `<X>Repository.findById(id, SelectMode.FOR_UPDATE)` — pessimistic lock на write-path.
  - Вызывает доменный метод (`order.confirm()`).
  - Сохраняет (`repository.save(order)`).
  - Записывает в outbox `<X>Event` (см. `R-KFK-OBX-1`) — для синхронизации read-model.

- **R-CQRS-CMD-4.** Command возвращает **минимум**: id новой/изменённой entity, статус (`Order` или просто `Long`), либо `UseCaseEmptyResult`. Не возвращай read-DTO целиком из command — это смешение responsibilities.

- **R-CQRS-CMD-5.** Validation на command — частично контракт (через generated DTO + Jakarta, см. `R-VLD-WHERE-1`); бизнес-инварианты — в агрегате (`R-VLD-WHERE-3`).

### 2.2 Запрещено

- **R-CQRS-CMD-X1.** Command-handler делает SELECT для **чтения** «и обновления потом». Read должен идти через query-handler. Если внутри command нужно что-то прочитать — это часть load-aggregate (одно действие), не отдельный read.

- **R-CQRS-CMD-X2.** Command возвращает **полный read-DTO** (`OrderJson` со всеми вложениями для UI). Контроллер сам сделает второй call в query-handler если UI нужен read после write.

- **R-CQRS-CMD-X3.** **Несколько агрегатов** меняются в одном `@Transactional` command-handler без саги. Нарушает aggregate-границы и atomicity (`R-AGG-X*`).

---

## 3. Query side

Query side — чтение. Read-handler'ы, view-репозитории, read-DTO.

### 3.1 Обязательно

- **R-CQRS-QRY-1.** Query — record, реализует `UseCaseQuery<R>` (см. `R-UC-1`):
  ```java
  public record GetOrderSummaryQuery(Long orderId)
      implements UseCaseQuery<OrderSummary> {}
  ```

- **R-CQRS-QRY-2.** Query handler:
  - `@Component` + `@Transactional(readOnly = true)` (см. `R-JOOQ-TX-2`).
  - Загружает данные через `<X>ViewRepository` (см. `R-JOOQ-VIEW-1`) — отдельный интерфейс для read-проекций.
  - Возвращает read-DTO (`OrderSummary`), не агрегат.

- **R-CQRS-QRY-3.** Read-DTO — **read-model record** в `core/<bc>/dto/view/` или `core/<bc>/domain/repository/view/`:
  ```java
  public record OrderSummary(
      Long orderId,
      OrderStatus status,
      String customerName,        // денормализовано — не нужно вытаскивать Customer
      Money totalAmount,
      int itemCount,              // pre-computed, не List<OrderItem>
      OffsetDateTime createdAt
  ) {}
  ```
  Структура продиктована UI/API needs, не агрегатом.

- **R-CQRS-QRY-4.** Query handler **не вызывает доменные методы** агрегата (`order.confirm()` etc.). Только read.

### 3.2 Запрещено

- **R-CQRS-QRY-X1.** Query handler делает write (UPDATE / INSERT / DELETE). Это уже command, перенеси.

- **R-CQRS-QRY-X2.** Query handler **загружает агрегат целиком** через основной `<X>Repository` (с multiset, FOR UPDATE и т.п.) и потом маппит в read-DTO. Это лишняя работа: если есть `<X>ViewRepository` — используй его; если нет — создай.

- **R-CQRS-QRY-X3.** Query возвращает агрегат (`Order`) или его внутренние Entity (`OrderItem`) наружу. Это нарушение границ DDD — потребитель может вызвать business-методы на read-объекте, что разорвёт инварианты.

---

## 4. Read-model

Read-model — данные, оптимизированные под чтение. Это может быть отдельная таблица в той же БД, materialized view, ElasticSearch index, Redis cache.

### 4.1 Обязательно

- **R-CQRS-RM-1.** Read-model хранится в **месте, оптимальном для нагрузки чтения**:
  - Денормализованная PG-таблица (`order_summary`) — для tabular queries / pagination.
  - PG materialized view — для тяжёлых aggregations с TTL refresh.
  - Redis (см. `R-CACHE-*`) — для key-lookup hot-keys.
  - ElasticSearch — для full-text search и multi-field фильтров с relevance.

- **R-CQRS-RM-2.** **Schema read-model** — независимая от write-схемы. Денормализуй: `order_summary` содержит `customer_name`, `customer_email_hash` без join к `customer` таблице.

- **R-CQRS-RM-3.** Read-model **обновляется через события** (`R-CQRS-SYNC-*`), не synchronously в command-handler:
  - Command commit → outbox event → kafka → read-side consumer → UPDATE read-model.
  - Eventual consistency — норма CQRS. Latency обычно 100ms–1s.

- **R-CQRS-RM-4.** Read-model **может быть восстановлена** из write-side данных. Если read-model потеряна — есть скрипт перебора всех агрегатов и пересчёта read-model. Это критично для disaster recovery.

### 4.2 Запрещено

- **R-CQRS-RM-X1.** Read-model **с бизнес-логикой** (триггеры на UPDATE с CHECK-constraint бизнес-правил). Логика в write-side; read-model — только проекция.

- **R-CQRS-RM-X2.** **Source-of-truth read-model.** Если read-model потеряна и не восстановима из write-side — это уже не CQRS, это две разных системы с risk inconsistency.

- **R-CQRS-RM-X3.** **Bidirectional sync** (read-model → write-side). Eventual consistency идёт **в одну сторону**: write → events → read. Обратное направление = две систему с своим source-of-truth = ад.

---

## 5. Синхронизация через события

### 5.1 Обязательно

- **R-CQRS-SYNC-1.** **Синхронизация через outbox + Kafka** (см. `R-KFK-OBX-1`):
  - Command commit → outbox event атомарно.
  - Outbox-relay публикует в Kafka.
  - Read-side consumer (в этом же сервисе или другом) обновляет read-model.

- **R-CQRS-SYNC-2.** **Idempotent consumer** обязателен (см. `R-KFK-IDEM-1`). Read-model UPDATE может прийти дважды; consumer должен это распознавать (`processed_event` таблица или idempotent UPDATE через `version`-проверку).

- **R-CQRS-SYNC-3.** **Синхронный fallback при бутстрапе.** При первом запуске сервиса (или при потере read-model) — батч-задача проходит по агрегатам и rebuilds read-model. Не ждём пока придут события за 30 дней.

- **R-CQRS-SYNC-4.** **Eventual consistency декларируется в API**. Endpoint `GET /orders/{id}/summary` имеет в OpenAPI:
  ```yaml
  description: |
    Возвращает read-проекцию заказа.
    Возможна задержка до 1 секунды между write и появлением в этой проекции.
    Для immediate consistency используйте GET /orders/{id} (полный агрегат).
  ```

- **R-CQRS-SYNC-5.** **Read-your-writes** при необходимости — гарантия что после `POST /orders` (write) тот же клиент видит `GET /orders/{id}/summary` (read) с уже актуальными данными. Реализуется через:
  - Sticky session в gateway (запросы того же клиента — на тот же pod).
  - Либо явный wait в command-handler с polling read-model до успеха.
  - Либо альтернативный endpoint (без CQRS-разделения) для cases где RYW критичен.

### 5.2 Запрещено

- **R-CQRS-SYNC-X1.** **Синхронный UPDATE read-model в command-handler** (через JOOQ INSERT в `order_summary` после save Order). Read-model становится partof write-transaction → теряется decoupling, при rollback всё откатывается. Используй outbox.

- **R-CQRS-SYNC-X2.** **Sync через triggers БД** (PG trigger на `order` UPDATE → INSERT в `order_summary`). Невидимая магия, ломается на bulk-операциях, не работает cross-DB.

- **R-CQRS-SYNC-X3.** **Schema-coupled events.** Если event payload — это generated POJO write-схемы, любой ALTER TABLE на write-side ломает consumers. См. `R-KFK-EVT-X4` (event versioning).

---

## 6. Уровень и эволюция CQRS

### 6.1 Обязательно

- **R-CQRS-TIER-1.** **Уровень 1** (Слоёный: Controller → Service → Repository): CQRS не применяется, UseCase-маркеров нет.

- **R-CQRS-TIER-2.** **Уровень 2** (Use Case Pattern): lightweight CQRS — опция уровня, маркеры `UseCaseCommand`/`UseCaseQuery` обязательны. Read и write через **один и тот же `<X>Repository`**, но read-методы через `SelectMode.NO_LOCK` + `@Transactional(readOnly = true)`.

- **R-CQRS-TIER-3.** **Уровень 3** (DDD + Hexagonal): полный split. Появляется `<X>ViewRepository` (см. `R-JOOQ-VIEW-1`) с read-DTO; write — через `<X>Repository` с агрегатом и `FOR UPDATE`.

- **R-CQRS-TIER-4.** **Уровень 3, event-driven**: read-model в отдельной таблице/Redis/ElasticSearch, синхронизация через outbox + Kafka. Дальнейшая эволюция полного split по мере роста нагрузки.

- **R-CQRS-TIER-5.** **Эволюция CQRS всегда в одну сторону**: маркеры (Уровень 2) → split с ViewRepository (Уровень 3) → event-driven read-model. Возврат назад — крайне редкий и обычно говорит о неверной first-step decision.

### 6.2 Запрещено

- **R-CQRS-TIER-X1.** Уровень 1 с CQRS-маркерами «потому что красиво». Маркеры без enforcement (transactional readOnly, отдельный repository) — карго-культ.

- **R-CQRS-TIER-X2.** Event-driven read-model с одним `<X>Repository` для read и write. Если есть отдельная read-инфраструктура (отдельная таблица), то и интерфейс отдельный.

---

## 7. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Полный CQRS «just in case» для нового сервиса | `R-CQRS-WHEN-X1` | lightweight маркеры на старте |
| Разделение баз без явной причины | `R-CQRS-WHEN-X2` | conscientious decision |
| Command-handler делает отдельный SELECT | `R-CQRS-CMD-X1` | load-aggregate one-shot |
| Command возвращает полный read-DTO | `R-CQRS-CMD-X2` | минимум: id/статус |
| Несколько агрегатов в одном command | `R-CQRS-CMD-X3` | saga (см. `R-DIST-SAGA-*`) |
| Query handler делает write | `R-CQRS-QRY-X1` | перенести в command |
| Query грузит агрегат целиком и маппит | `R-CQRS-QRY-X2` | `<X>ViewRepository` с минимум данных |
| Query возвращает агрегат наружу | `R-CQRS-QRY-X3` | read-DTO |
| Read-model с бизнес-логикой | `R-CQRS-RM-X1` | проекция, без триггеров логики |
| Read-model как source-of-truth | `R-CQRS-RM-X2` | восстановима из write-side |
| Bidirectional sync | `R-CQRS-RM-X3` | one-way: write → events → read |
| Sync read-model в command-tx | `R-CQRS-SYNC-X1` | outbox + Kafka |
| Sync через PG triggers | `R-CQRS-SYNC-X2` | outbox + consumer |
| Schema-coupled events | `R-CQRS-SYNC-X3` | versioned event-records |
| Уровень 1 с CQRS-маркерами без enforcement | `R-CQRS-TIER-X1` | без маркеров |
| Event-driven read-model с одним repository для R+W | `R-CQRS-TIER-X2` | отдельный ViewRepository |

Финальная сводка: правил «Обязательно» — около 25, «Запрещено» — около 16.
