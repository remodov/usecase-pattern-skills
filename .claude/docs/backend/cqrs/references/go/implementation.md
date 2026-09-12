# CQRS — реализация на Go (net/http + chi)

Реализация контракта `../spec.md` (коды `R-CQRS-*`) на Go-стеке (stdlib `net/http` + chi).
Коды правил — общие с Java/Python; меняется реализация: маркеры `Command`/`Query` — интерфейсы-маркеры
(Go не имеет дженерик-параметризованных интерфейсов на уровне среды выполнения, поэтому маркер = пустой
интерфейс + строгая типизация Handler), read-only сторона — pgx с `pool.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})`, read-проекции
— `<X>ViewRepository`-интерфейс → read-DTO (`struct`, не агрегат).

> **Парадигма ошибок.** Command / Query handler возвращают `(T, error)`. Доменные ошибки — значения с
> `Kind() apperr.Domain`; edge-middleware (`httperr.Write`) маппит категорию в статус (`R-ERR-MAP-*`).
> Полный контракт ошибок — `../error-handling/references/go/implementation.md`.

---

## 1. Когда CQRS оправдан (`R-CQRS-WHEN-*`)

`cqrs/lightweight-first-full-on-evidence` — lightweight CQRS на маркерах (`Command`/`Query`-интерфейсах) — обязателен на Уровне 2+:
один интерфейс Handler, два маркера, read через read-only транзакцию pgx. `cqrs/lightweight-first-full-on-evidence`/`cqrs/lightweight-first-full-on-evidence` —
полный split (read-DB / Redis / ES) или денормализованная read-таблица — при доказанной read-нагрузке.
`cqrs/lightweight-first-full-on-evidence`/`X2` — полный CQRS / разделение БД «just in case» без боли; стартуем lightweight,
эволюционируем по метрикам.

---

## 2. Command side (`R-CQRS-CMD-*`)

`cqrs/command-returns-minimum` — Command = иммутабельный `struct`, реализует маркер-интерфейс `Command` (`usecase-pattern/usecase-implements-marker`). В Go
нет sealed-типов, поэтому маркер — пустой интерфейс с неэкспортируемым методом (пакетный замок):

```go
// core/cqrs/cqrs.go
package cqrs

type Command interface{ isCommand() }
type Query   interface{ isQuery()   }
```

```go
// core/order/command/confirm_order.go
package command

import "core/cqrs"

type ConfirmOrder struct {
    OrderID string
}

func (ConfirmOrder) isCommand() {}
```

`cqrs/command-changes-one-aggregate` — Command меняет state **одного** агрегата. Несколько агрегатов — saga (`R-DIST-SAGA-*`) или
неверные границы (`R-AGG-*`).

`cqrs/command-handler-does-not-query` — handler: загружает агрегат → вызывает доменный метод → сохраняет → фиксирует транзакцию:

```go
// core/order/handler/confirm_order_handler.go
package handler

type ConfirmOrderHandler struct {
    orders OrderRepository
    uow    UnitOfWork
    clock  Clock
}

func (h *ConfirmOrderHandler) Handle(ctx context.Context, cmd command.ConfirmOrder) (string, error) {
    var orderID string
    err := h.uow.Within(ctx, func(ctx context.Context) error {
        order, err := h.orders.ByID(ctx, cmd.OrderID)
        if err != nil {
            return fmt.Errorf("load order %s: %w", cmd.OrderID, err)
        }
        if err := order.Confirm(h.clock); err != nil {
            return err
        }
        if err := h.orders.Save(ctx, order); err != nil {
            return fmt.Errorf("save order: %w", err)
        }
        orderID = order.ID
        return nil
    })
    return orderID, err
}
// UnitOfWork-порт (core/port/uow.go) и out-адаптер (adapters/out/persistence/uow.go),
// пробрасывающий pgx.Tx через context, описаны в usecase-pattern/go §8.
```

`cqrs/command-returns-minimum` — возвращает минимум: id новой/изменённой entity, статус-код или `struct{}`. Не возвращает
read-DTO: контроллер сам вызовет query-handler если UI нужны данные после write.

`cqrs/validation-split-edge-and-aggregate` — валидация входа на DTO-слое (`go-playground/validator`, `validation/input-validated-at-edge`); бизнес-инварианты
в агрегате (`validation/domain-invariants-in-aggregate`).

`cqrs/command-handler-does-not-query` ❌ SELECT «для чтения, потом обновления» в command-handler. Чтение идёт через query-handler;
load-aggregate через `ByID` — одно действие, не отдельный query-путь.

`cqrs/command-returns-minimum` ❌ Возврат `OrderSummaryDTO` (полного read-DTO) из command.

`cqrs/command-changes-one-aggregate` ❌ Несколько агрегатов в одной транзакции без саги.

---

## 3. Query side (`R-CQRS-QRY-*`)

`cqrs/query-is-read-only` — Query = иммутабельный `struct`, реализует маркер-интерфейс `Query`:

```go
// core/order/query/get_order_summary.go
package query

type GetOrderSummary struct {
    OrderID string
}

func (GetOrderSummary) isQuery() {}
```

`cqrs/query-is-read-only` — handler читает через `<X>ViewRepository`, read-only транзакция, без commit:

```go
// core/order/handler/get_order_summary_handler.go
package handler

type GetOrderSummaryHandler struct {
    views OrderViewRepository
    db    *pgxpool.Pool
}

func (h *GetOrderSummaryHandler) Handle(ctx context.Context, q query.GetOrderSummary) (OrderSummaryDTO, error) {
    tx, err := h.db.BeginTx(ctx, pgx.TxOptions{AccessMode: pgx.ReadOnly})
    if err != nil {
        return OrderSummaryDTO{}, fmt.Errorf("begin read tx: %w", err)
    }
    defer tx.Rollback(ctx)

    summary, err := h.views.SummaryByID(ctx, tx, q.OrderID)
    if err != nil {
        return OrderSummaryDTO{}, fmt.Errorf("read order summary %s: %w", q.OrderID, err)
    }
    return summary, nil
}
```

`cqrs/query-returns-read-model` — read-DTO в `core/<bc>/dto/view/` или `core/<bc>/port/view/`. Структура — под UI/API,
не агрегат:

```go
// core/order/dto/view/order_summary.go
package view

type OrderSummaryDTO struct {
    OrderID       string
    CustomerName  string
    TotalAmount   int64
    Status        string
    ItemCount     int
    CreatedAt     time.Time
}
```

`cqrs/query-is-read-only` — query-handler не вызывает доменные методы агрегата (`order.Confirm()` и т. п.).
Только read.

`cqrs/query-is-read-only` ❌ UPDATE / INSERT / DELETE в query-handler → это command, перенести.

`cqrs/read-via-projection-not-aggregate` ❌ Загрузка агрегата `OrderRepository.ByID` (с `FOR UPDATE` / eager-load) с последующим
маппингом в DTO вместо `OrderViewRepository.SummaryByID`.

`cqrs/query-returns-read-model` ❌ Возврат агрегата `*Order` или Entity `*OrderItem` из query-handler наружу.

---

## 4. Read-model (`R-CQRS-RM-*`)

`cqrs/read-model-storage-and-schema` — read-model в месте, оптимальном для нагрузки чтения: PG-таблица (`order_summary`),
Redis-Hash (`go-redis/v9`) или ES-индекс — зависит от паттерна доступа.

`cqrs/read-model-storage-and-schema` — схема read-model независима от write-схемы. Денормализация обязательна:
`order_summary` хранит `customer_name`, `customer_email_hash` без join к `customer`:

```sql
-- read-side: независимая таблица
CREATE TABLE order_summary (
    order_id       uuid PRIMARY KEY,
    customer_name  text NOT NULL,
    total_amount   bigint NOT NULL,
    status         text NOT NULL,
    item_count     int NOT NULL,
    updated_at     timestamptz NOT NULL
);
```

`cqrs/read-model-synced-by-events` — read-model обновляется **через события** (`R-CQRS-SYNC-*`), не синхронно в command-handler.

`cqrs/read-model-is-rebuildable` — read-model восстановима из write-side. Существует rebuild-скрипт (или отдельная команда),
обходящий агрегаты и пересчитывающий read-model. Критично для disaster recovery.

`cqrs/projection-has-no-logic-or-backflow` ❌ Бизнес-логика в read-model (PG-триггеры с CHECK бизнес-правил). Логика — в write-side.

`cqrs/read-model-is-rebuildable` ❌ Read-model как source-of-truth (невосстановима из write) — это две системы.

`cqrs/projection-has-no-logic-or-backflow` ❌ Bidirectional sync (read → write). Eventual consistency — в одну сторону:
write → events → read.

---

## 5. Синхронизация через события (`R-CQRS-SYNC-*`)

`cqrs/read-model-synced-by-events` — sync через outbox + Kafka (`kafka/publish-via-outbox`). Go-стек: `segmentio/kafka-go` producer
читает из outbox-таблицы в той же PG-транзакции command-handler:

```go
// adapters/out/outbox/order_outbox_repository.go
func (r *OrderOutboxRepository) Enqueue(ctx context.Context, tx pgx.Tx, evt OrderConfirmedEvent) error {
    payload, err := json.Marshal(evt)
    if err != nil {
        return fmt.Errorf("marshal event: %w", err)
    }
    _, err = tx.Exec(ctx,
        `INSERT INTO outbox (event_type, payload, created_at) VALUES ($1, $2, now())`,
        "order.confirmed", payload,
    )
    return err
}
```

`cqrs/read-model-consumer-is-idempotent` — idempotent consumer обязателен (`kafka/consumer-is-idempotent`). Read-model UPDATE может прийти дважды;
consumer проверяет `processed_event` или использует idempotent UPDATE с `version`-проверкой:

```go
// adapters/in/kafka/order_summary_consumer.go
func (c *OrderSummaryConsumer) handle(ctx context.Context, msg kafka.Message) error {
    var evt OrderConfirmedEvent
    if err := json.Unmarshal(msg.Value, &evt); err != nil {
        return fmt.Errorf("unmarshal: %w", err)
    }
    tx, err := c.db.BeginTx(ctx, pgx.TxOptions{})
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)

    var alreadyProcessed bool
    _ = tx.QueryRow(ctx,
        `SELECT EXISTS(SELECT 1 FROM processed_event WHERE event_id = $1)`, evt.EventID,
    ).Scan(&alreadyProcessed)
    if alreadyProcessed {
        return nil
    }

    if err := c.summaries.Upsert(ctx, tx, toSummary(evt)); err != nil {
        return fmt.Errorf("upsert summary: %w", err)
    }
    _, err = tx.Exec(ctx,
        `INSERT INTO processed_event (event_id, processed_at) VALUES ($1, now())`, evt.EventID,
    )
    if err != nil {
        return fmt.Errorf("mark processed: %w", err)
    }
    return tx.Commit(ctx)
}
```

`cqrs/read-model-is-rebuildable` — синхронный rebuild при бутстрапе / потере read-model. Не ждём пока придут события
за прошедший период:

```go
// cmd/rebuild/main.go — отдельная CLI-команда, не часть основного сервера
func rebuildOrderSummaries(ctx context.Context, db *pgxpool.Pool, summaries OrderSummaryRepository) error {
    offset := 0
    for {
        orders, err := loadOrdersBatch(ctx, db, offset, 500)
        if err != nil || len(orders) == 0 {
            return err
        }
        for _, o := range orders {
            if err := summaries.Upsert(ctx, nil, toSummary(o)); err != nil {
                return err
            }
        }
        offset += len(orders)
    }
}
```

`cqrs/eventual-consistency-declared` — eventual consistency декларируется в OpenAPI. В Go (code-first через спецификацию или
комментарии):

```go
// edge/handler/order_summary_handler.go
// GET /orders/{id}/summary
// X-Data-Freshness: eventual (обновляется async через Kafka, задержка ≤ 2s)
```

`cqrs/eventual-consistency-declared` — read-your-writes при необходимости. Два подхода:
- Читать из write-side (основного репозитория) для того же клиента сразу после write.
- Version-токен: command возвращает `version`, UI ждёт query с `?minVersion=N`.

`cqrs/read-model-synced-by-events` ❌ Синхронный INSERT в `order_summary` внутри command-транзакции. Теряется decoupling;
при rollback read-model тоже откатывается. Используй outbox.

`cqrs/read-model-synced-by-events` ❌ Sync через PG-триггеры. Невидимая магия, ломается на bulk-операциях, не cross-DB.

`cqrs/events-not-coupled-to-write-schema` ❌ Schema-coupled events: payload = сгенерированный `sqlc`-тип write-схемы. Любой
ALTER TABLE ломает consumer'ов (`kafka/event-schema-forward-compatible`). Payload — явный event-struct с версионированием.

---

## 6. Уровень и эволюция (`R-CQRS-TIER-*`)

`cqrs/split-matches-maturity-level` — Уровень 1 (плоский `handler → repository`): CQRS-маркеров нет, не применяем.

`cqrs/split-matches-maturity-level` — Уровень 2: lightweight CQRS. Маркеры `Command`/`Query` обязательны. Read и write
через **один и тот же `<X>Repository`**, но read-методы используют read-only транзакцию pgx
(`pgx.TxOptions{AccessMode: pgx.ReadOnly}`). Enforcement — pgx падает на попытке write в read-only tx:

```go
// Уровень 2: один интерфейс, две транзакционных стратегии.
// pgx.Tx не в сигнатуре порта — tx пробрасывается через context UnitOfWork-адаптером (usecase-pattern/go §8).
type OrderRepository interface {
    ByID(ctx context.Context, id string) (*Order, error)
    SummaryByID(ctx context.Context, id string) (OrderSummaryDTO, error)
    Save(ctx context.Context, o *Order) error
}
```

`cqrs/split-matches-maturity-level` — Уровень 3: отдельный `<X>ViewRepository`-интерфейс с read-DTO; write — `<X>Repository`
с агрегатом. sqlc генерирует разные query-файлы под каждый интерфейс:

```go
// pgx.Tx не в сигнатурах портов — tx пробрасывается через context UnitOfWork-адаптером (usecase-pattern/go §8).
type OrderRepository interface {
    ByID(ctx context.Context, id string) (*Order, error)
    Save(ctx context.Context, o *Order) error
}

type OrderViewRepository interface {
    SummaryByID(ctx context.Context, id string) (OrderSummaryDTO, error)
    ListByCustomer(ctx context.Context, customerID string, page Pagination) ([]OrderSummaryDTO, error)
}
```

`cqrs/split-matches-maturity-level` — Уровень 3 event-driven: read-model в отдельной таблице / Redis / ES, sync через
outbox + Kafka (см. §5). `OrderViewRepository` читает из `order_summary`, не из `orders`.

`cqrs/evolution-is-one-way` — эволюция в одну сторону: Tier 2 → 3 → 4. Откат назад — признак неверного
first-step decision, не нормальный рефакторинг.

`cqrs/split-matches-maturity-level` ❌ Уровень 1 с маркерами `Command`/`Query` без enforcement (read-only tx, отдельный
интерфейс). Маркеры без механизма — карго-культ.

`cqrs/split-matches-maturity-level` ❌ Event-driven read-model (`order_summary`) с единым `OrderRepository` для read и
write. Отдельная инфра требует отдельного интерфейса.

---

## 7. Антипаттерны (`R-CQRS-ANTI-*`)

Все антипаттерны закрыты AVOID-правилами выше. Краткая сводка для ревью:

| Антипаттерн | Нарушает | Симптом в Go |
|---|---|---|
| Command возвращает `OrderDTO` | `cqrs/command-returns-minimum` | Handler возвращает `view.OrderSummaryDTO` |
| Query делает `tx.Exec("UPDATE …")` | `cqrs/query-is-read-only` | Exec/exec в read-only tx → pgx паника |
| `OrderRepository.ByID` + map → DTO в query | `cqrs/read-via-projection-not-aggregate` | Нет `ViewRepository`, агрегат целиком |
| `INSERT INTO order_summary` в command-транзакции | `cqrs/read-model-synced-by-events` | Нет outbox, синхронный dual-write |
| Payload = sqlc-структура write-схемы | `cqrs/events-not-coupled-to-write-schema` | Event struct содержит `db.Order` |
| Маркеры без read-only tx | `cqrs/split-matches-maturity-level` | `pgx.TxOptions{}` везде одинаково |

---

## Чеклист подключения к новому сервису (Go)

- [ ] `core/cqrs` определяет `Command` и `Query` с неэкспортируемым методом-маркером (пакетный замок)
- [ ] Каждый command-struct реализует `isCommand()`, каждый query-struct — `isQuery()`
- [ ] Command handler: rw-транзакция pgx → load aggregate → domain method → save → commit; возвращает id/статус, не DTO
- [ ] Query handler: read-only транзакция (`pgx.TxOptions{AccessMode: pgx.ReadOnly}`) → `<X>ViewRepository` → read-DTO; без commit, без доменных методов
- [ ] Отдельный `<X>ViewRepository`-интерфейс (Уровень 3) с sqlc-запросами под read-DTO
- [ ] Read-DTO в `core/<bc>/dto/view/` — структура под API, не агрегат
- [ ] Доменные ошибки агрегата — значения с `Kind() apperr.Domain`; edge-middleware (`httperr.Write`) маппит в 409/422
- [ ] Read-model денормализована, независима от write-схемы, восстановима (rebuild-команда)
- [ ] Sync write → read через outbox-таблицу + `segmentio/kafka-go`; нет синхронного dual-write в command-tx
- [ ] Idempotent consumer: `processed_event`-таблица или version-проверка в UPDATE
- [ ] Eventual consistency задекларирована в OpenAPI (заголовок / описание эндпоинта)
- [ ] Уровень соответствует зрелости сервиса; маркеры без enforcement не допускаются (`cqrs/split-matches-maturity-level`)
