# Graceful Shutdown — Go Style Guide (net/http + chi)

Реализация контракта `../graceful-shutdown-rules.md` (`R-SHUT-*`) на Go-стеке (net/http + chi). Коды правил —
общие с Java/Python; механизм: вместо Spring `ApplicationAvailability` + `@PreDestroy` — **`os.Signal` канал +
`context.WithCancel`** + `http.Server.Shutdown` + `sync.WaitGroup` для фоновых задач. K8s-часть (`R-SHUT-K8S-*`)
нейтральна. Ошибки — значения (`apperr.Kind` + `errors.As` + `%w`), как в
`../error-handling/go/error-handling-style-guide.md`.

---

## 1. Runtime/конфигурация (`R-SHUT-CFG-*`)

`R-SHUT-CFG-1` — `http.Server.Shutdown(ctx)` вместо `http.Server.Close()`: Shutdown дожидается in-flight
запросов; Close рвёт их немедленно.

`R-SHUT-CFG-2` — таймаут фазы shutdown задаётся явным контекстом (20–30s; в 60s budget после preStop остаётся
место для Kafka/БД):

```go
// internal/server/server.go
func Run(ctx context.Context, srv *http.Server, cfg Config) error {
    sigC := make(chan os.Signal, 1)
    signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)
    defer signal.Stop(sigC)

    errC := make(chan error, 1)
    go func() { errC <- srv.ListenAndServe() }()

    select {
    case <-sigC:
        slog.InfoContext(ctx, "получили SIGTERM, начинаем graceful shutdown")
    case err := <-errC:
        return err
    }

    shutCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout) // 25s
    defer cancel()
    return srv.Shutdown(shutCtx)
}
```

`R-SHUT-CFG-3` — readiness-флаг переводится в `false` первым, до `srv.Shutdown`. Health-endpoint проверяет
атомарный флаг; `atomic.Bool` — единственный источник состояния (не разрозненные переменные):

```go
// internal/health/state.go
type State struct{ ready atomic.Bool }

func NewState() *State { s := &State{}; s.ready.Store(true); return s }

func (s *State) SetNotReady() { s.ready.Store(false) }
func (s *State) IsReady() bool { return s.ready.Load() }
```

```go
// в Run, до srv.Shutdown:
appState.SetNotReady()
// /health/ready теперь → 503
```

`R-SHUT-CFG-4` — раздельные `/health/live` и `/health/ready` — chi-маршруты с разной логикой:

```go
r.Get("/health/live", func(w http.ResponseWriter, _ *http.Request) {
    w.WriteHeader(http.StatusOK)
})
r.Get("/health/ready", func(w http.ResponseWriter, _ *http.Request) {
    if !appState.IsReady() {
        w.WriteHeader(http.StatusServiceUnavailable)
        return
    }
    w.WriteHeader(http.StatusOK)
})
```

`R-SHUT-CFG-X1` ❌ `var shuttingDown bool` как обычная переменная без `atomic` и без связи с health-эндпоинтом —
k8s продолжает слать трафик.

---

## 2. HTTP drain (`R-SHUT-HTTP-*`)

`R-SHUT-HTTP-1` — `http.Server.Shutdown` дожидается всех in-flight запросов; новые соединения не принимаются
автоматически. Дополнительной логики не требуется — механизм встроен.

`R-SHUT-HTTP-2` — `preStop` hook со `sleep 10` обязателен в Deployment:

```yaml
# k8s/deployment.yaml (фрагмент)
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 10"]
```

`R-SHUT-HTTP-3` — долгие эндпоинты (>10s) — `202 Accepted` + polling или постановка задачи в очередь:

```go
// POST /orders/{id}/submit — запустить async, вернуть 202
func (h *OrderHandler) Submit(w http.ResponseWriter, r *http.Request) {
    orderID := chi.URLParam(r, "id")
    taskID, err := h.tasks.Enqueue(r.Context(), SubmitOrderTask{OrderID: orderID})
    if err != nil {
        httperr.Write(w, r, err)
        return
    }
    w.Header().Set("Location", "/orders/"+orderID+"/status")
    w.WriteHeader(http.StatusAccepted)
    _ = json.NewEncoder(w).Encode(map[string]string{"taskId": taskID})
}
```

`R-SHUT-HTTP-X1` ❌ `srv.Close()` вместо `srv.Shutdown(ctx)` — немедленно рвёт активные соединения, аннулирует graceful.

---

## 3. Kafka shutdown (`R-SHUT-KFK-*`)

`R-SHUT-KFK-1` — consumer (`segmentio/kafka-go`) дожимает текущий batch и коммитит offset перед остановкой;
горутина consumer'а управляется через `context.Context`, отменяемый на SIGTERM:

```go
// internal/consumer/order_consumer.go
func (c *OrderConsumer) Run(ctx context.Context) error {
    for {
        msg, err := c.reader.FetchMessage(ctx)
        if err != nil {
            if errors.Is(err, context.Canceled) || errors.Is(err, io.EOF) {
                return nil
            }
            return fmt.Errorf("fetch message: %w", err)
        }
        if err := c.handle(ctx, msg); err != nil {
            return fmt.Errorf("handle order event: %w", err)
        }
        if err := c.reader.CommitMessages(ctx, msg); err != nil {
            return fmt.Errorf("commit offset: %w", err)
        }
    }
}
```

`R-SHUT-KFK-2` — listener не запускает долгий каскад (HTTP с retry на 30s не укладывается в бюджет) — каскад в
async-flow или outbox.

`R-SHUT-KFK-3` — ручной `CommitMessages` после обработки каждого сообщения (или batch); `kafka-go` не имеет
авто-коммита в смысле kafka-go reader-API — нужно явно вызывать `CommitMessages`.

`R-SHUT-KFK-4` — flush и закрытие writer'а на shutdown:

```go
// в shutdown-последовательности:
if err := producer.Close(); err != nil {
    slog.ErrorContext(ctx, "kafka writer close", "error", err)
}
```

`R-SHUT-KFK-X1` ❌ `AutoCommit` на стороне kafka-go reader с `CommitInterval` — часть offset фиксируется до
обработки; потеря сообщений при SIGTERM.

---

## 4. БД и persistence (`R-SHUT-DB-*`)

`R-SHUT-DB-1` — пул `pgx` (`pgxpool.Pool`) закрывается последним, после завершения HTTP/задач/consumer'а;
порядок shutdown определяется explicit-последовательностью в `main`:

```go
// cmd/order-service/main.go
func main() {
    ctx := context.Background()
    pool, _ := pgxpool.New(ctx, cfg.DatabaseURL)
    appState := health.NewState()
    // ... инициализация consumer, scheduler

    shutdownFns := []func(){
        func() { appState.SetNotReady() },                         // R-SHUT-CFG-3
        func() { cancelConsumerCtx() },                            // R-SHUT-KFK-1
        func() { consumerWg.Wait() },
        func() { schedulerWg.Wait() },                             // R-SHUT-SCHED-1
        func() { srv.Shutdown(shutCtx) },                          // R-SHUT-HTTP-1
        func() { pool.Close() },                                   // R-SHUT-DB-1 — последним
    }
    // shutdownFns вызываются последовательно на SIGTERM
}
```

`R-SHUT-DB-2` — активные транзакции завершаются через свой канал (HTTP — via Shutdown, scheduler/consumer —
через отмену контекста с дожатием `WaitGroup`).

`R-SHUT-DB-3` — миграции (`golang-migrate` или аналог) запускаются только на старте, не на shutdown.

`R-SHUT-DB-X1` ❌ `pool.Close()` раньше завершения фоновых задач — pgx паникует при попытке взять соединение из
закрытого пула.

---

## 5. Фоновые задачи / async / outbox (`R-SHUT-SCHED-*`)

`R-SHUT-SCHED-1` — фоновые горутины завершают текущую итерацию, не начинают новую; управляются через
`context.Context` + `sync.WaitGroup`:

```go
// internal/scheduler/outbox_relay.go
func (r *OutboxRelay) Run(ctx context.Context, wg *sync.WaitGroup) {
    defer wg.Done()
    ticker := time.NewTicker(r.interval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            if err := r.processOneBatch(ctx); err != nil {
                slog.WarnContext(ctx, "outbox relay batch", "error", err)
            }
        }
    }
}
```

`R-SHUT-SCHED-2` — горутина с долгим каскадом держит `WaitGroup` до конца критичной секции; отмена контекста —
сигнал «не начинать новый batch», не «прервать текущий`:

```go
func (s *PaymentSettler) settle(ctx context.Context) error {
    // критичная секция: ctx отменён, но работу доводим до конца
    tx, err := s.pool.Begin(context.Background()) // отдельный ctx для tx!
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(context.Background())
    // ... бизнес-логика
    return tx.Commit(context.Background())
}
```

`R-SHUT-SCHED-3` — outbox-relay завершает текущий batch (`FOR UPDATE SKIP LOCKED`), не начинает новый; цикл
проверяет `ctx.Done()`, не `for { ... }` без проверки:

```go
func (r *OutboxRelay) processOneBatch(ctx context.Context) error {
    return sqlc_tx(ctx, r.pool, func(q *db.Queries) error {
        events, err := q.LockOutboxBatch(ctx, batchSize) // FOR UPDATE SKIP LOCKED
        if err != nil {
            return fmt.Errorf("lock batch: %w", err)
        }
        for _, e := range events {
            if err := r.publish(ctx, e); err != nil {
                return fmt.Errorf("publish event %s: %w", e.ID, err)
            }
            if err := q.MarkDispatched(ctx, e.ID); err != nil {
                return fmt.Errorf("mark dispatched %s: %w", e.ID, err)
            }
        }
        return nil
    })
}
```

`R-SHUT-SCHED-X1` ❌ Отмена горутины без `WaitGroup.Wait()` — задача убита в середине, частичные изменения без
rollback; inconsistent state.

---

## 6. Kubernetes (`R-SHUT-K8S-*`, нейтрально)

`R-SHUT-K8S-1` — `terminationGracePeriodSeconds: 60` явно в Deployment; preStop sleep — отдельный бюджет сверху.

`R-SHUT-K8S-2` — `readinessProbe` → `/health/ready`, `livenessProbe` → `/health/live`; на shutdown
readiness=503 (liveness-падение рестартит pod).

`R-SHUT-K8S-3` — `maxSurge: 1, maxUnavailable: 0` (нулевой downtime при rolling update).

```yaml
# k8s/deployment.yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      terminationGracePeriodSeconds: 60
      containers:
        - name: order-service
          lifecycle:
            preStop:
              exec:
                command: ["/bin/sh", "-c", "sleep 10"]
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
```

`R-SHUT-K8S-X1` ❌ Отсутствие preStop — 5–15s после SIGTERM kube-proxy ещё льёт трафик → 502.

`R-SHUT-K8S-X2` ❌ `terminationGracePeriodSeconds: 30` (default) при 25s graceful — preStop не помещается,
SIGKILL посреди дрейна.

---

## 7. Идемпотентность in-flight (`R-SHUT-IDEM-*`)

`R-SHUT-IDEM-1` — операции, которые SIGTERM может прервать, retry-safe: write с `Idempotency-Key` в заголовке,
money-cascade через task-queue/outbox, Kafka-handler через outbox + дедупликацию `processed_event(event_id)`:

```go
// adapters/out/payment/client.go
func (c *Client) Charge(ctx context.Context, cmd ChargeCommand) error {
    req, _ := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/charges", encode(cmd))
    req.Header.Set("Idempotency-Key", cmd.IdempotencyKey) // R-SHUT-IDEM-1, AUTH-19
    // ...
}
```

```go
// internal/consumer/product_consumer.go — дедупликация события
func (c *ProductConsumer) handle(ctx context.Context, msg kafka.Message) error {
    var event ProductCreatedEvent
    if err := json.Unmarshal(msg.Value, &event); err != nil {
        return fmt.Errorf("unmarshal product event: %w", err)
    }
    return c.queries.UpsertWithDedup(ctx, db.UpsertWithDedupParams{
        EventID: event.ID,
        // ...
    }) // INSERT ... ON CONFLICT (event_id) DO NOTHING
}
```

`R-SHUT-IDEM-X1` ❌ Money-операция (списание с Customer) без `Idempotency-Key` под retry — SIGTERM в момент
retry → новый pod спишет повторно (запрещено `R-RES-RE-X1`).

---

## 8. Бюджеты и observability (`R-SHUT-OBS-*`)

`R-SHUT-OBS-1` — реалистичный cumulative-бюджет: preStop 10s + `http.Server.Shutdown` ≤25s + scheduler/async
≤20s + kafka consumer ≤15s ≤ 60s; не помещается — сократить batch (100→20), не увеличивать budget.

`R-SHUT-OBS-2` — метрика `app_shutdown_duration_seconds` + структурный лог начала/конца shutdown:

```go
var shutdownDuration = promauto.NewGauge(prometheus.GaugeOpts{
    Name: "app_shutdown_duration_seconds",
    Help: "Duration of graceful shutdown",
})

// в Run, обёртка вокруг shutdown-последовательности:
start := time.Now()
defer func() {
    dur := time.Since(start).Seconds()
    shutdownDuration.Set(dur)
    slog.InfoContext(ctx, "graceful shutdown завершён", "duration_s", dur)
}()
slog.InfoContext(ctx, "graceful shutdown начат")
```

`R-SHUT-OBS-3` — лог факта SIGTERM первым:

```go
case sig := <-sigC:
    slog.InfoContext(ctx, "получили SIGTERM, начинаем graceful shutdown", "signal", sig.String())
    appState.SetNotReady()
```

`R-SHUT-OBS-X1` ❌ `slog.Error` при нормальном закрытии пула/consumer'а — шум в alert-канале на каждый деплой;
нормальное закрытие логировать на `Info`.

---

## Чеклист подключения к новому сервису (Go)

1. `os.Signal` канал (`SIGTERM`/`SIGINT`); `http.Server.Shutdown(ctx)` с явным таймаутом 20–25s; `appState.SetNotReady()` первым.
2. Раздельные `/health/live` и `/health/ready`; `/health/ready` возвращает 503 при `!appState.IsReady()`.
3. preStop `sleep 10` в Deployment; in-flight HTTP дожимаются через Shutdown; долгие эндпоинты — 202+polling.
4. kafka-go consumer управляется `context.Context`; `CommitMessages` после обработки; `writer.Close()` на shutdown.
5. `pgxpool.Pool.Close()` последним в shutdown-последовательности, после `WaitGroup.Wait()` по задачам.
6. Фоновые горутины + outbox-relay: `sync.WaitGroup` + проверка `ctx.Done()` перед новой итерацией; критичная секция — `context.Background()` для транзакций.
7. k8s: `terminationGracePeriodSeconds: 60`, preStop, probes на `/health/{live,ready}`, `maxUnavailable: 0`.
8. In-flight write-операции retry-safe — `Idempotency-Key`; money-cascade в outbox; Kafka-handler — `ON CONFLICT DO NOTHING` по `event_id`.
9. `app_shutdown_duration_seconds` (promauto Gauge); лог `SIGTERM`/начала/конца на `Info`; нормальное закрытие пула — не `Error`.
