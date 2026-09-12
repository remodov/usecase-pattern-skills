---
name: ucp-go-observability-design
lang: go
description: Спроектировать наблюдаемость Go-сервиса (net/http + chi) по UCP — slog JSON/Text, prometheus/client_golang RED/USE через chi-middleware, OTel с otelpgx/otelhttp, health live/ready с TTL-кешем, management-порт, SLO + burn-rate alerts.
when_to_use: Триггеры — «настрой логи/метрики/трейсинг в Go», «slog», «prometheus на Go». При настройке observability Go-сервиса.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Observability — проектирование (Go / net/http + chi)

Ты проектируешь наблюдаемость по **контракту** `backend/observability/spec.md` (`R-OBS-*`) и
**Go-реализации** `backend/observability/references/go/implementation.md`. Помни: в Go контекст передаётся явно
через `context.Context` (нет thread-local/MDC); логгер — через конструкторную DI, не глобальный; span закрывается
через `defer span.End()` (нет try-with-resources).

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды в обосновании, не в коде. Связанные: `backend/error-handling/references/go/implementation.md` (`error-handling/errors-counted-by-kind` — `app_errors_total` в edge-renderer), `backend/resilience/references/go/implementation.md` (health-check внешних систем), `backend/auth-patterns/references/go/implementation.md` (PII-гигиена `auth-patterns/no-pii-in-logs-and-events`, `auth-patterns/error-response-hides-cause`).

2. **Logging** (`R-OBS-LOG-*`): `log/slog` JSON в проде / Text локально по `APP_ENV`; логгер через конструктор-DI (`.With("component", "...")`) — никаких `slog.Default()`; структурные поля через key-value аргументы (`slog.String`, `slog.Int64`), не fmt-форматирование; уровни по семантике (INFO значимые события, WARN Domain/Validation-ошибки, ERROR — panic/Technical/Integration при открытом CB); `traceId`/`spanId` — автоматически через OTel-slog bridge (`go.opentelemetry.io/contrib/bridges/otelslog`); `requestId`/`userId` — через chi-middleware в `context.Context`, нет PII; нет `fmt.Println`/`fmt.Fprintf(os.Stderr)`.

3. **Metrics** (`R-OBS-MTR-*`): `github.com/prometheus/client_golang` + `promauto`; `/metrics` через `promhttp.Handler()` на **отдельном management-порту**; стандартные labels `service`/`env`/`version`; RED для HTTP через chi-middleware (`http_requests_total` + `http_request_duration_seconds`), path — chi route pattern (`chi.RouteContext(r.Context()).RoutePattern()`), не raw URL; USE через `collectors.NewGoCollector()` + `collectors.NewProcessCollector`; бизнес-`CounterVec`/`Histogram`; snake_case+единица; **низкая cardinality** (не `user_id`/`order_id`).

4. **Tracing** (`R-OBS-TRC-*`): OTel автоинструментация — `otelhttp.NewHandler(router, ...)` на chi-роутере, `otelhttp.NewTransport` на HTTP-клиентах, `otelpgx` на pgx-пуле, ручная propagation через `otel.GetTextMapPropagator()` для kafka-go (segmentio); manual span через `ctx, span := otel.Tracer("...").Start(ctx, "...")` + `defer span.End()`; атрибуты бизнес-контекста без PII; sampling `trace.TraceIDRatioBased` (1–10%) + `trace.ParentBased`; 100% errors — tail-based sampling в OTel Collector; `trace_id` в логах через OTel-slog bridge.

5. **Health** (`R-OBS-HC-*`): раздельные `/health/live` (только «процесс жив», без внешних систем) + `/health/ready` (pgxpool.Ping, go-redis Ping); custom-checker с TTL-кешем результата (`sync.Mutex` + `lastOK time.Time`) — не дёргать БД/Redis на каждый probe; `/info` (version/commit/build_time).

6. **Config/Context** (`R-OBS-CFG/CTX-*`): два `http.Server` в одном процессе — бизнес-порт и management-порт; management содержит только `/metrics`, `/health/live`, `/health/ready`, `/info`; `RequestID`-middleware первым в chi-цепочке (`r.Use(RequestID)` → `r.Use(otelhttp.Middleware)` → `r.Use(middleware.Logger)`); `Auth`-middleware кладёт `userId` в `context.Context`; контекст пробрасывается в горутины явным аргументом (не захват из замыкания); нет `context.WithValue` в UseCase Handler или Domain Service.

7. **SLO** (`R-OBS-SLO-*`): SLO recording rules из RED-гистограмм + multi-window burn-rate alerts (1h/6h) + alert на error budget < 10% + runbook. Самопроверка (§8) + предложи `ucp-go-observability-review`.

## Антипаттерны, которые НЕ генерировать

- PII в логах/спанах (`observability/no-pii-in-logs`/`observability/manual-spans-are-closed`); `fmt.Println`/`fmt.Fprintf(os.Stderr)` (`observability/no-direct-stdout-logging`); ошибка строкой (`log.ErrorContext(ctx, err.Error())`) вместо атрибута (`observability/parameterized-log-messages`).
- High-cardinality labels (`observability/low-cardinality-labels`); raw URL вместо chi route pattern в label (`observability/standard-metric-dimensions`); `/metrics` без сетевой защиты (`observability/management-endpoints-restricted`).
- `trace.AlwaysSample()` в проде (`observability/sampling-strategy`); PII в span attributes (`observability/manual-spans-are-closed`); manual span без `defer span.End()` (`observability/manual-spans-are-closed`); горутина с `context.Background()` — разрыв trace (`observability/context-propagated-to-async`).
- Liveness зависит от DB/Redis (`observability/liveness-and-readiness-split`); бизнес-состояние в health (`observability/health-check-is-technical`); health-probe делает бизнес-операцию (`observability/health-check-is-technical`).
- Один порт business+management (`observability/separate-management-port`); pprof без auth в проде (`observability/management-endpoints-restricted`).
- `context.WithValue` в UseCase Handler/Domain (`observability/context-set-at-edge-and-cleared`); ctx захвачен из замыкания в горутине (`observability/context-set-at-edge-and-cleared`); горутина без `ctx` аргумента (`observability/context-propagated-to-async`).
- Alert на каждый ERROR (`observability/burn-rate-alerting`); SLO 100% (`observability/slo-with-error-budget`); alert без runbook (`observability/alerts-have-runbooks`).

После работы скилла — обязательно `ucp-go-observability-review`.

$ARGUMENTS
