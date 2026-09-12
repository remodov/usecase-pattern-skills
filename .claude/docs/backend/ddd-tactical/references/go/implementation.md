# ddd-tactical — реализация на Go (net/http + chi)

Реализация контракта `../spec.md` (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`) на Go-стеке
(stdlib `net/http` + chi + sqlc + pgx/v5). Коды правил — общие с Java/Python; здесь — как они выглядят в
Go-сервисе. Домен живёт в `core/` **без фреймворка и без ORM** — чистый Go + stdlib; инфраструктурный слой
(sqlc, pgx, chi) строго в `adapters/`.

В Go нет классового наследования — базовые типы реализуются через **встраивание структур** (embedding).
Идиомы: VO и событие — immutable structs с value-equality; Entity — struct с identity-equality (embedding
`EntityBase[ID]`); Aggregate Root — Entity + срез событий; ошибки — значения-типы с `Kind()` (cross-ref
`error-handling/go`).

```go
// core/shared/building_blocks.go
package shared

import (
    "time"

    "github.com/google/uuid"
)

type EntityBase[ID comparable] struct {
    id ID
}

func NewEntityBase[ID comparable](id ID) EntityBase[ID] {
    return EntityBase[ID]{id: id}
}

func (e EntityBase[ID]) ID() ID { return e.id }

func (e EntityBase[ID]) Equals(other EntityBase[ID]) bool {
    return e.id == other.id
}

type DomainEvent interface {
    EventID() uuid.UUID
    OccurredAt() time.Time
    AggregateID() uuid.UUID
}

type AggregateBase[ID comparable] struct {
    EntityBase[ID]
    events []DomainEvent
}

func NewAggregateBase[ID comparable](id ID) AggregateBase[ID] {
    return AggregateBase[ID]{EntityBase: NewEntityBase[ID](id)}
}

func (a *AggregateBase[ID]) registerEvent(ev DomainEvent) {
    a.events = append(a.events, ev)
}

func (a *AggregateBase[ID]) PullEvents() []DomainEvent {
    evs := make([]DomainEvent, len(a.events))
    copy(evs, a.events)
    a.events = a.events[:0]
    return evs
}
```

---

## 1. Entity — `R-ENT-*`

`ddd-tactical/entity-equality-by-identity` — Entity встраивает `EntityBase[ID]` (или живёт внутри агрегата как private struct). `ddd-tactical/identity-is-immutable`/
`ddd-tactical/identity-is-immutable` — идентификатор задаётся при создании через конструктор `New…`, меняется только через embedded
`EntityBase`; публичного сеттера нет. `ddd-tactical/entity-equality-by-identity` — equality через `EntityBase.Equals(other.EntityBase)`, не
через `==` по всем полям; `==` на struct в Go сравнивает все поля — для Entity это неверно. `ddd-tactical/entity-constructor-validates` —
конструктор (`NewOrderLine(…)`) валидирует инварианты и возвращает `(*OrderLine, error)`.

```go
// core/order/entity/order_line.go
package entity

import (
    "fmt"

    "github.com/google/uuid"
    "example.com/svc/core/order/vo"
    "example.com/svc/core/shared"
)

type OrderLine struct {
    shared.EntityBase[uuid.UUID]
    productID vo.ProductID
    qty       int
    price     vo.Money
}

func NewOrderLine(id uuid.UUID, productID vo.ProductID, qty int, price vo.Money) (*OrderLine, error) {
    if qty <= 0 {
        return nil, fmt.Errorf("qty must be positive")
    }
    return &OrderLine{
        EntityBase: shared.NewEntityBase[uuid.UUID](id),
        productID:  productID,
        qty:        qty,
        price:      price,
    }, nil
}

func (l *OrderLine) Subtotal() vo.Money {
    return l.price.Multiply(l.qty)
}
```

`ddd-tactical/entity-equality-by-identity` ❌ не переопределяй equality через `==` по всем полям struct — это VO-семантика.
`ddd-tactical/entity-equality-by-identity` ❌ не сравнивай Entity через глубокое `reflect.DeepEqual` — только `.Equals()` по id.
`ddd-tactical/entity-constructor-validates` ❌ публичные сеттеры на все поля (`line.Qty = 5`) — состояние меняется бизнес-методами.
`ddd-tactical/no-object-references-across-aggregates` ❌ ссылка на другой агрегат объектом — только по id (`customerID CustomerID`, не `*Customer`).
`ddd-tactical/model-is-not-anemic` ❌ анемичная модель: одни геттеры, логика вынесена в сервисы.

> В Go `struct`-embedding не транзитивно наследует `==`: два `*OrderLine` с одинаковыми полями всё равно
> разные указатели. Для pointer-receiver equality всегда используй явный `.Equals()`.

---

## 2. Value Object — `R-VO-*`

`ddd-tactical/value-object-is-immutable`/`ddd-tactical/value-object-is-immutable` — VO = immutable struct без публичных сеттеров; все поля приватны, доступ через методы.
`ddd-tactical/value-equality-by-all-fields` — equality достигается `==` (работает корректно, если все поля comparable — для VO так и есть).
`ddd-tactical/value-validates-on-creation` — конструктор-фабрика `NewMoney(…)` проверяет инварианты. `ddd-tactical/value-object-is-immutable` — мутирующие операции
возвращают новый экземпляр.

```go
// core/order/vo/money.go
package vo

import (
    "fmt"

    "github.com/shopspring/decimal"
)

type Money struct {
    amount   decimal.Decimal
    currency string
}

func NewMoney(amount decimal.Decimal, currency string) (Money, error) {
    if amount.IsNegative() {
        return Money{}, fmt.Errorf("amount must be non-negative")
    }
    if len(currency) != 3 {
        return Money{}, fmt.Errorf("currency must be ISO-4217")
    }
    return Money{amount: amount, currency: currency}, nil
}

func (m Money) Amount() decimal.Decimal { return m.amount }
func (m Money) Currency() string        { return m.currency }

func (m Money) Multiply(factor int) Money {
    return Money{amount: m.amount.Mul(decimal.NewFromInt(int64(factor))), currency: m.currency}
}

func (m Money) Add(other Money) (Money, error) {
    if m.currency != other.currency {
        return Money{}, fmt.Errorf("currency mismatch: %s vs %s", m.currency, other.currency)
    }
    return Money{amount: m.amount.Add(other.amount), currency: m.currency}, nil
}
```

```go
// core/order/vo/product_id.go
package vo

import "github.com/google/uuid"

type ProductID struct{ value uuid.UUID }

func NewProductID(v uuid.UUID) ProductID { return ProductID{value: v} }
func (p ProductID) Value() uuid.UUID     { return p.value }
```

`ddd-tactical/value-has-no-identity` ❌ id или жизненный цикл у VO — VO без identity, нет `CreatedAt`, нет `Save()`.
`ddd-tactical/no-primitive-obsession` ❌ primitive obsession: `string` вместо `Email`, `float64` вместо `Money` — заворачивай.
`ddd-tactical/collections-in-values-are-protected` ❌ мутабельный slice внутри VO: `[]string tags` — используй `[N]string` или не экспонируй напрямую.

> Деньги — **`shopspring/decimal`**, никогда `float64` (нарушение IEEE 754 на сложении cents). Для
> высоконагруженных систем допустим `int64` в минорных единицах (копейки), но тогда это оговаривается явно
> в доменном словаре.

---

## 3. Aggregate Root — `R-AGG-*`

`ddd-tactical/aggregate-root-is-single-entry` — корень встраивает `AggregateBase[ID]`. `ddd-tactical/aggregate-root-is-single-entry` — внешние операции только через методы корня;
внутренние Entity наружу — копией (`lines()` возвращает `[]OrderLine`, не `[]*OrderLine`). `ddd-tactical/events-registered-by-root` —
события регистрируются в момент изменения состояния через `a.registerEvent(…)`, не в репозитории.
`ddd-tactical/transaction-boundary-equals-aggregate` — один use case меняет один агрегат; влияние на другие агрегаты — через события. `ddd-tactical/no-object-references-across-aggregates` —
ссылки на другие агрегаты по id.

```go
// core/order/aggregate/order.go
package aggregate

import (
    "fmt"
    "time"

    "github.com/google/uuid"
    "example.com/svc/core/order/entity"
    "example.com/svc/core/order/event"
    "example.com/svc/core/order/vo"
    "example.com/svc/core/shared"
)

type OrderStatus int

const (
    OrderStatusNew OrderStatus = iota + 1
    OrderStatusConfirmed
)

type Order struct {
    shared.AggregateBase[uuid.UUID]
    customerID vo.CustomerID
    status     OrderStatus
    lines      []*entity.OrderLine
}

func NewOrder(id uuid.UUID, customerID vo.CustomerID) *Order {
    o := &Order{
        AggregateBase: shared.NewAggregateBase[uuid.UUID](id),
        customerID:    customerID,
        status:        OrderStatusNew,
    }
    o.registerEvent(event.NewOrderCreated(uuid.New(), time.Now(), id))
    return o
}

func (o *Order) AddLine(line *entity.OrderLine) error {
    if o.status != OrderStatusNew {
        return fmt.Errorf("cannot modify confirmed order")
    }
    o.lines = append(o.lines, line)
    return nil
}

func (o *Order) Confirm(clock func() time.Time) error {
    if len(o.lines) == 0 {
        return fmt.Errorf("cannot confirm empty order")
    }
    o.status = OrderStatusConfirmed
    total := o.total()
    o.registerEvent(event.NewOrderConfirmed(uuid.New(), clock(), o.ID(), o.customerID.Value(), total.Amount(), total.Currency()))
    return nil
}

func (o *Order) total() vo.Money {
    var result vo.Money
    for _, l := range o.lines {
        sub := l.Subtotal()
        if m, err := result.Add(sub); err == nil {
            result = m
        }
    }
    return result
}

func (o *Order) Lines() []entity.OrderLine {
    result := make([]entity.OrderLine, 0, len(o.lines))
    for _, l := range o.lines {
        result = append(result, *l)
    }
    return result
}

func (o *Order) CustomerID() vo.CustomerID { return o.customerID }
func (o *Order) Status() OrderStatus       { return o.status }
```

`ddd-tactical/aggregate-stays-small` ❌ «God aggregate» с 20+ методами и 15+ полями — дробить по границам домена.
`ddd-tactical/aggregate-root-is-single-entry` ❌ `return o.lines` — возврат внутреннего slice (клиент append'ит, меняет состояние); всегда копия.
`ddd-tactical/transaction-boundary-equals-aggregate` ❌ менять поля чужого агрегата напрямую (`other.status = …` из метода этого агрегата).
`ddd-tactical/events-registered-by-root` ❌ регистрировать события вне корня — в Handler, репозитории или контроллере.

---

## 4. Domain Event — `R-EVT-*`

`ddd-tactical/event-is-immutable-record` — событие реализует интерфейс `DomainEvent` (несёт `EventID`/`OccurredAt`/`AggregateID`).
`ddd-tactical/event-named-in-past-tense` — имя глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderEvent`).
`ddd-tactical/event-is-immutable-record` — иммутабельно: struct с приватными полями, только геттеры. `ddd-tactical/event-carries-business-context` — несёт бизнес-контекст
значениями (id, сумма, статус), не сам агрегат. `ddd-tactical/events-published-after-save` — публикуются после сохранения агрегата,
затем `PullEvents()` очищает их (cross-ref `usecase-pattern/publish-events-after-save`, pattern-design).

```go
// core/order/event/order_confirmed.go
package event

import (
    "time"

    "github.com/google/uuid"
    "github.com/shopspring/decimal"
)

type OrderConfirmed struct {
    eventID     uuid.UUID
    occurredAt  time.Time
    orderID     uuid.UUID
    customerID  uuid.UUID
    total       decimal.Decimal
    currency    string
}

func NewOrderConfirmed(
    eventID uuid.UUID,
    occurredAt time.Time,
    orderID uuid.UUID,
    customerID uuid.UUID,
    total decimal.Decimal,
    currency string,
) OrderConfirmed {
    return OrderConfirmed{
        eventID:    eventID,
        occurredAt: occurredAt,
        orderID:    orderID,
        customerID: customerID,
        total:      total,
        currency:   currency,
    }
}

func (e OrderConfirmed) EventID() uuid.UUID          { return e.eventID }
func (e OrderConfirmed) OccurredAt() time.Time       { return e.occurredAt }
func (e OrderConfirmed) AggregateID() uuid.UUID      { return e.orderID }
func (e OrderConfirmed) CustomerID() uuid.UUID       { return e.customerID }
func (e OrderConfirmed) Total() decimal.Decimal      { return e.total }
func (e OrderConfirmed) Currency() string            { return e.currency }
```

`ddd-tactical/event-is-immutable-record` ❌ менять поля события после создания — struct с публичными полями, изменяемыми снаружи.
`ddd-tactical/event-carries-business-context` ❌ ссылка на агрегат/Entity в событии — только примитивы, VO и id.
`ddd-tactical/events-published-after-save` ❌ публиковать из контроллера/Handler — только корень регистрирует через `registerEvent`.
`ddd-tactical/no-after-commit-for-critical-effects` ❌ доставлять критичные эффекты «after commit» горутиной (теряется при крэше) — Outbox в той
же транзакции (cross-ref `R-SQLC-*`, outbox-pattern).

---

## 5. Repository — `R-REP-*`

`ddd-tactical/repository-port-in-domain` — порт репозитория — interface в `core/<bc>/port/`, типизирован агрегатом. `ddd-tactical/repository-port-in-domain` —
реализация в `adapters/out/persistence/` (sqlc + pgx); домен не знает про SQL. `ddd-tactical/repository-per-aggregate-root` — один
репозиторий = один корень. `ddd-tactical/repository-per-aggregate-root` — `Save` сохраняет агрегат целиком; публикация событий через
publisher и `PullEvents()` — на границе транзакции. `ddd-tactical/repository-speaks-domain` — методы в терминах домена.

```go
// core/order/port/order_repository.go
package port

import (
    "context"

    "github.com/google/uuid"
    "example.com/svc/core/order/aggregate"
)

type OrderRepository interface {
    ByID(ctx context.Context, id uuid.UUID) (*aggregate.Order, error)
    Save(ctx context.Context, order *aggregate.Order) error
    ActiveByCustomer(ctx context.Context, customerID uuid.UUID) ([]*aggregate.Order, error)
}
```

```go
// adapters/out/persistence/order_repository.go
package persistence

import (
    "context"
    "fmt"

    "github.com/google/uuid"
    "github.com/jackc/pgx/v5/pgxpool"
    "example.com/svc/adapters/out/persistence/sqlcgen"
    "example.com/svc/core/order/aggregate"
    "example.com/svc/core/order/port"
)

type pgOrderRepository struct {
    pool    *pgxpool.Pool
    queries *sqlcgen.Queries
}

func NewOrderRepository(pool *pgxpool.Pool) port.OrderRepository {
    return &pgOrderRepository{pool: pool, queries: sqlcgen.New(pool)}
}

func (r *pgOrderRepository) ByID(ctx context.Context, id uuid.UUID) (*aggregate.Order, error) {
    row, err := r.queries.GetOrder(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("order by id %s: %w", id, err)
    }
    return toAggregate(row), nil
}

func (r *pgOrderRepository) Save(ctx context.Context, order *aggregate.Order) error {
    tx, err := r.pool.Begin(ctx)
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx)

    q := r.queries.WithTx(tx)
    if err := upsertOrder(ctx, q, order); err != nil {
        return err
    }
    return tx.Commit(ctx)
}
```

`ddd-tactical/repository-speaks-domain` ❌ возвращать `sqlcgen.Order` (row-struct) наружу — домен получает sqlc-артефакт.
`ddd-tactical/repository-speaks-domain` ❌ методы под одну таблицу (`UpdateStatusInDB`) — терминология домена, не схемы.
`ddd-tactical/specification-is-not-a-query-builder` ❌ Specification, генерирующая SQL-предикат в порте — для read-side отдельный ViewRepository
(cross-ref `usecase-pattern/reads-via-read-model`).

---

## 6. Domain Service — `R-DS-*`

`ddd-tactical/domain-service-only-across-aggregates` — Domain Service только если логика касается ≥ 2 агрегатов и не помещается в один корень.
`ddd-tactical/domain-service-only-across-aggregates` — stateless struct; конструктор принимает только доменные зависимости (не репозитории, не
HTTP-клиенты). `ddd-tactical/domain-service-only-across-aggregates` — имя — доменная операция.

```go
// core/transfer/service/transfer_service.go
package service

import (
    "example.com/svc/core/account/aggregate"
    "example.com/svc/core/order/vo"
)

type TransferService struct{}

func (TransferService) Transfer(src, dst *aggregate.Account, amount vo.Money) error {
    if err := src.Withdraw(amount); err != nil {
        return err
    }
    return dst.Deposit(amount)
}
```

`ddd-tactical/domain-service-only-across-aggregates` ❌ оркестрация в Domain Service: загрузка из репозитория, транзакции, публикация событий —
это слой Application (Handler). Domain Service работает с уже загруженными объектами.
`ddd-tactical/domain-service-only-across-aggregates` ❌ Domain Service как свалка всей бизнес-логики, оставляющая агрегаты анемичными.

---

## 7. Factory — `R-FAC-*`

`ddd-tactical/factory-only-when-needed` — Factory (функция / метод пакета `aggregate`) вводится, только когда конструктор не справляется:
сборка из нескольких источников, выбор подтипа, генерация ID. `ddd-tactical/factory-only-when-needed` — возвращает уже валидный агрегат
с начальными событиями и ошибку; невалидный агрегат не возвращается.

```go
// core/order/aggregate/order_factory.go
package aggregate

import (
    "fmt"
    "time"

    "github.com/google/uuid"
    "example.com/svc/core/order/vo"
)

type CreateOrderParams struct {
    CustomerID vo.CustomerID
    Clock      func() time.Time
    NewID      func() uuid.UUID
}

func CreateOrder(p CreateOrderParams) (*Order, error) {
    if p.CustomerID == (vo.CustomerID{}) {
        return nil, fmt.Errorf("customerID is required")
    }
    return NewOrder(p.NewID(), p.CustomerID), nil
}
```

`ddd-tactical/factory-only-when-needed` ❌ Factory ради Factory — если хватает `NewOrder(id, customerID)`, не плодить слой.

---

## 8. Specification — `R-SPEC-*`

`ddd-tactical/specification-for-reuse` — спецификация — struct с методом `IsSatisfiedBy(candidate T) bool`. Для комбинирования —
методы `And`/`Or`/`Not` через обёртки. `ddd-tactical/specification-for-reuse` — вводится только когда правило применяется в ≥ 2
местах или нужна комбинация.

```go
// core/order/specification/eligible_for_discount.go
package specification

import (
    "example.com/svc/core/order/aggregate"
    "example.com/svc/core/order/vo"
)

type EligibleForDiscount struct {
    Threshold vo.Money
}

func (s EligibleForDiscount) IsSatisfiedBy(order *aggregate.Order) bool {
    total, _ := order.Total()
    return total.Amount().GreaterThanOrEqual(s.Threshold.Amount())
}
```

`ddd-tactical/specification-is-not-a-query-builder` ❌ Specification для генерации SQL-предиката (передаётся в репозиторий как WHERE-строитель).
`ddd-tactical/specification-for-reuse` ❌ Specification ради одного `if` в одном месте — преждевременная абстракция.

---

## 9. Module (структура пакетов) — `R-MOD-*`

Группировка по домену, не по типу:

```
core/
  shared/
    building_blocks.go          // EntityBase, AggregateBase, DomainEvent-interface
  <bounded-context>/            // например: order/, product/, customer/
    aggregate/                  // AggregateRoot
    entity/                     // внутренние Entity
    vo/                         // Value Objects
    event/                      // DomainEvent-реализации
    port/                       // интерфейсы-порты (repository, publisher, external)
    service/                    // Domain Service (опционально)
    specification/              // Specification (опционально)
    usecase/                    // UseCase + Handler (command/query)
adapters/
  in/http/                      // chi-роутер, handlers, DTOs
  out/persistence/              // sqlc-gen + pgx-репозитории
  out/messaging/                // kafka-producer
app/
  wire.go                       // ручная конструкторная сборка (или google/wire)
```

`ddd-tactical/packages-grouped-by-domain` — запрещено `entity/`, `service/`, `repository/` на верхнем уровне `core/` — только по
Bounded Context. Пакет `core/entity/` — ошибка: нарушает изоляцию контекстов.

`ddd-tactical/packages-grouped-by-domain` — домен (`core/<bc>/`) не импортирует `adapters/*`, chi, pgx, sqlc, Prometheus. Enforce
через `golang.org/x/tools/go/analysis` или `depguard`-линтер: `core` → `shared` разрешено;
`core` → `adapters` запрещено. Структура импортов: `core` < `adapters` < `app`.

> Канонический способ enforce: линтер `depguard` с правилом `denyPackages` или `go-arch-lint`. Без
> enforce граница медленно размывается «для скорости».

---

## 10. Чеклист подключения к новому сервису (Go)

- [ ] `core/shared/building_blocks.go` — `EntityBase[ID]`, `AggregateBase[ID]`, интерфейс `DomainEvent`.
- [ ] Entity встраивает `EntityBase[ID]`; конструктор `New…` возвращает `(*Entity, error)`; публичных сеттеров нет.
- [ ] VO — immutable struct, все поля приватны, конструктор-фабрика `New…` с проверкой инвариантов, мутирующие методы возвращают новый экземпляр.
- [ ] Aggregate Root встраивает `AggregateBase[ID]`; наружу — копии коллекций; `Lines()` возвращает `[]OrderLine`, не slice указателей.
- [ ] События реализуют интерфейс `DomainEvent`; struct с приватными полями + геттерами; имя в прошедшем времени.
- [ ] События регистрируются в корне агрегата (`registerEvent`), публикуются после `Save` через `PullEvents()`.
- [ ] Порт репозитория — interface в `core/<bc>/port/`; реализация в `adapters/out/persistence/` (sqlc + pgx).
- [ ] `Save` сохраняет агрегат в транзакции; события — через Outbox или синхронный publisher до `Commit`.
- [ ] Ссылки между агрегатами — только по id (VO-обёртка над `uuid.UUID`).
- [ ] Domain Service — только если логика касается ≥ 2 агрегатов; stateless struct.
- [ ] Factory — только при сложной сборке агрегата; возвращает `(*Aggregate, error)`.
- [ ] Деньги — `shopspring/decimal` или `int64` в минорных единицах, не `float64`.
- [ ] `core/<bc>/` не импортирует `adapters/*` — проверить `depguard` или `go-arch-lint` в CI.
- [ ] Пакеты по Bounded Context (`core/order/…`), не по типу (`core/entity/…`).
