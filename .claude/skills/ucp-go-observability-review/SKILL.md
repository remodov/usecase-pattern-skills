---
name: ucp-go-observability-review
lang: go
description: Ревью наблюдаемости Go-сервиса (net/http + chi) по UCP (требования observability/*) — slog JSON + context.Context, prometheus/client_golang (RED/USE, chi-middleware), OTel (otelhttp/otelpgx/otelslog-bridge), health live/ready, management-порт, SLO.
when_to_use: Изменения в logging-конфиге (slog), метриках (promauto), OTel-setup, chi-middleware, health-эндпоинтах, management-конфиге, context propagation.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Observability (Go / slog + prometheus/client_golang + OTel)

Ты ревьюишь наблюдаемость Go-сервиса на соответствие **контракту** `backend/observability/spec.md` (`R-OBS-*`) и
**Go-реализации** `backend/observability/references/go/implementation.md`.
Помни парадигму: в Go контекст передаётся явно через `context.Context` (нет thread-local/MDC/contextvars);
`defer span.End()` — единственный идиоматичный гарант закрытия span; logгер через конструктор (DI), не глобальный.

## Зависимости

- **`.claude/docs/backend/observability/spec.md`** + **`backend/observability/references/go/implementation.md`**.
- Парные: `backend/error-handling/references/go/implementation.md` (`R-ERR-LOG-*`, `R-ERR-OBS-*`), `backend/resilience/spec.md` (health внешних), `backend/auth-patterns/spec.md` (`auth-patterns/no-pii-in-logs-and-events` PII).

## Инструкции

1. **Прочти** контракт `observability/spec.md` (коды) + требования `go-style/*` (идиомы). Цитируй конкретные коды (`observability/no-pii-in-logs`, `observability/low-cardinality-labels`), не только префикс.

2. **Скоп.** Логирование (`slog`), метрики (`promauto`), OTel-setup, chi-middleware (request-id, metrics, auth), health-эндпоинты, management-сервер, context propagation; `git diff`.

3. **Прогон по подгруппам.**

   ### Logging (`R-OBS-LOG-*`)
   - `slog.NewJSONHandler` в проде, `slog.NewTextHandler` локально — по `APP_ENV`; логгер через конструктор, не `slog.Default()` — `R-OBS-LOG-1/2`.
   - Структурные поля через key-value аргументы (`slog.String`, `slog.Int64`, `slog.Any`), не `fmt.Sprintf` — `observability/parameterized-log-messages`.
   - Уровни по семантике: DEBUG/INFO/WARN/ERROR — `observability/log-levels-and-noise`.
   - `traceId`/`spanId` через OTel-slog bridge (`go.opentelemetry.io/contrib/bridges/otelslog`); `requestId`/`userId` через `context.Context` — `observability/request-context-in-every-record`.
   - Логи на границах out-adapter, не на каждый запрос в хендлерах — `observability/log-levels-and-noise`.
   - PII в логах → `observability/no-pii-in-logs` (**критично**).
   - `fmt.Println` / `fmt.Fprintf(os.Stderr, ...)` → `observability/no-direct-stdout-logging`.
   - Тяжёлая сериализация вычисленной строкой (`obj.ExpensiveJSON()`) вместо `slog.Any("key", obj)` → `observability/parameterized-log-messages`.
   - `log.ErrorContext(ctx, err.Error())` строкой вместо атрибута `slog.String("error", err.Error())` → `observability/parameterized-log-messages`.
   - Полный request body для PII-эндпоинтов → `observability/no-pii-in-logs`.
   - INFO-лог на каждый HTTP-запрос внутри хендлеров (access-log — дело chi-middleware) → `observability/log-levels-and-noise`.

   ### Metrics (`R-OBS-MTR-*`)
   - `promauto` + `promhttp.Handler()` на management-порту — `observability/metrics-are-exported`.
   - Labels `service`/`env`/`version` через `prometheus.Labels` в `promauto` — `observability/standard-metric-dimensions`.
   - RED для HTTP через chi-middleware (`http_requests_total`, `http_request_duration_seconds`); `path` — chi route pattern, не raw URL — `observability/red-and-use-metrics`.
   - USE через `collectors.NewGoCollector()` / `collectors.NewProcessCollector(...)` — `observability/red-and-use-metrics`.
   - Бизнес-метрики (`orders_created_total`, `order_amount_rub`) через `promauto.NewCounterVec` / `NewHistogram` — `observability/red-and-use-metrics`.
   - Имена snake_case с единицей в суффиксе (`payment_duration_seconds`, `orders_created_total`) — `observability/metric-naming`.
   - Label-значения низкой cardinality: `status_class`, `payment_method`, chi route pattern — `observability/low-cardinality-labels`.
   - `user_id`/`order_id`/`request_id` как label → `observability/low-cardinality-labels` (**критично**, OOM в Prometheus).
   - Нестандартные label-имена (`app` вместо `service`) → `observability/standard-metric-dimensions`.
   - `prometheus.NewCounterVec` без регистрации (нет `promauto`) → `observability/metrics-are-exported`.
   - `/metrics` на бизнес-порту без сетевой защиты → `observability/management-endpoints-restricted` (**критично**).

   ### Tracing (`R-OBS-TRC-*`)
   - OTel автоинструментация: `otelhttp.NewHandler` на роутере, `otelpgx` на pgx-пуле, `otelhttp.NewTransport` на HTTP-клиентах — `observability/tracing-auto-instrumented`.
   - `traceparent` W3C propagation через `otelhttp` на входящих / `otelhttp.Transport` на исходящих — `observability/tracing-auto-instrumented`.
   - Ручные span для UseCase хендлеров: `otel.Tracer("...").Start(ctx, "Op")` + `defer span.End()` — `observability/manual-spans-are-closed`.
   - Атрибуты — бизнес-контекст (`order.id`, `payment.method`), не PII — `observability/manual-spans-are-closed`.
   - `trace.TraceIDRatioBased(0.01)` в `trace.ParentBased(...)` (1–10%); tail-based на ошибки в коллекторе — `observability/sampling-strategy`.
   - `trace_id`/`span_id` в логах — через OTel-slog bridge, не вручную — `observability/logs-linked-to-traces`.
   - `trace.AlwaysSample()` в проде → `observability/sampling-strategy`.
   - PII в span attributes → `observability/manual-spans-are-closed` (**критично**).
   - Manual span без `defer span.End()` → `observability/manual-spans-are-closed` (в Go нет try-with-resources).
   - Горутина с `context.Background()` вместо родительского ctx → `observability/context-propagated-to-async`.

   ### Health checks (`R-OBS-HC-*`)
   - Раздельные `/health/live` (только «процесс жив», без внешних проверок) и `/health/ready` (с TTL-кешем проверки зависимостей) — `R-OBS-HC-1/2`.
   - `/info` (version, commit, build_time) на management-порту — `observability/health-indicator-per-system`.
   - Бизнес-состояние в health → `observability/health-check-is-technical`.
   - `/health/live` зависит от DB/Redis → `observability/liveness-and-readiness-split` (**критично**, restart-loop).
   - Health-probe выполняет бизнес-операцию (`INSERT INTO health_check`) → `observability/health-check-is-technical`.

   ### Config (`R-OBS-CFG-*`)
   - Два `http.Server` в одном процессе: бизнес-порт (`router`) и management-порт (`/metrics`, `/health/*`, `/info`) — `observability/separate-management-port`.
   - Явный список endpoint'ов на management-сервере; без `pprof` в проде без auth — `observability/separate-management-port`.
   - Buckets гистограммы latency: `prometheus.DefBuckets` или кастомные для SLO (напр. p99 < 500ms) — `observability/metrics-are-exported`.
   - Уровень логов по `APP_ENV`; `slog.LevelVar` для runtime-изменения — `observability/structured-logs-in-production`.
   - `net/http/pprof` без auth на публичной сети → `observability/management-endpoints-restricted` (**критично**).
   - Один порт для бизнес + management → `observability/separate-management-port`.
   - Все debug-эндпоинты без контроля доступа → `observability/management-endpoints-restricted`.

   ### Context propagation (`R-OBS-CTX-*`)
   - `RequestID`-middleware первым в chi-цепочке: читает/генерирует `X-Request-Id`, кладёт в `context.Context` через typed key — `observability/context-set-at-edge-and-cleared`.
   - `trace_id`/`span_id` через OTel-slog bridge автоматически; не добавлять вручную через `ctx.Value(...)` — `observability/logs-linked-to-traces`.
   - Горутины получают родительский ctx явным аргументом (не захватывают из замыкания); `context.WithTimeout(ctx, ...)` для fan-out — `observability/context-propagated-to-async`.
   - `userId` в ctx из auth-middleware после JWT-валидации (`golang-jwt`); хендлеры читают, не пишут в ctx — `observability/context-set-at-edge-and-cleared`.
   - Ctx захвачен из замыкания в долгоживущей горутине → `observability/context-set-at-edge-and-cleared`.
   - `context.WithValue` в UseCase Handler / Domain Service для observability-полей → `observability/context-set-at-edge-and-cleared`.
   - Горутина с `context.Background()` / без ctx → `observability/context-propagated-to-async` (**критично**, разрыв trace + потеря cancel).

   ### SLO и алерты (`R-OBS-SLO-*`)
   - SLO для каждого critical-endpoint; RED-гистограммы как источник данных для recording rules — `observability/slo-with-error-budget`.
   - Multi-window multi-burn-rate alerts (1h × 14× burn + 6h × 6× burn); реализуется в Prometheus rules — `observability/burn-rate-alerting`.
   - Alert на error budget < 10% за период — `observability/burn-rate-alerting`.
   - Alerts отдельно от SLO-recording rules — `observability/burn-rate-alerting`.
   - Alert на каждый ERROR в slog → `observability/burn-rate-alerting` (alert fatigue; используй `rate(app_errors_total{type="technical"}[5m]) > 0.1`).
   - SLO 100% target (нет error budget) → `observability/slo-with-error-budget`.
   - Alert без `annotations.runbook_url` → `observability/alerts-have-runbooks`.

4. **Grep-паттерны для обязательной проверки:**
   - `fmt\.Println\|fmt\.Fprintf\(os\.Stderr` — вне slog-pipeline.
   - `slog\.Default()` — глобальный логгер без DI.
   - `context\.Background()` внутри горутин (не в main/setup) — разрыв trace.
   - `trace\.AlwaysSample()` — запрещено в проде.
   - `WithValue` в хендлерах/сервисах вне middleware.
   - `prometheus\.New[A-Za-z]*` без `promauto` — метрика без регистрации.

5. **Cross-check:** PII-гигиена → `ucp-go-auth-review` (`auth-patterns/no-pii-in-logs-and-events`); health внешних систем → `ucp-go-resilience-review`; `R-ERR-LOG-*`/`R-ERR-OBS-*` (`app_errors_total`, `span.RecordError`) → `ucp-go-error-handling-review`; wiring chi-middleware в bootstrap → `ucp-go-bootstrap-review`.

6. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

7. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — PII в логах (`observability/no-pii-in-logs`), PII в span attributes (`observability/manual-spans-are-closed`), `user_id`/`order_id` как Prometheus label (`observability/low-cardinality-labels`), liveness зависит от DB/Redis (`observability/liveness-and-readiness-split`), pprof без auth (`observability/management-endpoints-restricted`), горутина с `context.Background()` (`observability/context-propagated-to-async`), `/metrics` на бизнес-порту без защиты (`observability/management-endpoints-restricted`).
   - **Предупреждение** — `fmt.Println` вместо `slog` (`observability/no-direct-stdout-logging`), `AlwaysSample()` в проде (`observability/sampling-strategy`), manual span без `defer span.End()` (`observability/manual-spans-are-closed`), один порт business+management (`observability/separate-management-port`), alert на каждый ERROR (`observability/burn-rate-alerting`), ctx захвачен из замыкания в горутине (`observability/context-set-at-edge-and-cleared`).
   - **Замечание** — INFO на каждый запрос в хендлерах (`observability/log-levels-and-noise`), нестандартные label-имена (`observability/standard-metric-dimensions`), нет runbook (`observability/alerts-have-runbooks`), `context.WithValue` в хендлере (`observability/context-set-at-edge-and-cleared`).

## Что не входит

- PII-классификация/маскирование политики — `ucp-go-auth-review` (`auth-patterns/no-pii-in-logs-and-events`).
- Health внешних систем (TTL/probe-стратегия) — `ucp-go-resilience-review`.
- Wiring middleware/management в bootstrap — `ucp-go-bootstrap-review`.
- `R-ERR-LOG-*` / `R-ERR-OBS-*` (ошибки-значения, `app_errors_total`, `span.RecordError`) — `ucp-go-error-handling-review`.

$ARGUMENTS
