---
name: ucp-go-observability-design
lang: go
description: Спроектировать наблюдаемость Go-сервиса (net/http + chi) по UCP (коды R-OBS-*) — slog JSON/Text, prometheus/client_golang RED/USE через chi-middleware, OTel с otelpgx/otelhttp, health live/ready с TTL-кешем, management-порт, SLO + burn-rate alerts.
when_to_use: Триггеры — «настрой логи/метрики/трейсинг в Go», «slog», «prometheus на Go». При настройке observability Go-сервиса.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Observability — проектирование (Go / net/http + chi)

Ты проектируешь наблюдаемость по **контракту** `backend/observability/observability-rules.md` (`R-OBS-*`) и
**Go-реализации** `backend/observability/go/observability-style-guide.md`. Помни: в Go контекст передаётся явно
через `context.Context` (нет thread-local/MDC); логгер — через конструкторную DI, не глобальный; span закрывается
через `defer span.End()` (нет try-with-resources).

## Инструкции

1. **Прочитай** контракт + Go-style-guide. Коды в обосновании, не в коде. Связанные: `backend/error-handling/go/error-handling-style-guide.md` (`R-ERR-OBS-1` — `app_errors_total` в edge-renderer), `backend/resilience/go/resilience-style-guide.md` (health-check внешних систем), `backend/auth-patterns/go/auth-patterns-style-guide.md` (PII-гигиена `AUTH-16`, `AUTH-18`).

2. **Logging** (`R-OBS-LOG-*`): `log/slog` JSON в проде / Text локально по `APP_ENV`; логгер через конструктор-DI (`.With("component", "...")`) — никаких `slog.Default()`; структурные поля через key-value аргументы (`slog.String`, `slog.Int64`), не fmt-форматирование; уровни по семантике (INFO значимые события, WARN Domain/Validation-ошибки, ERROR — panic/Technical/Integration при открытом CB); `traceId`/`spanId` — автоматически через OTel-slog bridge (`go.opentelemetry.io/contrib/bridges/otelslog`); `requestId`/`userId` — через chi-middleware в `context.Context`, нет PII; нет `fmt.Println`/`fmt.Fprintf(os.Stderr)`.

3. **Metrics** (`R-OBS-MTR-*`): `github.com/prometheus/client_golang` + `promauto`; `/metrics` через `promhttp.Handler()` на **отдельном management-порту**; стандартные labels `service`/`env`/`version`; RED для HTTP через chi-middleware (`http_requests_total` + `http_request_duration_seconds`), path — chi route pattern (`chi.RouteContext(r.Context()).RoutePattern()`), не raw URL; USE через `collectors.NewGoCollector()` + `collectors.NewProcessCollector`; бизнес-`CounterVec`/`Histogram`; snake_case+единица; **низкая cardinality** (не `user_id`/`order_id`).

4. **Tracing** (`R-OBS-TRC-*`): OTel автоинструментация — `otelhttp.NewHandler(router, ...)` на chi-роутере, `otelhttp.NewTransport` на HTTP-клиентах, `otelpgx` на pgx-пуле, ручная propagation через `otel.GetTextMapPropagator()` для kafka-go (segmentio); manual span через `ctx, span := otel.Tracer("...").Start(ctx, "...")` + `defer span.End()`; атрибуты бизнес-контекста без PII; sampling `trace.TraceIDRatioBased` (1–10%) + `trace.ParentBased`; 100% errors — tail-based sampling в OTel Collector; `trace_id` в логах через OTel-slog bridge.

5. **Health** (`R-OBS-HC-*`): раздельные `/health/live` (только «процесс жив», без внешних систем) + `/health/ready` (pgxpool.Ping, go-redis Ping); custom-checker с TTL-кешем результата (`sync.Mutex` + `lastOK time.Time`) — не дёргать БД/Redis на каждый probe; `/info` (version/commit/build_time).

6. **Config/Context** (`R-OBS-CFG/CTX-*`): два `http.Server` в одном процессе — бизнес-порт и management-порт; management содержит только `/metrics`, `/health/live`, `/health/ready`, `/info`; `RequestID`-middleware первым в chi-цепочке (`r.Use(RequestID)` → `r.Use(otelhttp.Middleware)` → `r.Use(middleware.Logger)`); `Auth`-middleware кладёт `userId` в `context.Context`; контекст пробрасывается в горутины явным аргументом (не захват из замыкания); нет `context.WithValue` в UseCase Handler или Domain Service.

7. **SLO** (`R-OBS-SLO-*`): SLO recording rules из RED-гистограмм + multi-window burn-rate alerts (1h/6h) + alert на error budget < 10% + runbook. Самопроверка (§8) + предложи `ucp-go-observability-review`.

## Антипаттерны, которые НЕ генерировать

- PII в логах/спанах (`R-OBS-LOG-X1`/`R-OBS-TRC-X2`); `fmt.Println`/`fmt.Fprintf(os.Stderr)` (`R-OBS-LOG-X2`); ошибка строкой (`log.ErrorContext(ctx, err.Error())`) вместо атрибута (`R-OBS-LOG-X4`).
- High-cardinality labels (`R-OBS-MTR-X1`); raw URL вместо chi route pattern в label (`R-OBS-MTR-X2`); `/metrics` без сетевой защиты (`R-OBS-MTR-X4`).
- `trace.AlwaysSample()` в проде (`R-OBS-TRC-X1`); PII в span attributes (`R-OBS-TRC-X2`); manual span без `defer span.End()` (`R-OBS-TRC-X3`); горутина с `context.Background()` — разрыв trace (`R-OBS-TRC-X4`).
- Liveness зависит от DB/Redis (`R-OBS-HC-X2`); бизнес-состояние в health (`R-OBS-HC-X1`); health-probe делает бизнес-операцию (`R-OBS-HC-X3`).
- Один порт business+management (`R-OBS-CFG-X2`); pprof без auth в проде (`R-OBS-CFG-X1`).
- `context.WithValue` в UseCase Handler/Domain (`R-OBS-CTX-X2`); ctx захвачен из замыкания в горутине (`R-OBS-CTX-X1`); горутина без `ctx` аргумента (`R-OBS-CTX-X3`).
- Alert на каждый ERROR (`R-OBS-SLO-X1`); SLO 100% (`R-OBS-SLO-X2`); alert без runbook (`R-OBS-SLO-X3`).

После работы скилла — обязательно `ucp-go-observability-review`.

$ARGUMENTS
