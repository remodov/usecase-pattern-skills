# Observability — Go Style Guide (net/http + chi)

Реализация контракта `../observability-rules.md` (коды `R-OBS-LOG-*`, `R-OBS-MTR-*`, `R-OBS-TRC-*`, `R-OBS-HC-*`, `R-OBS-CFG-*`, `R-OBS-CTX-*`, `R-OBS-SLO-*`).
Инструментарий: **log/slog** (логи), **prometheus/client_golang** (метрики), **go.opentelemetry.io/otel** (трейсы), **context.Context** вместо MDC/contextvars.

---

## 1. Logging (`R-OBS-LOG-*`)

`R-OBS-LOG-1` — `log/slog` с `slog.NewJSONHandler(os.Stdout, ...)` в проде, `slog.NewTextHandler` локально.
Выбор — по переменной окружения (`APP_ENV`), единожды при старте:

```go
// internal/platform/log/setup.go
func New(env string) *slog.Logger {
    if env == "production" {
        return slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
    }
    return slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug}))
}
```

`R-OBS-LOG-2` — логгер через конструктор (DI), не глобальный `slog.Default()`.
Пробрасывается в хендлеры через структуру-сервис:

```go
type OrderHandler struct {
    log    *slog.Logger
    orders OrderService
}

func NewOrderHandler(log *slog.Logger, orders OrderService) *OrderHandler {
    return &OrderHandler{log: log.With("component", "order_handler"), orders: orders}
}
```

`R-OBS-LOG-3` — структурные поля через key-value аргументы (`slog.String`, `slog.Int64`, атрибуты), не fmt-форматирование:

```go
// PREFER
h.log.InfoContext(ctx, "order_created", slog.String("order_id", order.ID), slog.String("customer_id", order.CustomerID))

// AVOID
h.log.InfoContext(ctx, fmt.Sprintf("order created: %s", order.ID))
```

`R-OBS-LOG-4` — уровни по семантике: DEBUG — вспомогательный (внутренние состояния, данные для отладки);
INFO — значимые события (создан заказ, сменён статус); WARN — ожидаемые сбои (Domain/Validation-ошибки,
деградация внешки); ERROR — неожиданные сбои (panic, Technical, Integration при открытом CB).

`R-OBS-LOG-5` — `traceId`/`spanId` подставляются автоматически через OTel-slog bridge
(`go.opentelemetry.io/contrib/bridges/otelslog`); `requestId` и `userId` — через middleware в `context.Context`,
читаются в slog-handler или извлекаются явно в edge-слое:

```go
// internal/platform/middleware/reqid.go
type ctxKey string

const (
    ctxRequestID ctxKey = "request_id"
    ctxUserID    ctxKey = "user_id"
)

func RequestID(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        id := r.Header.Get("X-Request-Id")
        if id == "" {
            id = uuid.NewString()
        }
        ctx := context.WithValue(r.Context(), ctxRequestID, id)
        w.Header().Set("X-Request-Id", id)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

Логгер с полями контекста на edge:

```go
func logFromCtx(ctx context.Context, log *slog.Logger) *slog.Logger {
    args := []any{}
    if id, ok := ctx.Value(ctxRequestID).(string); ok {
        args = append(args, slog.String("request_id", id))
    }
    if uid, ok := ctx.Value(ctxUserID).(string); ok {
        args = append(args, slog.String("user_id", uid))
    }
    return log.With(args...)
}
```

`R-OBS-LOG-6` — логи на границах: вход в out-adapter (`INFO product_lookup_started`), выход (`INFO`/`WARN` в зависимости от результата), ошибка интеграции (`WARN`/`ERROR`). Хендлеры UseCase логируют только значимые события, не каждый вызов.

---

`R-OBS-LOG-X1` — PII в логах (email, телефон, ФИО, токены, полный payload карты) — критическое нарушение.
Маскировать или не логировать совсем:

```go
// PREFER — только идентификатор
log.InfoContext(ctx, "payment_registered", slog.String("order_id", cmd.OrderID))

// AVOID — токен в логе
log.InfoContext(ctx, "payment", slog.String("card_token", cmd.CardToken))
```

`R-OBS-LOG-X2` — `fmt.Println` / `fmt.Fprintf(os.Stderr, ...)` — вне pipeline, теряют контекст. Только `slog`.

`R-OBS-LOG-X3` — тяжёлая сериализация как аргумент: `slog` ленив при `slog.Any`, но при передаче уже вычисленной строки ленивость теряется. Передавай объект, не `obj.String()`:

```go
// PREFER
log.DebugContext(ctx, "snapshot", slog.Any("order", order))

// AVOID
log.DebugContext(ctx, "snapshot: "+order.ExpensiveJSON())
```

`R-OBS-LOG-X4` — `log.ErrorContext(ctx, err.Error())` строкой — теряется структура. Передавай ошибку атрибутом:

```go
// PREFER
log.ErrorContext(ctx, "order_confirm_failed", slog.String("error", err.Error()), "order_id", id)
// или через OTel-bridge: span.RecordError(err) + slog вытянет автоматически
```

`R-OBS-LOG-X5` — полный request body для эндпоинтов с PII (платежи, профиль) — только идентификаторы (`order_id`).

`R-OBS-LOG-X6` — INFO-лог на каждый HTTP-запрос внутри хендлеров — noise. Access-log ведёт `chi/middleware.Logger` отдельно с правильным форматом.

---

## 2. Metrics (`R-OBS-MTR-*`)

`R-OBS-MTR-1` — `github.com/prometheus/client_golang` + `promauto` для авто-регистрации; endpoint `/metrics`
через `promhttp.Handler()` на отдельном management-порту:

```go
// internal/platform/metrics/server.go
func StartManagement(addr string) *http.Server {
    mux := http.NewServeMux()
    mux.Handle("/metrics", promhttp.Handler())
    mux.HandleFunc("/health/live", liveHandler)
    mux.HandleFunc("/health/ready", readyHandler)
    return &http.Server{Addr: addr, Handler: mux}
}
```

`R-OBS-MTR-2` — стандартные labels `service`/`env`/`version` через `prometheus.Labels` в `promauto`:

```go
// internal/platform/metrics/common.go
var commonLabels = prometheus.Labels{
    "service": env.ServiceName,
    "env":     env.AppEnv,
    "version": env.Version,
}
```

Для метрик сервиса — добавлять `With(commonLabels)` к `CounterVec` / `HistogramVec`.

`R-OBS-MTR-3` — RED для HTTP (Rate/Errors/Duration) — через chi-middleware:

```go
// internal/platform/middleware/metrics.go
var (
    httpRequestsTotal = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    }, []string{"method", "path", "status_class"})

    httpRequestDurationSeconds = promauto.NewHistogramVec(prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request latency",
        Buckets: prometheus.DefBuckets,
    }, []string{"method", "path", "status_class"})
)

func Metrics(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
        start := time.Now()
        next.ServeHTTP(ww, r)
        status := statusClass(ww.Status())
        path := chi.RouteContext(r.Context()).RoutePattern()
        httpRequestsTotal.WithLabelValues(r.Method, path, status).Inc()
        httpRequestDurationSeconds.WithLabelValues(r.Method, path, status).Observe(time.Since(start).Seconds())
    })
}

func statusClass(code int) string {
    switch {
    case code < 400:
        return "success"
    case code < 500:
        return "client_error"
    default:
        return "server_error"
    }
}
```

`R-OBS-MTR-4` — USE для ресурсов (горутины, соединения) — через `prometheus/client_golang/prometheus/collectors`:

```go
// в main или platform/metrics/setup.go
prometheus.MustRegister(collectors.NewGoCollector())         // goroutines, GC, mem
prometheus.MustRegister(collectors.NewProcessCollector(...)) // CPU, FDs
// pgx-pool stats — регистрируй кастомный Collector или Gauge, обновляемый периодически
```

`R-OBS-MTR-5` — бизнес-метрики через `promauto`:

```go
// internal/order/metrics.go
var (
    ordersCreatedTotal = promauto.NewCounterVec(prometheus.CounterOpts{
        Name: "orders_created_total",
        Help: "Orders successfully created",
    }, []string{"payment_method"})

    orderAmountRub = promauto.NewHistogram(prometheus.HistogramOpts{
        Name:    "order_amount_rub",
        Help:    "Order amount in rubles",
        Buckets: []float64{100, 500, 1000, 5000, 10000, 50000},
    })
)

// в UseCase Handler:
ordersCreatedTotal.WithLabelValues(string(cmd.PaymentMethod)).Inc()
orderAmountRub.Observe(float64(order.AmountMinor) / 100)
```

`R-OBS-MTR-6` — имена snake_case с единицей в суффиксе: `payment_duration_seconds`, `orders_created_total`,
`product_cache_hits_total`. Без `_total` для Gauge-метрик.

`R-OBS-MTR-7` — label-значения низкой cardinality: `status_class` (3 значения), `payment_method` (CARD/SBP),
`endpoint`/`path` (chi route pattern, не raw URL — иначе `/orders/123` и `/orders/456` разные series).

---

`R-OBS-MTR-X1` — `user_id`/`order_id`/`request_id` как label-значения — миллионы time series, OOM в Prometheus.
Для трассировки отдельных объектов — traces (OTel), не метрики.

`R-OBS-MTR-X2` — нестандартные label-имена (`app` вместо `service`, `environment` вместо `env`) — нарушает
единообразие дашбордов.

`R-OBS-MTR-X3` — метрики без зарегистрированного registry. `promauto` решает это автоматически — он регистрирует
в `prometheus.DefaultRegisterer`. Не создавай `prometheus.NewCounterVec` без регистрации.

`R-OBS-MTR-X4` — `/metrics` на бизнес-порту без сетевой защиты. Management-сервер должен быть доступен только
внутренней сети (сетевая политика / VPN).

---

## 3. Tracing (`R-OBS-TRC-*`)

`R-OBS-TRC-1` — OTel автоинструментация через contrib-пакеты:

```go
// internal/platform/tracing/setup.go
import (
    "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
)

func Setup(ctx context.Context, cfg Config) (func(context.Context) error, error) {
    exp, err := otlptracegrpc.New(ctx, otlptracegrpc.WithEndpoint(cfg.OTLPEndpoint))
    if err != nil {
        return nil, fmt.Errorf("tracing exporter: %w", err)
    }
    tp := trace.NewTracerProvider(
        trace.WithBatcher(exp),
        trace.WithSampler(trace.ParentBased(trace.TraceIDRatioBased(cfg.SampleRate))),
        trace.WithResource(cfg.Resource),
    )
    otel.SetTracerProvider(tp)
    return tp.Shutdown, nil
}
```

Chi-роутер оборачивается `otelhttp.NewHandler(router, "order-service")` — авто-span на каждый запрос.
Для pgx — `go.opentelemetry.io/contrib/instrumentation/github.com/jackc/pgx/v5/otelpgx`.
Для kafka-go — `otelsegmentio` или ручная propagation через `otel.GetTextMapPropagator()`.

`R-OBS-TRC-2` — `traceparent` (W3C Trace Context) пропагируется автоматически через `otelhttp` на входящем запросе
и через `otelhttp.Transport` / `httptrace` на исходящем HTTP-клиенте:

```go
client := &http.Client{
    Transport: otelhttp.NewTransport(http.DefaultTransport),
}
```

`R-OBS-TRC-3` — ручные span для UseCase хендлеров и значимых операций:

```go
// internal/order/usecase/confirm_order.go
func (h *ConfirmOrderHandler) Handle(ctx context.Context, cmd ConfirmOrderCommand) error {
    ctx, span := otel.Tracer("order").Start(ctx, "ConfirmOrder")
    defer span.End()

    order, err := h.orders.Load(ctx, cmd.OrderID)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return fmt.Errorf("load order: %w", err)
    }
    // ...
    return nil
}
```

`try-finally` гарантируется через `defer span.End()` — нельзя пропустить закрытие.

`R-OBS-TRC-4` — span attributes — бизнес-контекст, не PII:

```go
span.SetAttributes(
    attribute.String("order.id", cmd.OrderID),
    attribute.String("order.status", string(order.Status)),
    attribute.String("payment.method", string(cmd.PaymentMethod)),
    // НЕ customer.email, НЕ card.pan
)
```

`R-OBS-TRC-5` — sampling: `trace.TraceIDRatioBased(0.01)` (1%) в проде оборачивается в `trace.ParentBased(...)` —
уважает решение вышестоящего сервиса. 100% на ошибки через tail-based sampling в коллекторе (OTel Collector
`tail_sampling` processor).

`R-OBS-TRC-6` — `trace_id` в логах через OTel-slog bridge (`go.opentelemetry.io/contrib/bridges/otelslog`):
bridge автоматически добавляет `trace_id`/`span_id` в каждую slog-запись из active span-а в контексте.

---

`R-OBS-TRC-X1` — `trace.AlwaysSample()` в проде на нагруженном сервисе — переполняет Tempo/Jaeger за часы.

`R-OBS-TRC-X2` — PII в span attributes (`customer.email`, `order.detail` с адресом). Tracing хранилище
менее защищено, чем основная БД.

`R-OBS-TRC-X3` — manual span без `defer span.End()` — утечка span. В Go нет try-with-resources, `defer` — единственный идиоматичный гарант:

```go
// AVOID — span может не закрыться при ранних return
ctx, span := tracer.Start(ctx, "op")
if err := doA(); err != nil {
    return err // span не закрыт
}
span.End()

// PREFER
ctx, span := tracer.Start(ctx, "op")
defer span.End()
```

`R-OBS-TRC-X4` — разрыв контекста в горутинах без проброса `ctx`:

```go
// AVOID
go func() {
    h.notify(context.Background(), order) // теряет trace context
}()

// PREFER — см. R-OBS-CTX-3
```

---

## 4. Health checks (`R-OBS-HC-*`)

`R-OBS-HC-1` — раздельные `/health/live` и `/health/ready` на management-порту:

```go
// /health/live — только «процесс жив»; не зависит от внешних систем
func liveHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
    _, _ = w.Write([]byte(`{"status":"UP"}`))
}

// /health/ready — готовность принимать трафик
func (h *readyHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if err := h.check(r.Context()); err != nil {
        w.WriteHeader(http.StatusServiceUnavailable)
        _ = json.NewEncoder(w).Encode(map[string]string{"status": "DOWN", "reason": "dependency unavailable"})
        return
    }
    w.WriteHeader(http.StatusOK)
    _, _ = w.Write([]byte(`{"status":"UP"}`))
}
```

`R-OBS-HC-2` — custom-check на критичные внешние системы с TTL-кешем результата (не дёргать БД/Redis на каждый
probe Kubernetes):

```go
// internal/platform/health/postgres.go
type pgChecker struct {
    db      *pgxpool.Pool
    mu      sync.Mutex
    lastOK  time.Time
    ttl     time.Duration
}

func (c *pgChecker) Check(ctx context.Context) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    if time.Since(c.lastOK) < c.ttl {
        return nil
    }
    if err := c.db.Ping(ctx); err != nil {
        return fmt.Errorf("postgres ping: %w", err)
    }
    c.lastOK = time.Now()
    return nil
}
```

`R-OBS-HC-3` — `/info` (версия, build, commit):

```go
func infoHandler(version, commit, buildTime string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        _ = json.NewEncoder(w).Encode(map[string]string{
            "version":    version,
            "commit":     commit,
            "build_time": buildTime,
        })
    }
}
```

---

`R-OBS-HC-X1` — бизнес-состояние в health (`if orderCount > threshold { return DOWN }`) — health это техническое
состояние процесса; бизнес-метрики → SLO.

`R-OBS-HC-X2` — liveness зависит от внешних систем (DB/Redis): при недоступности Kubernetes рестартует pod,
что не помогает, создаёт restart-loop. Внешние проверки — только в readiness.

`R-OBS-HC-X3` — health-probe выполняет бизнес-операцию (`INSERT INTO health_check`). Kubernetes scrape каждые
секунды → DDoS себя.

---

## 5. Конфигурация (`R-OBS-CFG-*`)

`R-OBS-CFG-1` — management-порт отдельный от бизнес-порта. Два HTTP-сервера в одном процессе:

```go
// cmd/server/main.go
businessSrv := &http.Server{Addr: cfg.Addr, Handler: otelhttp.NewHandler(router, "order-service")}
managementSrv := metrics.StartManagement(cfg.ManagementAddr)

g, ctx := errgroup.WithContext(ctx)
g.Go(func() error { return businessSrv.ListenAndServe() })
g.Go(func() error { return managementSrv.ListenAndServe() })
```

`R-OBS-CFG-2` — explicit список endpoints на management: только `/metrics`, `/health/live`, `/health/ready`, `/info`.
Не монтируй `pprof` на production management-порт без отдельной защиты.

`R-OBS-CFG-3` — дефолтные buckets гистограммы латентности (`prometheus.DefBuckets`) подходят для большинства
HTTP-сервисов. Для платёжных эндпоинтов с SLO «p99 < 500ms» — кастомные:

```go
Buckets: []float64{0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0}
```

`R-OBS-CFG-4` — конфиг логирования по `APP_ENV` (`production` → JSON/INFO; иные → Text/DEBUG). Уровень
управляется через `slog.LevelVar` для возможности runtime-изменения без перезапуска:

```go
var logLevel slog.LevelVar // default: INFO

// management endpoint для изменения уровня логирования (только в проде, только за auth)
mux.HandleFunc("PUT /log-level", func(w http.ResponseWriter, r *http.Request) {
    // ...
    logLevel.Set(newLevel)
})
```

---

`R-OBS-CFG-X1` — pprof/debug-эндпоинты (`net/http/pprof`) без auth на публичной сети — утечка профилей памяти.
Если нужно в проде — только за mTLS или сетевой политикой.

`R-OBS-CFG-X2` — один порт для бизнес и management в проде. Невозможно ограничить scraping-трафик.

`R-OBS-CFG-X3` — монтировать все debug-эндпоинты (`pprof`, `expvar`, raw stack dump) без контроля доступа.

---

## 6. Context propagation (`R-OBS-CTX-*`)

`R-OBS-CTX-1` — request-id middleware создаёт или читает `X-Request-Id` и кладёт в `context.Context`.
В Go context.Context — единственный механизм propagation (нет thread-local):

```go
// internal/platform/middleware/reqid.go — см. §1 выше
// middleware монтируется первым в chi-цепочке:
r := chi.NewRouter()
r.Use(RequestID)
r.Use(otelhttp.Middleware("order-service")) // OTel после — чтобы span видел request_id
r.Use(middleware.Logger)
```

`R-OBS-CTX-2` — `trace_id`/`span_id` в логах — автоматически через OTel-slog bridge; не добавлять руками
через `ctx.Value(...)`.

`R-OBS-CTX-3` — горутины без проброса `ctx` разрывают trace. Канонический паттерн:

```go
// AVOID — новый context.Background() в горутине
go func() {
    h.notify(context.Background(), customerID)
}()

// PREFER — пробрасываем родительский ctx
notifyCtx, notifyCancel := context.WithTimeout(ctx, 5*time.Second)
defer notifyCancel()
go func(ctx context.Context) {
    h.notify(ctx, customerID)
}(notifyCtx)
```

Для fan-out с WaitGroup — передавай `ctx` явным аргументом в каждую горутину, не захватывай из замыкания
(может быть отменён раньше).

`R-OBS-CTX-4` — `userId` в context.Context после JWT-валидации в auth-middleware:

```go
// internal/platform/middleware/auth.go
func Auth(verifier TokenVerifier) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            claims, err := verifier.Verify(r.Header.Get("Authorization"))
            if err != nil {
                httperr.Write(w, r, &apperr.UnauthorizedError{})
                return
            }
            ctx := context.WithValue(r.Context(), ctxUserID, claims.Subject)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

---

`R-OBS-CTX-X1` — в Go нет утечки через thread pool (каждый запрос — отдельный `context.Context`, он не переиспользуется). Но захват `ctx` из замыкания в долгоживущей горутине — утечка trace. Всегда передавай ctx аргументом.

`R-OBS-CTX-X2` — `context.WithValue` в UseCase Handler или Domain Service для observability-полей (`request_id`, `user_id`). Только в middleware. Handler читает из ctx, не пишет.

`R-OBS-CTX-X3` — горутина с `context.Background()` / без `ctx` — разрыв trace и потеря cancel-сигнала:

```go
// AVOID
go func() {
    _ = h.repo.Save(context.Background(), order) // trace разорван, cancel не работает
}()
```

---

## 7. SLO и алерты (`R-OBS-SLO-*`)

`R-OBS-SLO-1` — у каждого critical-эндпоинта есть SLO. Метрики для SLO формируются из RED-гистограмм (§2).
Пример: `POST /orders` — SLO availability 99.9%, latency p99 < 500ms:

```yaml
# prometheus rule (вне Go-кода, в ops-репо или helm-чарте)
- record: job:http_request_duration_seconds:p99
  expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{path="/orders"}[5m])) by (le))
```

`R-OBS-SLO-2` — multi-window multi-burn-rate alerts (Google SRE Workbook): быстрое окно (1h) + медленное (6h)
с разными порогами burn rate (14× за 1h → page; 6× за 6h → ticket). Реализуется в Prometheus/Alertmanager
rules, не в Go-коде.

`R-OBS-SLO-3` — alert на error budget < 10% (за период): срабатывает один раз на период, сигнал «нужен
reliability focus». Alertmanager inhibition — подавляет менее критичные alert'ы при активном SLO-alert.

`R-OBS-SLO-4` — alerts отдельны от SLO-recording rules: recording rules обновляются часто, alert-правила
должны пересматриваться при изменении SLO-target.

---

`R-OBS-SLO-X1` — alert на каждый ERROR в slog — alert fatigue. Агрегируй через Prometheus:
`rate(app_errors_total{type="technical"}[5m]) > 0.1` — один alert на паттерн, не на событие.

`R-OBS-SLO-X2` — SLO 100% target — нет error budget, нечем оперировать. 99.9% даёт 43 минуты в месяц.

`R-OBS-SLO-X3` — alerts без runbook. Каждый alert содержит `annotations.runbook_url` ссылкой на ops-docs.

---

## 8. Антипаттерны

Сводная таблица нарушений с кодами для grep по коду ревью:

| Код | Что запрещено | Последствие |
|---|---|---|
| `R-OBS-LOG-X1` | PII в логах | compliance-инцидент |
| `R-OBS-LOG-X2` | `fmt.Println` вместо `slog` | потеря pipeline и контекста |
| `R-OBS-LOG-X4` | `err.Error()` строкой в `slog.Error` | потеря структуры |
| `R-OBS-MTR-X1` | `user_id`/`order_id` как label-значение | OOM в Prometheus |
| `R-OBS-MTR-X4` | `/metrics` на публичном порту без защиты | утечка метрик |
| `R-OBS-TRC-X1` | `AlwaysSample()` в проде | переполнение Tempo |
| `R-OBS-TRC-X2` | PII в span attributes | утечка в tracing storage |
| `R-OBS-TRC-X3` | span без `defer span.End()` | утечка spans |
| `R-OBS-TRC-X4` | горутина с `context.Background()` | разрыв trace |
| `R-OBS-HC-X2` | liveness зависит от DB/Redis | restart-loop |
| `R-OBS-CFG-X2` | один порт business+management | scraping блокирует бизнес |
| `R-OBS-CTX-X1` | ctx захвачен из замыкания в горутине | утечка trace |
| `R-OBS-CTX-X2` | `context.WithValue` в хендлере/домене | неявная связанность |
| `R-OBS-SLO-X1` | alert на каждый ERROR | alert fatigue |
| `R-OBS-SLO-X3` | alert без runbook | эскалация без действия |

---

## Чеклист подключения к новому сервису (Go)

- [ ] `log/slog`: JSON-handler в проде, Text локально, по `APP_ENV`; логгер через конструктор, не глобальный.
- [ ] Структурные поля как key-value аргументы; нет PII; нет `fmt.Println`; ошибка — атрибутом, не строкой.
- [ ] `promauto`: RED-middleware на chi (rate/errors/duration), бизнес-метрики (Counter/Histogram), USE через `GoCollector`/`ProcessCollector`.
- [ ] Все label-значения низкой cardinality; path — chi route pattern, не raw URL.
- [ ] OTel: `otlptracegrpc`-exporter, `otelhttp.NewHandler` на роутере, `otelhttp.NewTransport` на HTTP-клиентах, `otelpgx` на pgx-пуле, OTel-slog bridge.
- [ ] `TraceIDRatioBased` + `ParentBased` sampling (1–10%); tail-based в коллекторе на ошибки; `defer span.End()` на каждом ручном span.
- [ ] `/health/live` и `/health/ready` раздельно; readiness с TTL-кешем проверки внешних систем.
- [ ] Management-сервер на отдельном порту: `/metrics`, `/health/live`, `/health/ready`, `/info`; без debug-эндпоинтов в проде без auth.
- [ ] `RequestID`-middleware первым в chi-цепочке; `Auth`-middleware кладёт `user_id` в ctx; ctx пробрасывается в горутины аргументом.
- [ ] SLO recording rules + multi-window burn-rate alerts + alert на error budget < 10%; у каждого alert — `runbook_url`.
