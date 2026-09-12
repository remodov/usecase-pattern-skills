---
name: ucp-go-bootstrap-review
lang: go
description: Ревью bootstrap Go-сервиса (net/http + chi) по UCP — envconfig fail-fast, конструкторная DI без глобалов, chi-middleware-стек, sqlc+pgx/v5 pool, graceful shutdown SIGTERM+atomic.Bool, health live/ready раздельно, slog по APP_ENV.
when_to_use: Изменения в cmd/server/main.go, internal/config/, internal/server/, internal/health/ или sqlc/pgxpool-wiring.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью bootstrap (Go / net/http + chi)

Ты ревьюишь bootstrap-слой Go-сервиса на соответствие `backend/go/go-bootstrap/spec.md` (`GOBOOT-*`).

## Зависимости

- **`.claude/docs/backend/go/go-bootstrap/spec.md`** — правила `GOBOOT-*` (единственный файл, содержит код-примеры).
- Парные: `backend/error-handling/spec.md` + `backend/error-handling/references/go/implementation.md` (edge-renderer, recover-middleware `go-bootstrap/recover-at-edge` / `error-handling/integration-and-technical-mapping`), `backend/observability/spec.md` (`GOBOOT-17/18` / `R-OBS-*`), `backend/resilience/spec.md` (`R-SHUT-*` — graceful shutdown cross-ref), `backend/auth-patterns/spec.md` (`auth-patterns/no-pii-in-logs-and-events` — PII в логах, `AUTH-18/19` — JWT-middleware).

## Инструкции

1. **Прочти** `go-bootstrap/spec.md`. Цитируй конкретные коды (`go-bootstrap/dependencies-via-constructors`), не только префикс.

2. **Скоп.** `cmd/server/main.go`, `internal/config/`, `internal/server/`, `internal/health/`, `db/` (sqlc-сгенерированный код), `docker-compose.yml`, `go.mod`, `git diff`.

3. **Прогон.**

   ### Конфигурация (`GOBOOT-2/3/4`)
   - `envconfig.Process` — единственная точка чтения env; нет `os.Getenv` россыпью → `go-bootstrap/single-config-object`.
   - `APP_ENV=local|integration-test|production` — три состояния; профиль гейтится по `cfg.Env`, не жёстким кодом → `go-bootstrap/profile-from-environment`.
   - Required-поля без `default` — fail-fast при старте; секреты только из env/Vault, не в коде → `go-bootstrap/config-is-typed-and-validated`.

   ### Точка входа и DI (`GOBOOT-5/6/7`)
   - `main.go` — только точка входа; вся логика — в `run()` → `go-bootstrap/main-only-starts`.
   - Зависимости собираются конструкторами (`New*(...)`) в `run()`; нет пакетных глобальных переменных `var db *pgxpool.Pool` → `go-bootstrap/dependencies-via-constructors`.
   - Нет `init()` для инициализации ресурсов → `go-bootstrap/dependencies-via-constructors`.
   - `Clock` / `IDGenerator` за интерфейсом; production-реализация в сборщике → `go-bootstrap/clock-and-ids-behind-interfaces`.

   ### Router и middleware (`GOBOOT-8/9/10`)
   - Router — `chi.NewRouter()`; middleware-стек в строгом порядке: Recoverer → correlation-ID → logging → metrics → tracing → auth → `go-bootstrap/middleware-order`.
   - Correlation-ID пробрасывается в `context.Context` и в ответ → `go-bootstrap/correlation-id-in-context`.
   - Recoverer-middleware перехватывает panic → 500, логирует с трейсом → `go-bootstrap/recover-at-edge`.
   - Health-эндпоинты зарегистрированы **до** бизнес-роутов → нарушение `go-bootstrap/health-routes-first`, если наоборот.

   ### Persistence-wiring (`GOBOOT-11/12`)
   - Persistence — `sqlc` + `pgx/v5`; `pgxpool.Pool` один на сервис, создаётся в `run()`, закрывается `defer pool.Close()` → `go-bootstrap/pool-and-migrations`.
   - Миграции — `golang-migrate` или Flyway в CI/деплое; нет `CREATE TABLE` / DDL в `main()` → `go-bootstrap/pool-and-migrations`.
   - Нет `pgx.Connect` на каждый запрос вместо пула → `go-bootstrap/pool-and-migrations`.
   - README содержит quickstart: `docker compose up -d postgres && migrate ... up && go run ./cmd/server` → `go-bootstrap/local-quickstart-documented`.

   ### Graceful shutdown (`GOBOOT-13/14`)
   - `signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)` → `go-bootstrap/graceful-shutdown`.
   - `appState.SetNotReady()` **до** `srv.Shutdown(shutCtx)` — readiness → 503 первым → `go-bootstrap/graceful-shutdown`.
   - Явный таймаут контекста (20–25s) для `Shutdown` → `go-bootstrap/graceful-shutdown`.
   - `http.Server.Close()` вместо `Shutdown()` — рвёт in-flight запросы → `go-bootstrap/graceful-shutdown`.
   - `os.Exit(0)` внутри сервисной логики — пропускает `defer`-цепочку → `go-bootstrap/graceful-shutdown`.
   - Фоновые goroutine завершаются через `context.Context` с отменой; ждёт `sync.WaitGroup` → `go-bootstrap/background-goroutines-awaited`.

   ### Health-эндпоинты (`GOBOOT-15/16`)
   - Два раздельных эндпоинта `/health/live` (200 всегда) и `/health/ready` (503 при деградации/shutdown) → `go-bootstrap/liveness-and-readiness-split`.
   - Единый `/health` без разделения live/ready → `go-bootstrap/liveness-and-readiness-split`.
   - `/health/ready` делает `pool.Ping(ctx)` с таймаутом 2s → `go-bootstrap/liveness-and-readiness-split`.

   ### Логирование и observability bootstrap (`GOBOOT-17/18/19`)
   - Логгер — `log/slog`; JSON-handler в production, Text-handler в local; инициализируется один раз в `run()`, `slog.SetDefault` → `go-bootstrap/structured-logging`.
   - `log.Printf(...)` стандартной `log`-пакет вместо `slog` — нет структуры → `go-bootstrap/structured-logging`.
   - `/metrics` — chi-роут `promhttp.Handler()`; `TracerProvider` инициализируется в `run()`, закрывается `defer tp.Shutdown(ctx)` → `go-bootstrap/metrics-and-tracing-initialized-once`.
   - Несколько `TracerProvider` в одном процессе → `go-bootstrap/metrics-and-tracing-initialized-once`.
   - PII не в логах (cross-ref `auth-patterns/no-pii-in-logs-and-events`); ошибки логируются один раз — в edge error-renderer (cross-ref `error-handling/log-once-with-exception`) → `go-bootstrap/no-pii-log-once`.

   ### Структура пакетов (`GOBOOT-20/21/22`)
   - Раскладка: `cmd/<name>/`, `internal/config/`, `internal/server/`, `internal/health/`, `internal/<domain>/`, `internal/<domain>/http/`, `internal/<domain>/postgres/`, `db/` → `go-bootstrap/package-layout-directs-inward`.
   - Доменный код `internal/<domain>/` не импортирует `net/http`, `pgx`, `chi` — только интерфейсы портов → `go-bootstrap/package-layout-directs-inward`.
   - Импорт `internal/<domain>/http` или `internal/<domain>/postgres` из `internal/<domain>/` — инверсия нарушена → `GOBOOT-X12`.
   - Общий пакет `utils/` / `helpers/` — заменить на `internal/timeutil/`, `internal/idgen/` → `GOBOOT-X13`.
   - `golangci-lint` с `errcheck`, `errorlint`, `govet`, `staticcheck` в CI → `go-bootstrap/lint-and-format-required`.

4. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

5. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `go-bootstrap/dependencies-via-constructors` (глобальный ресурс/pool), `go-bootstrap/dependencies-via-constructors` (`init()` для ресурсов), `go-bootstrap/pool-and-migrations` (DDL в main), `go-bootstrap/graceful-shutdown` (`Server.Close()` вместо `Shutdown`), `go-bootstrap/graceful-shutdown` (`os.Exit` внутри логики), `GOBOOT-X12` (доменный код импортирует адаптер), секрет в git.
   - **Предупреждение** — `go-bootstrap/single-config-object` (`os.Getenv` россыпью), `go-bootstrap/health-routes-first` (бизнес-роуты до health), `go-bootstrap/pool-and-migrations` (соединение на запрос вместо пула), `go-bootstrap/liveness-and-readiness-split` (единый health-эндпоинт), `go-bootstrap/structured-logging` (`log.Printf` вместо `slog`), `go-bootstrap/metrics-and-tracing-initialized-once` (несколько TracerProvider), отсутствие Recoverer-middleware.
   - **Замечание** — `GOBOOT-X13` (`utils/helpers`-пакет), нет README quickstart (`go-bootstrap/local-quickstart-documented`), нет `golangci-lint` в CI, PII в логах (cross-ref `auth-patterns/no-pii-in-logs-and-events`).

## Что не входит

- Бизнес-операции — `ucp-go-pattern-review`. Обработка ошибок (apperr/Kind/edge-renderer) — `ucp-go-error-handling-review`. Валидация — `ucp-go-validation-review`. Graceful shutdown детально — `ucp-shutdown-review`. Auth/JWT детально — `ucp-go-auth-review`. Observability детально — `ucp-go-observability-review`.

$ARGUMENTS
