# Resilience — Go Style Guide (net/http + chi)

Реализация контракта `../resilience-rules.md` (коды `R-RES-*`) на Go-стеке. Коды правил — общие с Java/Python; здесь — как они выглядят в Go-сервисе.

> **Стек.** Защита outbound-вызовов строится на: timeout — `context.WithTimeout` + per-client `http.Transport`; circuit breaker — `github.com/sony/gobreaker`; retry — `github.com/avast/retry-go/v4`; bulkhead — `golang.org/x/sync/semaphore`; health-cache — `sync.Mutex` + TTL поле. Метрики — `github.com/prometheus/client_golang` (promauto); трейсинг — `go.opentelemetry.io/otel`. Каждый out-adapter — отдельный `*http.Client` со своим `http.Transport`.

| Защита | Go |
|---|---|
| timeout | `context.WithTimeout` + `Transport.{DialContext,ResponseHeaderTimeout,IdleConnTimeout}` |
| circuit breaker | `gobreaker.CircuitBreaker` (per-system) |
| retry | `retry.Do` с `retry.RetryIf` + `retry.BackOffDelay` |
| bulkhead | `semaphore.NewWeighted(max)` (per-system) |
| time limiter | `context.WithTimeout` вокруг async/pollling |
| health | функция-probe + TTL-кеш (`sync.Mutex`) |

---

## 1. Где какая защита (`R-RES-WHERE-*`)

`R-RES-WHERE-1` — outbound HTTP к внешним системам (платежи, фискализация, страхование, сторонние API): полный набор — timeout + CB + bulkhead + (опц.) retry. `R-RES-WHERE-2` — internal s2s: timeout + CB; bulkhead — по тяжести. `R-RES-WHERE-3` — schedulers/outbox-relay: durable retry через **task-queue** (`*_task`, DB), не in-memory; `gobreaker`/`retry-go` — для транзиентов <5s. `R-RES-WHERE-4` — inbound rate limit — на API Gateway, не в каждом сервисе.

`R-RES-WHERE-X1` — `gobreaker`/`retry.Do` вокруг репозитория, SQL-запроса, in-memory функции: нет транзиентных режимов, любой сбой там — реальная ошибка, не environment-failure.

---

## 2. Per-system isolation (`R-RES-ISO-*`)

`R-RES-ISO-1` — на каждую внешнюю систему — **отдельный** `*http.Client` с отдельным `*http.Transport`, собственным `gobreaker.CircuitBreaker`, `semaphore.Weighted` и конфигом. `R-RES-ISO-2` — sizing: `MaxIdleConnsPerHost ≈ maxConcurrent × 1.2`; суммарно по всем системам ≤ половина пула БД. `R-RES-ISO-3` — единое имя системы (`sber`, `receipt`, `insurance`) везде: в `gobreaker.Settings.Name`, метриках, логах.

```go
// adapters/out/sber/client.go
func newSberHTTPClient(cfg SberClientConfig) *http.Client {
    return &http.Client{
        Timeout: cfg.CallTimeout,
        Transport: &http.Transport{
            DialContext:           (&net.Dialer{Timeout: cfg.ConnectTimeout}).DialContext,
            ResponseHeaderTimeout: cfg.ReadTimeout,
            MaxIdleConnsPerHost:   cfg.MaxConcurrent + 2,
            IdleConnTimeout:       90 * time.Second,
        },
    }
}
```

`R-RES-ISO-X1` — один `http.DefaultClient` или один `*http.Client` для Sber + OdnaKassa: зависание одной системы исчерпывает idle-коннекты другой. `R-RES-ISO-X2` — `&http.Client{}` без явного `Transport` — используются глобальные `http.DefaultTransport` defaults (shared).

---

## 3. Timeouts (`R-RES-TO-*`)

`R-RES-TO-1` — иерархия: `connectTimeout < readTimeout < callTimeout`; реализуется через `Transport.DialContext` (connect), `Transport.ResponseHeaderTimeout` (read), `http.Client.Timeout` (call).

`R-RES-TO-2` — per-system через типизированный конфиг:

```go
// adapters/out/sber/config.go
type SberClientConfig struct {
    ConnectTimeout time.Duration `envconfig:"SBER_CONNECT_TIMEOUT" default:"2s"`
    ReadTimeout    time.Duration `envconfig:"SBER_READ_TIMEOUT"    default:"10s"`
    CallTimeout    time.Duration `envconfig:"SBER_CALL_TIMEOUT"    default:"15s"`
    MaxConcurrent  int           `envconfig:"SBER_MAX_CONCURRENT"  default:"20"`
    BaseURL        string        `envconfig:"SBER_BASE_URL"        required:"true"`
}
```

`R-RES-TO-3` — уважать TimeBudget из входящего контекста: если вызов пришёл с дедлайном и `remainingBudget < callTimeout`, переопределить таймаут:

```go
func capTimeout(ctx context.Context, callTimeout time.Duration) (context.Context, context.CancelFunc) {
    deadline, ok := ctx.Deadline()
    if ok {
        remaining := time.Until(deadline) - 100*time.Millisecond
        if remaining < callTimeout {
            callTimeout = remaining
        }
    }
    return context.WithTimeout(ctx, callTimeout)
}
```

`R-RES-TO-X1` — `&http.Client{}` без `Timeout` и без `Transport` с DialContext — дефолт ∞. `R-RES-TO-X2` — `CallTimeout < ReadTimeout` — `http.Client.Timeout` сработает прежде ResponseHeaderTimeout; второй никогда. `R-RES-TO-X3` — `ReadTimeout > 60s` в синхронном HTTP-хендлере — перевести в task-queue (`R-RES-WHERE-3`).

---

## 4. Circuit Breaker (`R-RES-CB-*`)

`R-RES-CB-1` — `gobreaker.CircuitBreaker` оборачивает **public-метод** out-adapter (структуры-адаптера), не `*http.Client`, не handler, не репозиторий.

`R-RES-CB-2`..`R-RES-CB-5` — count-based окно 50, min requests 10, failure rate 50% (30% для платежей), open 30s → half-open (3 пробных вызова). `R-RES-CB-5` (slow-call threshold): `gobreaker` не имеет встроенного slow-call порога в отличие от Resilience4j. Реализуется косвенно: оберните вызов контекстным таймаутом (`context.WithTimeout`) и возвращайте ошибку при превышении — `IsSuccessful` пометит такой вызов как неуспешный и учтёт его в failure rate. Альтернатива — выделить timeout-circuit в отдельный слой поверх CB.

```go
// adapters/out/sber/sber_adapter.go
func newSberBreaker(name string) *gobreaker.CircuitBreaker {
    return gobreaker.NewCircuitBreaker(gobreaker.Settings{
        Name:        name,
        MaxRequests: 3,                // half-open: 3 пробных (R-RES-CB-4)
        Interval:    0,               // count-based — сброс счётчика при переходе в closed
        Timeout:     30 * time.Second, // open-state length (R-RES-CB-4)
        ReadyToTrip: func(counts gobreaker.Counts) bool {
            if counts.Requests < 10 {  // min calls (R-RES-CB-2)
                return false
            }
            ratio := float64(counts.TotalFailures) / float64(counts.Requests)
            return ratio >= 0.50       // порог для обычных систем (R-RES-CB-3); для платёжных — 0.30
        },
        OnStateChange: func(name string, from, to gobreaker.State) {
            slog.Warn("circuit breaker state changed",
                "system", name,
                "prev_state", from.String(),
                "new_state", to.String(),
            )
        },
    })
}
```

`R-RES-CB-6` — при open-state CB возвращает `gobreaker.ErrOpenState`; адаптер мапит в port-specific ошибку:

```go
type SberAdapter struct {
    client  *http.Client
    breaker *gobreaker.CircuitBreaker
    sem     *semaphore.Weighted
    cfg     SberClientConfig
}

func (a *SberAdapter) Register(ctx context.Context, order Order) (PaymentRef, error) {
    if err := a.sem.Acquire(ctx, 1); err != nil {        // bulkhead (R-RES-BH)
        return PaymentRef{}, &PaymentSystemUnavailableError{System: "sber", Cause: err}
    }
    defer a.sem.Release(1)

    raw, err := a.breaker.Execute(func() (any, error) {
        callCtx, cancel := capTimeout(ctx, a.cfg.CallTimeout)
        defer cancel()
        return a.doRegister(callCtx, order)              // реальный HTTP-запрос
    })
    if err != nil {
        if errors.Is(err, gobreaker.ErrOpenState) || errors.Is(err, gobreaker.ErrTooManyRequests) {
            return PaymentRef{}, &PaymentSystemUnavailableError{System: "sber", Cause: err}
        }
        return PaymentRef{}, fmt.Errorf("sber register: %w", err)
    }
    return raw.(PaymentRef), nil
}
```

`R-RES-CB-X1` — `gobreaker` вокруг репозитория/SQL. `R-RES-CB-X2` — самописный CB на `sync.Mutex` + счётчик (bug-source; `gobreaker` отлажен и интегрируется с метриками). `R-RES-CB-X3` — один `gobreaker.CircuitBreaker` с `Name: "default"` для Sber и OdnaKassa — делят состояние.

---

## 5. Retry (`R-RES-RE-*`)

`R-RES-RE-1` — `retry.Do` **только** при идемпотентности: read-метод (`GetOrderStatus`, `FindProduct`) или write-метод с `Idempotency-Key` (`AUTH-19`). `R-RES-RE-2`/`R-RES-RE-3` — exponential backoff, до 3 попыток (включая первую), не более 5; фильтр только транзиентных ошибок:

```go
func (a *SberAdapter) GetPaymentStatus(ctx context.Context, ref PaymentRef) (PaymentStatus, error) {
    var result PaymentStatus
    err := retry.Do(
        func() error {
            var callErr error
            result, callErr = a.doGetStatus(ctx, ref)
            return callErr
        },
        retry.Context(ctx),
        retry.Attempts(3),
        retry.DelayType(retry.BackOffDelay),
        retry.Delay(200*time.Millisecond),
        retry.RetryIf(func(err error) bool {
            var unavail *PaymentSystemUnavailableError
            if errors.As(err, &unavail) {
                return false                 // CB open — не ретраить
            }
            var netErr net.Error
            if errors.As(err, &netErr) && netErr.Timeout() {
                return true                  // timeout транзиентен
            }
            return isRetriable5xx(err)       // 5xx от внешней системы
        }),
    )
    return result, err
}
```

`R-RES-RE-4`/`R-RES-RE-5` — долгий retry (>30s) или durable (переживание рестарта) — task-queue: таблица `*_task` с полями `status`, `retry_count`, `next_attempt_at`, `last_error`; scheduler poll каждые ~5s по `status = 'IN_PROGRESS' AND next_attempt_at <= now()`.

`R-RES-RE-X1` — `retry.Do` на write-методе без `Idempotency-Key` (двойной платёж). `R-RES-RE-X2` — retry на 4xx-ответе от внешней системы: контрактная ошибка, повтор не поможет. `R-RES-RE-X3` — `retry.FixedDelay` без роста задержки — бьёт пачкой по лежачей системе. `R-RES-RE-X4` — ретрай тех же ошибок, что считает CB, без согласования `RetryIf`: double-count failure.

---

## 6. Bulkhead (`R-RES-BH-*`)

`R-RES-BH-1`/`R-RES-BH-2` — `semaphore.NewWeighted(maxConcurrent)` per-system, **отдельно** от HTTP connection pool; ограничивает одновременные вызовы. `context.Context` и OTel-трейс не теряются — семафор работает в том же горутине, не создаёт отдельного пула. `R-RES-BH-3` — `maxConcurrent ≈ MaxIdleConnsPerHost × 0.8` (срабатывает раньше исчерпания пула):

```go
// adapters/out/insurance/insurance_adapter.go
type InsuranceAdapter struct {
    client  *http.Client
    breaker *gobreaker.CircuitBreaker
    sem     *semaphore.Weighted
}

func NewInsuranceAdapter(cfg InsuranceClientConfig) *InsuranceAdapter {
    return &InsuranceAdapter{
        client:  newInsuranceHTTPClient(cfg),
        breaker: newInsuranceBreaker("insurance"),
        sem:     semaphore.NewWeighted(int64(cfg.MaxConcurrent)),
    }
}

func (a *InsuranceAdapter) RequestCoverage(ctx context.Context, order Order) (CoverageRef, error) {
    if err := a.sem.Acquire(ctx, 1); err != nil {
        return CoverageRef{}, &InsuranceUnavailableError{Cause: err}
    }
    defer a.sem.Release(1)
    // ... CB + HTTP-вызов
}
```

`R-RES-BH-X1` — отдельный `goroutine`-пул (`errgroup` с фиксированным размером) как bulkhead для sync-кода: теряется `context.Context`/OTel без явного проброса; семафора достаточно.

---

## 7. Fallback (`R-RES-FB-*`)

`R-RES-FB-1` — fallback допустим для деградации: вернуть кешированный результат, частичный ответ, разумный дефолт (не для money-операций). `R-RES-FB-2` — явная обработка через `errors.As`/`errors.Is`, осознанный результат:

```go
func (s *ProductService) GetProductDetails(ctx context.Context, id ProductID) (ProductDetails, error) {
    details, err := s.catalogAdapter.GetDetails(ctx, id)
    if err != nil {
        var unavail *CatalogUnavailableError
        if errors.As(err, &unavail) {
            cached, cacheErr := s.cache.Get(ctx, id)  // fallback к кешу (R-RES-FB-1)
            if cacheErr == nil {
                return cached, nil
            }
        }
        return ProductDetails{}, fmt.Errorf("get product details: %w", err)
    }
    return details, nil
}
```

`R-RES-FB-X1` — fallback `Money{Amount: 0}` для money-операций: возврат нуля за «не удалось списать» — бизнес-баг. `R-RES-FB-X2` — `return result, nil` при фактической ошибке (тихий «успех» — клиент не узнает об отказе). `R-RES-FB-X3` — fallback, делающий outbound во второй провайдер (например, резервный платёжный шлюз) без собственного `gobreaker` на этот второй вызов — cascading failure.

---

## 8. Конфигурация (`R-RES-CFG-*`)

`R-RES-CFG-1` — параметры CB/retry/timeout/bulkhead через `envconfig` (kelseyhightower/envconfig) или `viper`; не хардкодом в коде — можно менять через env/ConfigMap без redeploy. `R-RES-CFG-2` — дефолты в тегах `default:`, per-system через префикс:

```go
// adapters/out/config.go
type OutboundConfig struct {
    Sber      SberClientConfig
    Receipt   ReceiptClientConfig
    Insurance InsuranceClientConfig
}

// envconfig читает SBER_CONNECT_TIMEOUT, RECEIPT_CONNECT_TIMEOUT и т.д. через prefix
```

`R-RES-CFG-3` — имя системы в `gobreaker.Settings.Name` = имя в конфиге = имя в метриках: `sber`, `receipt`, `insurance`, `odnakassa`.

`R-RES-CFG-X1` — `gobreaker.NewCircuitBreaker(gobreaker.Settings{...})` с числами прямо в коде без конфига: скрытые параметры, не управляются через env.

---

## 9. Связка с HTTP-клиентом из OpenAPI-генерации (`R-RES-OAS-*`)

`R-RES-OAS-1` — `gobreaker`/`retry.Do`/`sem.Acquire` — на **public-методе** структуры-адаптера, не на сгенерированном клиенте. `R-RES-OAS-2` — для новых сервисов клиент генерируется из OpenAPI-спеки внешней системы (oapi-codegen); спека в `adapters/out/<system>/openapi/<system>.openapi.yaml`; codegen в `internal/generated/<system>/`, не коммитится.

`R-RES-OAS-4` — между сгенерированным клиентом и портом из `core/` — явный mapper (generated DTO → domain-тип); адаптер использует mapper и возвращает domain, не generated DTO:

```go
// adapters/out/sber/mapper.go
func toPaymentRef(resp generated.RegisterResponse) PaymentRef {
    return PaymentRef{
        OrderID:    resp.OrderId,
        FormURL:    resp.FormUrl,
        ExternalID: resp.MdOrder,
    }
}
```

`R-RES-OAS-X1` — `gobreaker` встроен в сгенерированный клиент: регенерация затрёт. `R-RES-OAS-X3` — `PaymentPort.Register` возвращает `generated.RegisterResponse`: domain port раскрывает transport-DTO.

---

## 10. Health checks (`R-RES-HC-*`)

`R-RES-HC-1` — на каждую систему — отдельный health-индикатор, отражается в `/health/ready`. `R-RES-HC-2` — TTL-кеш ~30s: не проверять внешнюю систему на каждый K8s-пинг. `R-RES-HC-3` — лёгкий probe: `GET /health` или `HEAD /`, не бизнес-вызов. `R-RES-HC-4` — readiness учитывает внешние системы, liveness — нет:

```go
// adapters/out/sber/health.go
type SberHealthChecker struct {
    client    *http.Client
    baseURL   string
    mu        sync.Mutex
    lastCheck time.Time
    lastOK    bool
    ttl       time.Duration
}

func (h *SberHealthChecker) Check(ctx context.Context) error {
    h.mu.Lock()
    defer h.mu.Unlock()
    if time.Since(h.lastCheck) < h.ttl {
        if !h.lastOK {
            return errors.New("sber: last probe failed")
        }
        return nil
    }
    probeCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
    defer cancel()
    req, _ := http.NewRequestWithContext(probeCtx, http.MethodGet, h.baseURL+"/health", nil)
    resp, err := h.client.Do(req)
    h.lastCheck = time.Now()
    if err != nil || resp.StatusCode >= 500 {
        h.lastOK = false
        return fmt.Errorf("sber health probe: %w", err)
    }
    h.lastOK = true
    return nil
}
```

`R-RES-HC-X1` — probe без кеша на каждый `/health/ready`: при K8s-пробах каждые 5s — DDoS внешней системы своими же health-check'ами. `R-RES-HC-X2` — probe бизнес-операцией (`registerTestOrder`, `getTransactions`) — изменяет состояние, нагружает, плодит мусорные данные.

---

## 11. Async и polling (`R-RES-ASYNC-*`)

`R-RES-ASYNC-1` — polling внешней системы (например, страхование: «отправили → ждём результат») — через **task-queue**, не через `time.Sleep`-цикл в горутине handler'а:

```go
// scheduler/insurance_poll_scheduler.go
func (s *InsurancePollScheduler) Run(ctx context.Context) {
    ticker := time.NewTicker(5 * time.Second)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            s.processPendingTasks(ctx)
        }
    }
}
```

`R-RES-ASYNC-2` — `time.Sleep` в адаптере допустим только при total wait <2s (короткий фиксированный backoff для транзиентного retry). `R-RES-ASYNC-3` — для async outbound (`goroutine` + channel) — `context.WithTimeout` обязателен; без него retry/CB не покрывают timeout goroutine-вызова.

`R-RES-ASYNC-X1` — `time.Sleep`-цикл с опросом внешней системы внутри HTTP-handler'а или в `goroutine`, запущенной из него: блокирует/держит горутину на N×iterations секунд, при нагрузке исчерпывает пул воркеров. `R-RES-ASYNC-X2` — `time.Sleep(d)` с `d > 5s` — запах «должно быть task-queue».

---

## 12. Observability (`R-RES-OBS-*`)

`R-RES-OBS-1` — метрики CB/retry/bulkhead через `promauto`:

```go
// adapters/out/metrics.go
var (
    cbState = promauto.NewGaugeVec(prometheus.GaugeOpts{
        Name: "circuit_breaker_state",
        Help: "Current circuit breaker state (0=closed, 1=open, 2=half-open)",
    }, []string{"system"})

    retryAttemptsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "retry_attempts_total",
        Help: "Total retry attempts by system and outcome",
    }, []string{"system", "outcome"})

    bulkheadRejectedTotal = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "bulkhead_rejected_total",
        Help: "Total requests rejected by bulkhead",
    }, []string{"system"})
)
```

Обновление метрики CB-состояния — в `OnStateChange` callback'е `gobreaker.Settings`.

`R-RES-OBS-2` — OTel-span на adapter-методе с атрибутами `circuit_breaker.state` и `external.system`:

```go
func (a *SberAdapter) Register(ctx context.Context, order Order) (PaymentRef, error) {
    ctx, span := otel.Tracer("sber-adapter").Start(ctx, "SberAdapter.Register")
    defer span.End()
    span.SetAttributes(
        attribute.String("external.system", "sber"),
        attribute.String("circuit_breaker.state", a.breaker.State().String()),
    )
    // ...
}
```

`R-RES-OBS-3` — структурный лог (WARN) на каждый state-transition CB (в `OnStateChange`), не на каждый успешный вызов:

```go
OnStateChange: func(name string, from, to gobreaker.State) {
    slog.Warn("circuit breaker state changed",
        "system", name,
        "prev_state", from.String(),
        "new_state", to.String(),
    )
},
```

`R-RES-OBS-X1` — отключение метрик resilience (`promauto` убрать / Prometheus выключить): SRE не увидит залипший half-open на Sber до инцидента.

---

## 13. Антипаттерны (сводка из `R-RES-*-X*`)

Полный список — в `../resilience-rules.md` §13. Типичные Go-специфичные:

- `http.DefaultClient` для внешних вызовов — shared transport, нет изоляции по системам.
- `&http.Client{Timeout: 0}` — бесконечный timeout.
- Один `gobreaker.CircuitBreaker` с `Name: "default"` на все системы — делят состояние.
- `retry.Do` без `retry.RetryIf` — ретраит всё, включая 4xx и `gobreaker.ErrOpenState`.
- `time.Sleep`-polling в HTTP-handler'е — исчерпывает goroutine-пул при нагрузке.
- Probe в `/health` без TTL-кеша — K8s-пробы каждые 5s = DDoS внешней системы.
- Fallback `Money{Amount: 0}` для payment-операций — бизнес-баг без exception.

---

## Чеклист подключения к новому сервису (Go)

- [ ] На каждую внешнюю систему — отдельный `*http.Client` + `*http.Transport` с явными `DialContext` / `ResponseHeaderTimeout` / `MaxIdleConnsPerHost`
- [ ] `gobreaker.CircuitBreaker` per-system: count-based окно 50, min 10, failure rate 50%/30%, timeout 30s, half-open 3, `OnStateChange` → WARN-лог + метрика
- [ ] `semaphore.NewWeighted(maxConcurrent)` per-system (≈ 80% от `MaxIdleConnsPerHost`); `Acquire` до CB-вызова
- [ ] retry только на read-методах или write с `Idempotency-Key`; `retry.RetryIf` по `errors.As`; max 3 попытки; `BackOffDelay`; не на `ErrOpenState`/4xx
- [ ] `capTimeout` уважает входящий дедлайн контекста (`R-RES-TO-3`)
- [ ] Конфигурация через `envconfig`-теги; имя системы = `SBER_`-префикс = `gobreaker.Settings.Name` = метрика
- [ ] `gobreaker`/`retry.Do`/`sem.Acquire` — на public-методе адаптера, не на сгенерированном клиенте
- [ ] Mapper generated DTO → domain-тип; port возвращает domain, не generated struct
- [ ] `SberHealthChecker` с TTL-кешем ~30s; probe `GET /health`/`HEAD /`; `/health/ready` учитывает внешние
- [ ] Polling — task-queue (`*_task` таблица); `time.Sleep` в адаптере только при total wait <2s
- [ ] `promauto`: `circuit_breaker_state{system}`, `retry_attempts_total{system,outcome}`, `bulkhead_rejected_total{system}`
- [ ] OTel-span на adapter-методе: `external.system`, `circuit_breaker.state`; `span.RecordError` + `span.SetStatus(codes.Error, ...)`
- [ ] Долгий retry (>30s) / durable (переживание рестарта) → task-queue, не `retry.Do`
- [ ] fallback не для money; fallback с outbound → собственный CB на второй вызов
