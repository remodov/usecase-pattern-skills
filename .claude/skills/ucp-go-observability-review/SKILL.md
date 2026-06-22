---
name: ucp-go-observability-review
lang: go
description: Ревью наблюдаемости Go-сервиса (net/http + chi) по UCP (коды R-OBS-*) — slog JSON + context.Context, prometheus/client_golang (RED/USE, chi-middleware), OTel (otelhttp/otelpgx/otelslog-bridge), health live/ready, management-порт, SLO.
when_to_use: Изменения в logging-конфиге (slog), метриках (promauto), OTel-setup, chi-middleware, health-эндпоинтах, management-конфиге, context propagation.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Observability (Go / slog + prometheus/client_golang + OTel)

Ты ревьюишь наблюдаемость Go-сервиса на соответствие **контракту** `backend/observability/observability-rules.md` (`R-OBS-*`) и
**Go-реализации** `backend/observability/go/observability-style-guide.md`.
Помни парадигму: в Go контекст передаётся явно через `context.Context` (нет thread-local/MDC/contextvars);
`defer span.End()` — единственный идиоматичный гарант закрытия span; logгер через конструктор (DI), не глобальный.

## Зависимости

- **`.claude/docs/backend/observability/observability-rules.md`** + **`backend/observability/go/observability-style-guide.md`**.
- Парные: `backend/error-handling/go/error-handling-style-guide.md` (`R-ERR-LOG-*`, `R-ERR-OBS-*`), `backend/resilience/resilience-rules.md` (health внешних), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-16` PII).

## Инструкции

1. **Прочти** контракт `observability-rules.md` (коды) + Go-style-guide (идиомы). Цитируй конкретные коды (`R-OBS-LOG-X1`, `R-OBS-MTR-X1`), не только префикс.

2. **Скоп.** Логирование (`slog`), метрики (`promauto`), OTel-setup, chi-middleware (request-id, metrics, auth), health-эндпоинты, management-сервер, context propagation; `git diff`.

3. **Прогон по подгруппам.**

   ### Logging (`R-OBS-LOG-*`)
   - `slog.NewJSONHandler` в проде, `slog.NewTextHandler` локально — по `APP_ENV`; логгер через конструктор, не `slog.Default()` — `R-OBS-LOG-1/2`.
   - Структурные поля через key-value аргументы (`slog.String`, `slog.Int64`, `slog.Any`), не `fmt.Sprintf` — `R-OBS-LOG-3`.
   - Уровни по семантике: DEBUG/INFO/WARN/ERROR — `R-OBS-LOG-4`.
   - `traceId`/`spanId` через OTel-slog bridge (`go.opentelemetry.io/contrib/bridges/otelslog`); `requestId`/`userId` через `context.Context` — `R-OBS-LOG-5`.
   - Логи на границах out-adapter, не на каждый запрос в хендлерах — `R-OBS-LOG-6`.
   - PII в логах → `R-OBS-LOG-X1` (**критично**).
   - `fmt.Println` / `fmt.Fprintf(os.Stderr, ...)` → `R-OBS-LOG-X2`.
   - Тяжёлая сериализация вычисленной строкой (`obj.ExpensiveJSON()`) вместо `slog.Any("key", obj)` → `R-OBS-LOG-X3`.
   - `log.ErrorContext(ctx, err.Error())` строкой вместо атрибута `slog.String("error", err.Error())` → `R-OBS-LOG-X4`.
   - Полный request body для PII-эндпоинтов → `R-OBS-LOG-X5`.
   - INFO-лог на каждый HTTP-запрос внутри хендлеров (access-log — дело chi-middleware) → `R-OBS-LOG-X6`.

   ### Metrics (`R-OBS-MTR-*`)
   - `promauto` + `promhttp.Handler()` на management-порту — `R-OBS-MTR-1`.
   - Labels `service`/`env`/`version` через `prometheus.Labels` в `promauto` — `R-OBS-MTR-2`.
   - RED для HTTP через chi-middleware (`http_requests_total`, `http_request_duration_seconds`); `path` — chi route pattern, не raw URL — `R-OBS-MTR-3`.
   - USE через `collectors.NewGoCollector()` / `collectors.NewProcessCollector(...)` — `R-OBS-MTR-4`.
   - Бизнес-метрики (`orders_created_total`, `order_amount_rub`) через `promauto.NewCounterVec` / `NewHistogram` — `R-OBS-MTR-5`.
   - Имена snake_case с единицей в суффиксе (`payment_duration_seconds`, `orders_created_total`) — `R-OBS-MTR-6`.
   - Label-значения низкой cardinality: `status_class`, `payment_method`, chi route pattern — `R-OBS-MTR-7`.
   - `user_id`/`order_id`/`request_id` как label → `R-OBS-MTR-X1` (**критично**, OOM в Prometheus).
   - Нестандартные label-имена (`app` вместо `service`) → `R-OBS-MTR-X2`.
   - `prometheus.NewCounterVec` без регистрации (нет `promauto`) → `R-OBS-MTR-X3`.
   - `/metrics` на бизнес-порту без сетевой защиты → `R-OBS-MTR-X4` (**критично**).

   ### Tracing (`R-OBS-TRC-*`)
   - OTel автоинструментация: `otelhttp.NewHandler` на роутере, `otelpgx` на pgx-пуле, `otelhttp.NewTransport` на HTTP-клиентах — `R-OBS-TRC-1`.
   - `traceparent` W3C propagation через `otelhttp` на входящих / `otelhttp.Transport` на исходящих — `R-OBS-TRC-2`.
   - Ручные span для UseCase хендлеров: `otel.Tracer("...").Start(ctx, "Op")` + `defer span.End()` — `R-OBS-TRC-3`.
   - Атрибуты — бизнес-контекст (`order.id`, `payment.method`), не PII — `R-OBS-TRC-4`.
   - `trace.TraceIDRatioBased(0.01)` в `trace.ParentBased(...)` (1–10%); tail-based на ошибки в коллекторе — `R-OBS-TRC-5`.
   - `trace_id`/`span_id` в логах — через OTel-slog bridge, не вручную — `R-OBS-TRC-6`.
   - `trace.AlwaysSample()` в проде → `R-OBS-TRC-X1`.
   - PII в span attributes → `R-OBS-TRC-X2` (**критично**).
   - Manual span без `defer span.End()` → `R-OBS-TRC-X3` (в Go нет try-with-resources).
   - Горутина с `context.Background()` вместо родительского ctx → `R-OBS-TRC-X4`.

   ### Health checks (`R-OBS-HC-*`)
   - Раздельные `/health/live` (только «процесс жив», без внешних проверок) и `/health/ready` (с TTL-кешем проверки зависимостей) — `R-OBS-HC-1/2`.
   - `/info` (version, commit, build_time) на management-порту — `R-OBS-HC-3`.
   - Бизнес-состояние в health → `R-OBS-HC-X1`.
   - `/health/live` зависит от DB/Redis → `R-OBS-HC-X2` (**критично**, restart-loop).
   - Health-probe выполняет бизнес-операцию (`INSERT INTO health_check`) → `R-OBS-HC-X3`.

   ### Config (`R-OBS-CFG-*`)
   - Два `http.Server` в одном процессе: бизнес-порт (`router`) и management-порт (`/metrics`, `/health/*`, `/info`) — `R-OBS-CFG-1`.
   - Явный список endpoint'ов на management-сервере; без `pprof` в проде без auth — `R-OBS-CFG-2`.
   - Buckets гистограммы latency: `prometheus.DefBuckets` или кастомные для SLO (напр. p99 < 500ms) — `R-OBS-CFG-3`.
   - Уровень логов по `APP_ENV`; `slog.LevelVar` для runtime-изменения — `R-OBS-CFG-4`.
   - `net/http/pprof` без auth на публичной сети → `R-OBS-CFG-X1` (**критично**).
   - Один порт для бизнес + management → `R-OBS-CFG-X2`.
   - Все debug-эндпоинты без контроля доступа → `R-OBS-CFG-X3`.

   ### Context propagation (`R-OBS-CTX-*`)
   - `RequestID`-middleware первым в chi-цепочке: читает/генерирует `X-Request-Id`, кладёт в `context.Context` через typed key — `R-OBS-CTX-1`.
   - `trace_id`/`span_id` через OTel-slog bridge автоматически; не добавлять вручную через `ctx.Value(...)` — `R-OBS-CTX-2`.
   - Горутины получают родительский ctx явным аргументом (не захватывают из замыкания); `context.WithTimeout(ctx, ...)` для fan-out — `R-OBS-CTX-3`.
   - `userId` в ctx из auth-middleware после JWT-валидации (`golang-jwt`); хендлеры читают, не пишут в ctx — `R-OBS-CTX-4`.
   - Ctx захвачен из замыкания в долгоживущей горутине → `R-OBS-CTX-X1`.
   - `context.WithValue` в UseCase Handler / Domain Service для observability-полей → `R-OBS-CTX-X2`.
   - Горутина с `context.Background()` / без ctx → `R-OBS-CTX-X3` (**критично**, разрыв trace + потеря cancel).

   ### SLO и алерты (`R-OBS-SLO-*`)
   - SLO для каждого critical-endpoint; RED-гистограммы как источник данных для recording rules — `R-OBS-SLO-1`.
   - Multi-window multi-burn-rate alerts (1h × 14× burn + 6h × 6× burn); реализуется в Prometheus rules — `R-OBS-SLO-2`.
   - Alert на error budget < 10% за период — `R-OBS-SLO-3`.
   - Alerts отдельно от SLO-recording rules — `R-OBS-SLO-4`.
   - Alert на каждый ERROR в slog → `R-OBS-SLO-X1` (alert fatigue; используй `rate(app_errors_total{type="technical"}[5m]) > 0.1`).
   - SLO 100% target (нет error budget) → `R-OBS-SLO-X2`.
   - Alert без `annotations.runbook_url` → `R-OBS-SLO-X3`.

4. **Grep-паттерны для обязательной проверки:**
   - `fmt\.Println\|fmt\.Fprintf\(os\.Stderr` — вне slog-pipeline.
   - `slog\.Default()` — глобальный логгер без DI.
   - `context\.Background()` внутри горутин (не в main/setup) — разрыв trace.
   - `trace\.AlwaysSample()` — запрещено в проде.
   - `WithValue` в хендлерах/сервисах вне middleware.
   - `prometheus\.New[A-Za-z]*` без `promauto` — метрика без регистрации.

5. **Cross-check:** PII-гигиена → `ucp-go-auth-review` (`AUTH-16`); health внешних систем → `ucp-go-resilience-review`; `R-ERR-LOG-*`/`R-ERR-OBS-*` (`app_errors_total`, `span.RecordError`) → `ucp-go-error-handling-review`; wiring chi-middleware в bootstrap → `ucp-go-bootstrap-review`.

6. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

7. **Серьёзность** (`RFF-12`):
   - **Критично** — PII в логах (`R-OBS-LOG-X1`), PII в span attributes (`R-OBS-TRC-X2`), `user_id`/`order_id` как Prometheus label (`R-OBS-MTR-X1`), liveness зависит от DB/Redis (`R-OBS-HC-X2`), pprof без auth (`R-OBS-CFG-X1`), горутина с `context.Background()` (`R-OBS-CTX-X3`), `/metrics` на бизнес-порту без защиты (`R-OBS-MTR-X4`).
   - **Предупреждение** — `fmt.Println` вместо `slog` (`R-OBS-LOG-X2`), `AlwaysSample()` в проде (`R-OBS-TRC-X1`), manual span без `defer span.End()` (`R-OBS-TRC-X3`), один порт business+management (`R-OBS-CFG-X2`), alert на каждый ERROR (`R-OBS-SLO-X1`), ctx захвачен из замыкания в горутине (`R-OBS-CTX-X1`).
   - **Замечание** — INFO на каждый запрос в хендлерах (`R-OBS-LOG-X6`), нестандартные label-имена (`R-OBS-MTR-X2`), нет runbook (`R-OBS-SLO-X3`), `context.WithValue` в хендлере (`R-OBS-CTX-X2`).

## Что не входит

- PII-классификация/маскирование политики — `ucp-go-auth-review` (`AUTH-16`).
- Health внешних систем (TTL/probe-стратегия) — `ucp-go-resilience-review`.
- Wiring middleware/management в bootstrap — `ucp-go-bootstrap-review`.
- `R-ERR-LOG-*` / `R-ERR-OBS-*` (ошибки-значения, `app_errors_total`, `span.RecordError`) — `ucp-go-error-handling-review`.

$ARGUMENTS
