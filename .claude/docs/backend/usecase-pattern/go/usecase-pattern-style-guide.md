# usecase-pattern — Go Style Guide (net/http + chi)

Реализация контракта `../usecase-pattern-rules.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`) на Go-стеке (stdlib `net/http` + chi).
Коды — общие с Java/Python; здесь — как они выглядят без ORM и фреймворков инъекций, с ошибками-значениями и ручной конструкторной сборкой.

Структура UCP: `core/<bc>/` (UseCase + Domain + порты-интерфейс, без net/http/pgx), `adapters/in/http/` (chi-роутеры), `adapters/out/` (sqlc+pgx-репозитории, HTTP-клиенты), `app/` (конструкторная DI-сборка, dispatcher).

---

## 1. UseCase — `R-UC-*`

`R-UC-1` / `R-UC-2` — UseCase = immutable struct без методов-логики. Маркеры команды/запроса — интерфейсы-маркеры с приватным методом, параметризованные через дженерик-обёртку:

```go
// core/usecase/usecase.go
package usecase

// Command — маркер операции, изменяющей состояние. R — тип результата.
type Command[R any] interface{ commandResult() R }

// Query — маркер операции, только читающей. R — тип результата.
type Query[R any] interface{ queryResult() R }
```

```go
// core/order/usecases.go
package order

import "myservice/core/usecase"

type OrderID string

// CreateOrder — команда создания заказа; результат — OrderID.
type CreateOrder struct {
    CustomerID string
    Items      []OrderItemInput
}

func (CreateOrder) commandResult() OrderID { return "" }

// FindOrderByID — запрос; результат — OrderView.
type FindOrderByID struct {
    ID string
}

func (FindOrderByID) queryResult() OrderView { return OrderView{} }
```

`R-UC-3` — имя по бизнес-операции (`CreateOrder`, `FindOrderByID`), один UseCase = одна операция.
`R-UC-4` — результат явно типизирован через тип-параметр маркера; для «пустого» ответа — отдельный тип:

```go
type VoidResult struct{}

type CancelOrder struct {
    OrderID   string
    Reason    string
    RequestedBy string
}

func (CancelOrder) commandResult() VoidResult { return VoidResult{} }
```

`R-UC-X1` ❌ логика в UseCase-структуре (методы с обращением к БД, вычисления). `R-UC-X2` ❌ один struct на create+update — разнести. `R-UC-X3` ❌ изменяемые поля (slice-pointer без copy) — передавать через конструктор или явные поля; намеренная иммутабельность в Go — без сеттеров и без экспорта полей-указателей. `R-UC-X4` ❌ возвращать `error` как единственный результат без явного `VoidResult` там, где контроллер ожидает типизированный `R`.

---

## 2. Handler — `R-HND-*`

`R-HND-1` — Handler реализует типизированный интерфейс `Handler[UC, R]`:

```go
// core/usecase/handler.go
package usecase

import "context"

type Handler[UC any, R any] interface {
    Handle(ctx context.Context, uc UC) (R, error)
}
```

```go
// core/order/create_order_handler.go
package order

import (
    "context"
    "myservice/core/order/port"
)

type CreateOrderHandler struct {
    orders port.OrderRepository
    clock  port.Clock
}

func NewCreateOrderHandler(orders port.OrderRepository, clock port.Clock) *CreateOrderHandler {
    return &CreateOrderHandler{orders: orders, clock: clock}
}

func (h *CreateOrderHandler) Handle(ctx context.Context, uc CreateOrder) (OrderID, error) {
    o, err := NewOrder(uc.CustomerID, uc.Items, h.clock.Now())
    if err != nil {
        return "", err
    }
    if err := h.orders.Add(ctx, o); err != nil {
        return "", fmt.Errorf("create order: %w", err)
    }
    return o.ID, nil
}
```

`R-HND-2` — Handler регистрируется в dispatcher'е при конструкторной сборке (`app/wire.go` / `app/di.go`); dispatcher находит его по типу UseCase.

`R-HND-3` — граница транзакции на Handler: команда открывает транзакцию через `UnitOfWork`, запрос — read-only (см. §8).

`R-HND-4` — один Handler — один UseCase (`CreateOrderHandler` только для `CreateOrder`).

`R-HND-5` — все зависимости через конструктор; поля — приватные, инициализируются один раз:

```go
type FindOrderByIDHandler struct {
    orders port.OrderViewRepository
}

func NewFindOrderByIDHandler(orders port.OrderViewRepository) *FindOrderByIDHandler {
    return &FindOrderByIDHandler{orders: orders}
}

func (h *FindOrderByIDHandler) Handle(ctx context.Context, uc FindOrderByID) (OrderView, error) {
    view, err := h.orders.FindByID(ctx, uc.ID)
    if err != nil {
        return OrderView{}, fmt.Errorf("find order %s: %w", uc.ID, err)
    }
    return view, nil
}
```

`R-HND-X1` ❌ Handler зовёт другой Handler напрямую — только через dispatcher / Step. `R-HND-X2` ❌ инфраструктурные ошибки (`pgconn.PgError`, `net.Error`) вылетают из Handler — маппить в доменные в адаптере (cross-ref `R-ERR-WHERE-2b`, `error-handling/go`). `R-HND-X3` ❌ изменяемые поля в Handler (кэш запросов, счётчик) — Handler stateless.

---

## 3. Dispatcher и контроллер — `R-DSP-*`

`R-DSP-1` / `R-DSP-2` — контроллер не вызывает Handler напрямую, только через `Dispatcher`. В Go — реестр `reflect.Type → handlerFunc` собирается при старте:

```go
// app/dispatcher/dispatcher.go
package dispatcher

import (
    "context"
    "fmt"
    "reflect"
)

type handlerFunc func(ctx context.Context, uc any) (any, error)

type Dispatcher struct {
    registry map[reflect.Type]handlerFunc
}

func NewDispatcher() *Dispatcher {
    return &Dispatcher{registry: make(map[reflect.Type]handlerFunc)}
}

// Register связывает тип UseCase с Handler-функцией. Вызывается при сборке app.
func Register[UC any, R any](d *Dispatcher, h interface {
    Handle(context.Context, UC) (R, error)
}) {
    var zero UC
    t := reflect.TypeOf(zero)
    d.registry[t] = func(ctx context.Context, uc any) (any, error) {
        return h.Handle(ctx, uc.(UC))
    }
}

func (d *Dispatcher) Dispatch(ctx context.Context, uc any) (any, error) {
    t := reflect.TypeOf(uc)
    fn, ok := d.registry[t]
    if !ok {
        return nil, fmt.Errorf("no handler registered for %s", t.Name())
    }
    return fn(ctx, uc)
}
```

Регистрация в DI-сборке:

```go
// app/di.go
d := dispatcher.NewDispatcher()
dispatcher.Register(d, order.NewCreateOrderHandler(orderRepo, clock))
dispatcher.Register(d, order.NewFindOrderByIDHandler(orderViewRepo))
```

`R-DSP-3` — контроллер делает только: маппинг `Request → UseCase`, `dispatch`, маппинг `Result → Response`, HTTP-код:

```go
// adapters/in/http/order_handler.go
func (h *OrderHTTPHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
    var req CreateOrderRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        httperr.Write(w, r, apperr.NewValidation("invalid request body"))
        return
    }
    principal := auth.PrincipalFromCtx(r.Context())         // R-DSP-X2: из контекста, не из UseCase
    result, err := h.dispatcher.Dispatch(r.Context(), order.CreateOrder{
        CustomerID: principal.UserID,
        Items:      req.toDomainItems(),
    })
    if err != nil {
        httperr.Write(w, r, err)
        return
    }
    orderID := result.(order.OrderID)
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusCreated)
    _ = json.NewEncoder(w).Encode(CreateOrderResponse{ID: string(orderID)})
}
```

`R-DSP-X1` ❌ бизнес-логика в контроллере (`if product.Stock == 0 { ... }`), обращения к репозиторию. `R-DSP-X2` ❌ передача `*http.Request` / `auth.Principal`-объекта в UseCase — извлекать `UserID`/`TenantID` в контроллере.

---

## 4. CQRS — `R-CQRS-*`

`R-CQRS-1`/`-3` — команды реализуют `Command[R]` (имя-глагол: `CreateOrder`, `CancelOrder`, `ConfirmPayment`), запросы — `Query[R]` (`FindOrderByID`, `SearchOrders`, `GetCustomerBalance`).

`R-CQRS-2` — команда открывает read-write транзакцию через `UnitOfWork`; запрос выполняется в read-only соединении или read-only транзакции (см. §8):

```go
// core/order/search_orders_handler.go
func (h *SearchOrdersHandler) Handle(ctx context.Context, uc SearchOrders) (OrderPage, error) {
    return h.views.Search(ctx, port.SearchFilter{
        CustomerID: uc.CustomerID,
        Status:     uc.Status,
        Page:       uc.Page,
        PageSize:   uc.PageSize,
    })
}
```

`R-CQRS-4` — чтения возвращают read-модель (`OrderView`, `OrderPage`, `CustomerSummary`) через `ViewRepository`; запись — через `OrderRepository` с агрегатом.

`R-CQRS-X1` ❌ команда возвращает `OrderView` со всеми связями — только `OrderID` / минимальный summary. `R-CQRS-X2` ❌ запрос пишет (обновляет `last_viewed_at`, счётчик просмотров) — это команда.

---

## 5. Слои моделей — `R-LAY-*`

`R-LAY-1` — на входе UseCase — поля из API-DTO или явные VO, не sqlc-struct из БД:

```go
// adapters/in/http/dto.go
type CreateOrderRequest struct {
    Items []OrderItemRequest `json:"items"`
}

type OrderItemRequest struct {
    ProductID string `json:"productId"`
    Quantity  int    `json:"quantity"`
}

func (r CreateOrderRequest) toDomainItems() []order.OrderItemInput {
    items := make([]order.OrderItemInput, len(r.Items))
    for i, it := range r.Items {
        items[i] = order.OrderItemInput{ProductID: it.ProductID, Quantity: it.Quantity}
    }
    return items
}
```

`R-LAY-2` — на выходе UseCase — read-DTO/VO, не sqlc-struct:

```go
// core/order/views.go
type OrderView struct {
    ID         string
    CustomerID string
    Status     string
    TotalCents int64
    Items      []OrderItemView
    CreatedAt  time.Time
}
```

`R-LAY-3` — маппинг — явными функциями в том слое, которому принадлежит преобразование; не один тип на все слои:

```go
// adapters/out/persistence/order_mapper.go
func toOrderView(row db.GetOrderRow) order.OrderView {
    return order.OrderView{
        ID:         row.ID.String(),
        CustomerID: row.CustomerID.String(),
        Status:     string(row.Status),
        TotalCents: row.TotalCents,
        CreatedAt:  row.CreatedAt.Time,
    }
}
```

`R-LAY-X1` ❌ sqlc-struct (`db.Order`) уходит напрямую в JSON-ответ через контроллер. `R-LAY-X3` ❌ «универсальный» маппинг через `json.Marshal` → `json.Unmarshal` или `reflect`-копирование. `R-LAY-DDD` — доменные агрегаты (`core/order/Order`) не утекают в HTTP-ответы (cross-ref `ddd-tactical/go`).

---

## 6. Hexagonal (Уровень 3) — `R-HEX-*`

`R-HEX-1` — раскладка пакетов:

```
core/
  order/               # Bounded Context
    usecases.go        # UseCase-структуры
    *_handler.go       # Handler-ы
    order.go           # Aggregate
    views.go           # read-модели
    port/
      order_repository.go
      clock.go
adapters/
  in/
    http/              # chi-роутеры, HTTP-хендлеры
  out/
    persistence/       # sqlc+pgx реализации портов
    payment/           # HTTP-клиент внешней системы
app/
  di.go                # конструкторная сборка
  dispatcher/          # dispatcher
```

`R-HEX-2` — `core/` импортирует только stdlib и свои пакеты; **не** `net/http`, `pgx`, `chi`, `kafka-go`. Проверяется тестом на импорты или `go-arch-lint`:

```go
// core/order/port/order_repository.go
package port

import (
    "context"
    "myservice/core/order" // только core — ок
)

type OrderRepository interface {
    Add(ctx context.Context, o *order.Order) error
    Get(ctx context.Context, id order.OrderID) (*order.Order, error)
}
```

`R-HEX-3` — все внешние взаимодействия за интерфейсами-портами в `core/<bc>/port/`; реализация в `adapters/out/`:

```go
// core/product/port/catalog_port.go
type CatalogPort interface {
    GetProduct(ctx context.Context, id string) (Product, error)
}

// adapters/out/catalog/catalog_client.go — реализация
type CatalogHTTPClient struct{ ... }

func (c *CatalogHTTPClient) GetProduct(ctx context.Context, id string) (product.Product, error) { ... }
```

`R-HEX-4` — Handler вызывается из HTTP-адаптера, Kafka-consumer-а и scheduler-а; Handler не дублируется:

```go
// adapters/in/http/order_handler.go  — вызывает через dispatcher
// adapters/in/kafka/order_consumer.go — тот же dispatcher.Dispatch(ctx, CreateOrder{...})
```

`R-HEX-X1` ❌ прямой `pgxpool.Pool` в `core/`. `R-HEX-X2` ❌ `import "github.com/go-chi/chi/v5"` или `import "github.com/jackc/pgx/v5"` в `core/`. Enforce — тест на импорты или `go vet -mod=mod`.

---

## 7. Step — `R-STEP-*`

`R-STEP-1` — Step = интерфейс с одним методом `Execute`; stateless:

```go
// core/usecase/step.go
package usecase

import "context"

type Step[I any, O any] interface {
    Execute(ctx context.Context, in I) (O, error)
}
```

```go
// core/order/steps/validate_inventory_step.go
type ValidateInventoryStep struct {
    catalog port.CatalogPort
}

func NewValidateInventoryStep(catalog port.CatalogPort) *ValidateInventoryStep {
    return &ValidateInventoryStep{catalog: catalog}
}

func (s *ValidateInventoryStep) Execute(ctx context.Context, items []OrderItemInput) error {
    for _, item := range items {
        product, err := s.catalog.GetProduct(ctx, item.ProductID)
        if err != nil {
            return fmt.Errorf("validate inventory: %w", err)
        }
        if product.Stock < item.Quantity {
            return &InsufficientStockError{ProductID: item.ProductID, Requested: item.Quantity, Available: product.Stock}
        }
    }
    return nil
}
```

`R-STEP-2` — Step вводится, когда одна логика нужна ≥ 2 Handler-ам (например, `ValidateInventoryStep` используется в `CreateOrderHandler` и `ReserveStockHandler`).

`R-STEP-X1` ❌ Step внутри Step — это уже логика Handler-а. `R-STEP-X2` ❌ Step с полями, меняющимися между вызовами.

---

## 8. Транзакции и события — `R-TX-*`

`R-TX-1` — граница транзакции на Handler через `UnitOfWork`-порт; репозиторий не знает о транзакции снаружи него:

```go
// core/order/port/unit_of_work.go
type UnitOfWork interface {
    Do(ctx context.Context, fn func(ctx context.Context) error) error
}

// adapters/out/persistence/pgx_uow.go
type PgxUnitOfWork struct{ pool *pgxpool.Pool }

func (u *PgxUnitOfWork) Do(ctx context.Context, fn func(ctx context.Context) error) error {
    tx, err := u.pool.Begin(ctx)
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    txCtx := context.WithValue(ctx, txKey{}, tx)
    if err := fn(txCtx); err != nil {
        _ = tx.Rollback(ctx)
        return err
    }
    return tx.Commit(ctx)
}
```

Handler команды:

```go
func (h *CreateOrderHandler) Handle(ctx context.Context, uc CreateOrder) (OrderID, error) {
    var id OrderID
    err := h.uow.Do(ctx, func(ctx context.Context) error {
        o, err := NewOrder(uc.CustomerID, uc.Items, h.clock.Now())
        if err != nil {
            return err
        }
        if err := h.orders.Add(ctx, o); err != nil {
            return fmt.Errorf("add order: %w", err)
        }
        id = o.ID
        return nil
    })
    return id, err
}
```

Handler запроса — без транзакции (read-only соединение напрямую или read-only tx):

```go
func (h *FindOrderByIDHandler) Handle(ctx context.Context, uc FindOrderByID) (OrderView, error) {
    return h.views.FindByID(ctx, uc.ID)
}
```

`R-TX-2` — один UseCase = одна транзакция; Saga — оркестратор в Handler, каждый шаг — отдельный UseCase / внешний вызов с Outbox (cross-ref `distributed/go`):

```go
// Saga-оркестратор в Handler, НЕ вложенные транзакции
func (h *ConfirmOrderHandler) Handle(ctx context.Context, uc ConfirmOrder) (VoidResult, error) {
    err := h.uow.Do(ctx, func(ctx context.Context) error {
        if err := h.orders.UpdateStatus(ctx, uc.OrderID, StatusConfirmed); err != nil {
            return err
        }
        return h.outbox.Publish(ctx, OrderConfirmedEvent{OrderID: uc.OrderID})
    })
    return VoidResult{}, err
}
```

`R-TX-3` — публикация доменных событий (Уровень 3) — после `repository.Add/Save`, затем `aggregate.ClearEvents()` (cross-ref `ddd-tactical/go`):

```go
if err := h.orders.Save(ctx, order); err != nil {
    return VoidResult{}, fmt.Errorf("save order: %w", err)
}
for _, ev := range order.Events() {
    if err := h.outbox.Publish(ctx, ev); err != nil {
        return VoidResult{}, fmt.Errorf("publish event: %w", err)
    }
}
order.ClearEvents()
```

---

## Чеклист подключения к новому сервису (Go)

- [ ] `core/usecase/usecase.go`: интерфейсы-маркеры `Command[R]` / `Query[R]` и `Handler[UC, R]`
- [ ] UseCase — plain struct, без методов-логики, без сеттеров; имя по бизнес-операции
- [ ] Handler — `*NamedHandler` с `Handle(ctx, UC) (R, error)`, deps через конструктор `New*`, поля приватные
- [ ] `Dispatcher` (`app/dispatcher/`) с реестром `reflect.Type → handlerFunc`; `Register[UC, R]` при сборке; один dispatcher на приложение
- [ ] Контроллер тонкий: JSON-Request → UseCase → `dispatcher.Dispatch` → Response; `UserID` из `auth.PrincipalFromCtx`, не из тела запроса
- [ ] API-DTO (`adapters/in/http/dto.go`) с методом `toDomainItems()` / `toDomain*()`; sqlc-struct в `adapters/out/persistence/`; явный маппер между ними
- [ ] Порты — интерфейсы в `core/<bc>/port/`; `core/` не импортирует `pgx`/`chi`/`kafka-go`; enforce тестом на импорты
- [ ] CQRS: команда через `UnitOfWork.Do` (read-write tx) → возвращает ID/VoidResult; запрос read-only → возвращает View
- [ ] `UnitOfWork`-порт в `core/`, реализация `PgxUnitOfWork` в `adapters/out/persistence/`; граница TX на Handler
- [ ] Инфра-ошибки (`pgconn.PgError`, `net.Error`, `context.DeadlineExceeded`) маппятся в доменные/интеграционные в адаптере (cross-ref `error-handling/go`)
- [ ] Конструкторная сборка в `app/di.go`; `Register` для каждого Handler-а; `google/wire` — опционально
- [ ] Step (`core/usecase/step.go`) — только если логика используется ≥ 2 Handler-ами; Step без состояния
- [ ] Публикация доменных событий через Outbox после `repository.Save` внутри той же UoW-транзакции (cross-ref `distributed/go`)
