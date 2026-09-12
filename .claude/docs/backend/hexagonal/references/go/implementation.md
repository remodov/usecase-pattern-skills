# Hexagonal Architecture — реализация на Go (net/http + chi)

Реализация контракта `../spec.md` (коды `R-HEX-WHEN-*`, `R-HEX-MOD-*`, `R-HEX-CORE-*`, `R-HEX-PORT-*`, `R-HEX-AIN-*`, `R-HEX-AOUT-*`, `R-HEX-BOOT-*`, `R-HEX-TEST-*`).
Коды общие с Java/Python; меняется **механизм изоляции**: вместо Gradle-модулей и ArchUnit — Go-пакеты с тестом
`go vet` + кастомным `golangci-lint`-плагином (или ручным `govulncheck`-style scan) и строгим package-конвенционом.
В Go нет compile-time module-isolation внутри одного репо (без Go Workspaces), поэтому enforcement — архитектурный тест
(`go test ./...` c `goarchtest`/`godepgraph` или простой проверкой `go list -deps`) в CI. Ошибки — значения (`apperr`),
не исключения (cross-ref `error-handling/references/go/implementation.md`).

---

## 1. Когда переходить (`R-HEX-WHEN-*`)

`hexagonal/level-three-only` — Hexagonal = Уровень 3 (DDD + ports/adapters + архитектурный CI-тест). Уровень 1–2 — overkill:
плоский `internal/<bc>/` без слоёв.

`hexagonal/level-three-only` — признаки «пора»: несколько внешних систем (Sber + ОднаКасса + Redis), нужны unit-тесты core без
поднятия базы/HTTP, разные in-adapter'ы (REST + Kafka-consumer) для одного домена.

`hexagonal/level-three-only` — признаки «рано»: 3–5 эндпоинтов, один выход (Postgres), монопользователь команды — полный каркас
добавит ceremony без выгоды.

`hexagonal/level-three-only` ❌ Cargo-cult: сервис из 3 хендлеров в полной hex-раскладке. Ceremony без выгоды.

`hexagonal/no-partial-adoption` ❌ Частичный Hexagonal: `core/` есть, но `handler.go` в `adapter/in/http/` читает из репозитория
напрямую. Либо полностью, либо плоский `internal/`.

---

## 2. Структура пакетов (`R-HEX-MOD-*`)

Вместо Gradle-модулей — пакеты с конвенцией импортов. `hexagonal/module-per-part`/`hexagonal/core-free-of-framework` — `core/` не импортирует ничего
инфраструктурного:

```
internal/
  core/<bc>/{aggregate,entity,value_object,event,port,usecase,service}/
  adapter/in/http/                   # chi-роутеры + middleware (R-HEX-AIN)
  adapter/in/kafka/                  # kafka-consumer (отдельный пакет на тип входа)
  adapter/out/persistence/           # sqlc + pgx (R-HEX-AOUT)
  adapter/out/<system>/              # httpx-клиент к внешней системе (per-system)
bootstrap/
  main.go                            # composition root: wire, chi.Router, http.Server
  config.go                          # envconfig
  Dockerfile
```

`hexagonal/module-per-part`/`hexagonal/module-per-part` — каждый out-adapter и каждый in-adapter — **отдельный пакет** (`adapter/out/sber/`,
`adapter/out/payment/`). Не складывать оба REST-входа (user + admin) в один `adapter/in/http/` без разделения:

```
adapter/in/http/
  user/          # R-HEX-MOD-4: user-router (аутентификация пользователя)
  admin/         # admin-router (отдельный middleware auth)
```

`R-HEX-MOD-5` — `bootstrap/main.go` — единственное место, где импортируются все адаптеры вместе. Никто не зависит
от `bootstrap/`.

`hexagonal/module-per-part` ❌ Всё в одном пакете `internal/<bc>/` с подпапками без enforcement-импортов. Нет ни compile-time,
ни архитектурного теста — нарушения никто не поймает.

`hexagonal/core-free-of-framework` ❌ `core/<bc>/` импортирует `adapter/out/persistence/` (strelka inverted). Стрелка всегда:
`bootstrap → adapter/* → core`.

`hexagonal/in-adapter-per-audience` ❌ User- и admin-роутеры в одном пакете без разделения — теряется compile-time изоляция
security-мидлвар.

---

## 3. Core (`R-HEX-CORE-*`)

`hexagonal/core-free-of-framework` — `core/<bc>/` зависит **только от**:
- stdlib Go (`context`, `errors`, `time`, `fmt`)
- `core/apperr` (domain-ошибки)
- других пакетов `core/<bc2>/` (кросс-BC через port, не прямые импорты aggregate)

`hexagonal/core-structure` — структура core:

```
core/order/
  aggregate/      order.go           # Order aggregate (rich domain)
  value_object/   money.go           # Money VO
  event/          order_confirmed.go # OrderConfirmed domain event
  port/out/       payment_port.go    # PaymentPort interface
                  order_repo.go      # OrderRepository interface
  usecase/        confirm_order.go   # ConfirmOrderUseCase + ConfirmOrderCommand
  service/        pricing_service.go # Domain Service (если нужен cross-aggregate)
```

`hexagonal/rich-domain-model` — rich domain: логика в агрегате, не в `*Service`:

```go
// core/order/aggregate/order.go
package aggregate

type Order struct {
    id         OrderID
    customerID CustomerID
    items      []OrderItem
    status     Status
    total      Money
}

func (o *Order) Confirm(payment PaymentResult) error {
    if o.status != StatusPending {
        return &InvalidStatusTransitionError{From: o.status, To: StatusConfirmed}
    }
    if payment.Amount.IsLessThan(o.total) {
        return &InsufficientPaymentError{Required: o.total, Provided: payment.Amount}
    }
    o.status = StatusConfirmed
    return nil
}
```

`hexagonal/di-annotations-in-core` — DI-аннотации в Go нет; core — чистые структуры + интерфейсы. Wiring — только в `bootstrap/`.

`hexagonal/core-free-of-framework` ❌ Импорт `chi`, `pgx`, `slog` в `core/`. Enforce через архитектурный тест (§8).

`hexagonal/core-free-of-framework` ❌ Импорт `jackc/pgx` / sqlc-generated types в `core/`. Persistence — деталь `adapter/out/persistence/`;
маппинг — `persistence/<X>_mapper.go`.

`hexagonal/rich-domain-model` ❌ Анемичный агрегат — только поля + геттеры, логика в `OrderService`. Процедурный стиль в DDD-обёртке.

`hexagonal/no-generated-types-in-core` ❌ Sqlc-generated struct (напр. `db.Order`) как доменный тип в `core/`. Это persistence-деталь;
в core — доменная структура `aggregate.Order`.

`hexagonal/no-generated-types-in-core` ❌ HTTP-DTO (`CreateOrderRequest`) в `core/`. REST-DTO — деталь `adapter/in/http/`; в core — `usecase.ConfirmOrderCommand`.

---

## 4. Ports (`R-HEX-PORT-*`)

`hexagonal/outbound-port-interface-in-core` — outbound-порт = **`interface`** в `core/<bc>/port/out/`, описывает что нужно core (cross-ref
`R-ERR-HIER-*` для port-ошибок):

```go
// core/order/port/out/payment_port.go
package out

type PaymentPort interface {
    Register(ctx context.Context, cmd RegisterPaymentCommand) (RegisterPaymentResult, error)
    Cancel(ctx context.Context, paymentID PaymentID) error
}

type RegisterPaymentCommand struct {
    OrderID    OrderID
    CustomerID CustomerID
    Amount     Money
}

type RegisterPaymentResult struct {
    PaymentID  PaymentID
    ConfirmedAt time.Time
}
```

`hexagonal/port-speaks-domain-types` — port-методы оперируют domain-типами (`Money`, `OrderID`), не DTO внешней системы (`SberRegisterRequest`).

`hexagonal/port-exceptions-in-core` — port-ошибки объявлены в `core/`:

```go
// core/order/port/out/errors.go
package out

type PaymentPortError struct {
    Op  string
    Err error
}

func (e *PaymentPortError) Error() string { return "payment port: " + e.Op + ": " + e.Err.Error() }
func (e *PaymentPortError) Unwrap() error { return e.Err }
func (e *PaymentPortError) Kind() apperr.Kind { return apperr.Integration }
```

Подклассы системы — в адаптере:

```go
// adapter/out/sber/errors.go
type SberError struct{ Op string; Err error }
func (e *SberError) Unwrap() error             { return e.Err }
func (e *SberError) Kind() apperr.Kind         { return apperr.Integration }
```

Handler ловит `*out.PaymentPortError` через `errors.As`, не `*SberError`.

`hexagonal/inbound-port-is-use-case` — inbound-порт = UseCase + Handler (вход через `Dispatcher`), отдельный «InboundPort» interface не нужен:

```go
// core/order/usecase/confirm_order.go
package usecase

type ConfirmOrderCommand struct {
    OrderID    OrderID
    PaymentRef string
}

type ConfirmOrderHandler struct {
    orders   out.OrderRepository
    payments out.PaymentPort
}

func NewConfirmOrderHandler(orders out.OrderRepository, payments out.PaymentPort) *ConfirmOrderHandler {
    return &ConfirmOrderHandler{orders: orders, payments: payments}
}

func (h *ConfirmOrderHandler) Handle(ctx context.Context, cmd ConfirmOrderCommand) error {
    order, err := h.orders.FindByID(ctx, cmd.OrderID)
    if err != nil {
        return fmt.Errorf("load order %s: %w", cmd.OrderID, err)
    }
    result, err := h.payments.Register(ctx, out.RegisterPaymentCommand{
        OrderID: cmd.OrderID, Amount: order.Total(),
    })
    if err != nil {
        return fmt.Errorf("register payment: %w", err)
    }
    if err := order.Confirm(result); err != nil {
        return err
    }
    return h.orders.Save(ctx, order)
}
```

`hexagonal/outbound-port-interface-in-core` ❌ Interface `PaymentPort` объявлен в `adapter/out/sber/` — порт-контракт живёт в `core/`.

`hexagonal/port-speaks-domain-types` ❌ `PaymentPort.Register(ctx, SberRequest)` — DTO внешней системы в сигнатуре. Адаптер мапит
`RegisterPaymentCommand → SberRequest` внутри.

`hexagonal/absence-is-not-error` ❌ `(Order, bool)` из порта, где `false` = «не найдено». Возвращай ошибку с domain-смыслом:

```go
// PREFER
type OrderNotFoundError struct{ OrderID OrderID }
func (e *OrderNotFoundError) Error() string   { return "order not found: " + string(e.OrderID) }
func (e *OrderNotFoundError) Kind() apperr.Kind { return apperr.Domain }

// AVOID
func (r *OrderRepo) FindByID(ctx context.Context, id OrderID) (Order, bool, error)
```

`hexagonal/outbound-port-interface-in-core` ❌ `PaymentPort` как struct (не interface) — убивает подмену in-memory mock в unit-тестах.

---

## 5. Adapters in (`R-HEX-AIN-*`)

`hexagonal/in-adapter-per-audience` — отдельный пакет на каждый тип входа (`adapter/in/http/`, `adapter/in/kafka/`). HTTP
регистрируется в chi-роутере, kafka — отдельный consumer-loop.

`hexagonal/controller-dispatches-only` — handler маппит request-DTO → command, зовёт UseCase Handler; не зовёт репозиторий напрямую:

```go
// adapter/in/http/order_handler.go
package http

type OrderHandler struct {
    confirmOrder *usecase.ConfirmOrderHandler
}

func (h *OrderHandler) ConfirmOrder(w http.ResponseWriter, r *http.Request) {
    var req ConfirmOrderRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        httperr.Write(w, r, apperr.NewValidation("invalid json"))
        return
    }
    if err := validate.Struct(req); err != nil {
        httperr.Write(w, r, mapValidationErrors(err))
        return
    }
    cmd := OrderRequestMapper{}.ToConfirmCommand(req)
    if err := h.confirmOrder.Handle(r.Context(), cmd); err != nil {
        httperr.Write(w, r, err)
        return
    }
    w.WriteHeader(http.StatusNoContent)
}
```

`hexagonal/rest-mapping-in-adapter` — маппер — отдельная структура в пакете адаптера:

```go
// adapter/in/http/order_request_mapper.go
package http

type OrderRequestMapper struct{}

func (OrderRequestMapper) ToConfirmCommand(req ConfirmOrderRequest) usecase.ConfirmOrderCommand {
    return usecase.ConfirmOrderCommand{
        OrderID:    aggregate.OrderID(req.OrderID),
        PaymentRef: req.PaymentRef,
    }
}

func (OrderRequestMapper) ToOrderResponse(o aggregate.Order) OrderResponse {
    return OrderResponse{ID: string(o.ID()), Status: string(o.Status())}
}
```

Не возвращай `aggregate.Order` напрямую как HTTP-response — domain entity не сериализуется предсказуемо.

`hexagonal/adapters-do-not-know-each-other` — `adapter/in/http/` знает `chi`, `encoding/json`, `go-playground/validator`; **не знает**
`adapter/out/persistence/` или `adapter/out/sber/`.

`hexagonal/controller-dispatches-only` ❌ Бизнес-логика в handler:

```go
// AVOID
func (h *OrderHandler) ConfirmOrder(w http.ResponseWriter, r *http.Request) {
    if req.Amount > 100_000 {   // бизнес-правило в адаптере
        ...
    }
}
```

`hexagonal/controller-dispatches-only` ❌ Handler напрямую инжектит `OrderRepository`:

```go
// AVOID
type OrderHandler struct {
    repo persistence.OrderRepository  // нарушение: in-adapter → out-adapter
}
```

`hexagonal/rest-mapping-in-adapter` ❌ Возврат `aggregate.Order` как тело ответа (`json.NewEncoder(w).Encode(order)`) — используй
response-DTO из маппера.

`hexagonal/adapters-do-not-know-each-other` ❌ `adapter/in/http/` импортирует `adapter/out/sber/` — адаптеры зависят только от `core/`.

---

## 6. Adapters out (`R-HEX-AOUT-*`)

`hexagonal/out-adapter-per-system` — отдельный пакет на каждую внешнюю систему (`adapter/out/sber/`, `adapter/out/odna_kassa/`,
`adapter/out/persistence/`). Per-system isolation (cross-ref `resilience/client-per-external-system`).

`hexagonal/out-adapter-per-system` — адаптер реализует порт-interface из `core/`:

```go
// adapter/out/sber/payment_adapter.go
package sber

type PaymentAdapter struct {
    client *Client
    mapper PaymentMapper
}

var _ out.PaymentPort = (*PaymentAdapter)(nil)   // compile-time assertion

func (a *PaymentAdapter) Register(ctx context.Context, cmd out.RegisterPaymentCommand) (out.RegisterPaymentResult, error) {
    sberReq := a.mapper.ToSberRequest(cmd)
    sberResp, err := a.client.RegisterPayment(ctx, sberReq)
    if err != nil {
        return out.RegisterPaymentResult{}, &SberError{Op: "register", Err: err}
    }
    return a.mapper.ToDomainResult(sberResp), nil
}
```

`hexagonal/adapter-maps-not-decides` — маппер domain ↔ DTO внешней системы — отдельная структура в адаптере:

```go
// adapter/out/sber/payment_mapper.go
package sber

type PaymentMapper struct{}

func (PaymentMapper) ToSberRequest(cmd out.RegisterPaymentCommand) SberRegisterRequest {
    return SberRegisterRequest{
        OrderID:  string(cmd.OrderID),
        Amount:   cmd.Amount.Kopecks(),
        Currency: "RUB",
    }
}

func (PaymentMapper) ToDomainResult(resp SberRegisterResponse) out.RegisterPaymentResult {
    return out.RegisterPaymentResult{
        PaymentID:   out.PaymentID(resp.PaymentID),
        ConfirmedAt: resp.CreatedAt,
    }
}
```

`hexagonal/adapters-do-not-know-each-other` — `adapter/out/sber/` знает `net/http`-клиент + Sber-DTO; **не знает** `adapter/out/persistence/`.

`hexagonal/port-speaks-domain-types` ❌ `Register(ctx, cmd)` возвращает `(SberRegisterResponse, error)` из порт-метода — только domain-тип.

`hexagonal/adapter-maps-not-decides` ❌ Бизнес-логика в адаптере:

```go
// AVOID
if sberResp.Code == 1 {
    return out.RegisterPaymentResult{}, &InsufficientFundsError{...}  // решение в хендлере
}
```

Адаптер мапит: если Sber вернул ошибку, адаптер оборачивает её в `SberError`; handler интерпретирует через `errors.As`.

`hexagonal/out-adapter-per-system` ❌ Один адаптер `UniversalPaymentAdapter` реализует порты `PaymentPort` + `RefundPort` + `SubscriptionPort`
из разных BC. Per-system + per-concern isolation.

`hexagonal/adapters-do-not-know-each-other` ❌ `SberAdapter` инжектит `OdnaKassaAdapter` — координация двух систем — это use case в `core/`
(handler инжектит оба порта через `PaymentPort` + `RefundPort`).

---

## 7. Bootstrap / composition root (`R-HEX-BOOT-*`)

`hexagonal/bootstrap-composition-only` — `bootstrap/main.go` — единственное место ручной сборки:

```go
// bootstrap/main.go
package main

func main() {
    cfg := mustLoadConfig()

    db := mustOpenDB(cfg.DBURL)
    sberClient := sber.NewClient(cfg.SberURL, cfg.SberKey)

    orderRepo := persistence.NewOrderRepository(db)
    paymentAdapter := sber.NewPaymentAdapter(sberClient)

    confirmHandler := usecase.NewConfirmOrderHandler(orderRepo, paymentAdapter)

    r := chi.NewRouter()
    r.Use(middleware.Recoverer)
    r.Use(otelMiddleware)
    orderHTTP := httpAdapter.NewOrderHandler(confirmHandler)
    r.Post("/orders/{id}/confirm", orderHTTP.ConfirmOrder)

    srv := &http.Server{Addr: cfg.Addr, Handler: r}
    runWithGracefulShutdown(srv)
}
```

`hexagonal/bootstrap-composition-only` — если google/wire: провайдеры для `core/` не знают о фреймворках; wire-set собирается в `bootstrap/`.

`hexagonal/composition-covers-all-adapters` — весь wiring — в `bootstrap/`; core и адаптеры экспортируют конструкторы (`NewXxx`), не
`init()`/глобальные синглтоны.

`hexagonal/bootstrap-composition-only` ❌ `bootstrap/` содержит бизнес-логику (`if cfg.Feature { ... }` с доменными правилами) или
chi-handler'ы. Только wiring + конфиг + запуск сервера.

`hexagonal/bootstrap-composition-only` ❌ Создание `chi.Router` или DI-wiring в `core/<bc>/` или `adapter/in/http/`. Только
`bootstrap/main.go`.

---

## 8. Архитектурные тесты (`R-HEX-TEST-*`)

`hexagonal/architecture-tests-required` — в Go нет ArchUnit; enforcement через тест, проверяющий импорты:

```go
// bootstrap/architecture_test.go
package main_test

func TestCoreHasNoFrameworkImports(t *testing.T) {
    forbidden := []string{
        "github.com/go-chi/chi",
        "github.com/jackc/pgx",
        "github.com/redis/go-redis",
        "github.com/segmentio/kafka-go",
    }
    pkgs := listPackages(t, "./internal/core/...")
    for _, pkg := range pkgs {
        for _, imp := range pkg.Imports {
            for _, fb := range forbidden {
                if strings.HasPrefix(imp, fb) {
                    t.Errorf("core package %s imports forbidden %s", pkg.PkgPath, imp)
                }
            }
        }
    }
}

func listPackages(t *testing.T, pattern string) []*packages.Package {
    t.Helper()
    cfg := &packages.Config{Mode: packages.NeedImports | packages.NeedName}
    pkgs, err := packages.Load(cfg, pattern)
    require.NoError(t, err)
    return pkgs
}
```

Аналогично проверяется: `adapter/in/http/` не импортирует `adapter/out/*`; `adapter/out/<system>/` не импортирует
другой `adapter/out/<other>/`.

`hexagonal/architecture-test-required-check` — `go test ./bootstrap/...` с тегом `//go:build arch` запускается в CI как required check; PR не
мерджится при падении.

`hexagonal/single-scan-root` — единый root-паттерн `./internal/...` для скана пакетов — единая точка:

```go
pkgs, err := packages.Load(cfg, "./internal/core/...", "./internal/adapter/...")
```

`hexagonal/architecture-tests-required` ❌ Только code-review для enforcement — человек пропустит импорт `pgx` в `core/`; нужен авто-тест.

---

## 9. Антипаттерны (сводка)

Антипаттерны перечислены в `../spec.md` §9; здесь — Go-специфичные проявления:

- **Shared global state** (`var db *pgx.Pool` в `core/`) — global singleton в core нарушает `hexagonal/core-free-of-framework`. Pool передаётся через конструктор адаптера.
- **`init()` для wiring** — `init()` в `adapter/out/persistence/` создаёт соединение с базой. Нет explicit DI → невозможно переопределить в тестах. Только конструкторы.
- **Прямой вызов `os.Exit` в core** — нарушает lifecycle-управление. Exit — только в `bootstrap/main.go` через `signal.NotifyContext`.
- **Embedding adapter в core** — `type OrderService struct { *persistence.OrderRepository }` в `core/`. Embedding — не DI; теряется тестируемость.

---

## Чеклист подключения к новому сервису (Go)

- [ ] `core/<bc>/` не импортирует `chi`, `pgx`, `kafka-go`, `redis`, `slog` — проверяется архитектурным тестом
- [ ] Стрелка `bootstrap → adapter/* → core`; адаптеры не импортируют друг друга
- [ ] Outbound-порты — `interface` в `core/<bc>/port/out/`; port-ошибки (`PaymentPortError`) — там же
- [ ] Каждый out-adapter: `var _ out.XxxPort = (*XxxAdapter)(nil)` compile-time assertion
- [ ] In-adapter: chi-handler → маппер → `UseCase.Handle`; репозиторий не инжектится в handler напрямую
- [ ] Маппер — отдельная структура в пакете адаптера; domain entity не сериализуется в HTTP-ответ напрямую
- [ ] Out-adapter: маппит domain ↔ system-DTO; без бизнес-логики внутри; per-system пакеты
- [ ] `bootstrap/main.go` — единственное место wiring; конструкторы, не `init()`/глобальные синглтоны
- [ ] Архитектурный тест (`packages.Load` + forbidden-imports) в CI как required check
- [ ] Ошибки — `apperr.Kind` + типизированные структуры; `httperr.Write` на edge (cross-ref `error-handling/go/`)
- [ ] `recover`-middleware только на edge (`bootstrap/`); в `core/` нет `recover()`
