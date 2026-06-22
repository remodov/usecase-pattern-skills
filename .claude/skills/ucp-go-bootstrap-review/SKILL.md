---
name: ucp-go-bootstrap-review
lang: go
description: Ревью bootstrap Go-сервиса (net/http + chi) по UCP (коды GOBOOT-*) — envconfig fail-fast, конструкторная DI без глобалов, chi-middleware-стек, sqlc+pgx/v5 pool, graceful shutdown SIGTERM+atomic.Bool, health live/ready раздельно, slog по APP_ENV.
when_to_use: Изменения в cmd/server/main.go, internal/config/, internal/server/, internal/health/ или sqlc/pgxpool-wiring.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью bootstrap (Go / net/http + chi)

Ты ревьюишь bootstrap-слой Go-сервиса на соответствие `backend/go/go-bootstrap/go-bootstrap-rules.md` (`GOBOOT-*`).

## Зависимости

- **`.claude/docs/backend/go/go-bootstrap/go-bootstrap-rules.md`** — правила `GOBOOT-*` (единственный файл, содержит код-примеры).
- Парные: `backend/error-handling/error-handling-rules.md` + `backend/error-handling/go/error-handling-style-guide.md` (edge-renderer, recover-middleware `GOBOOT-10` / `R-ERR-MAP-5`), `backend/observability/observability-rules.md` (`GOBOOT-17/18` / `R-OBS-*`), `backend/resilience/resilience-rules.md` (`R-SHUT-*` — graceful shutdown cross-ref), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-16` — PII в логах, `AUTH-18/19` — JWT-middleware).

## Инструкции

1. **Прочти** `go-bootstrap-rules.md`. Цитируй конкретные коды (`GOBOOT-X2`), не только префикс.

2. **Скоп.** `cmd/server/main.go`, `internal/config/`, `internal/server/`, `internal/health/`, `db/` (sqlc-сгенерированный код), `docker-compose.yml`, `go.mod`, `git diff`.

3. **Прогон.**

   ### Конфигурация (`GOBOOT-2/3/4`)
   - `envconfig.Process` — единственная точка чтения env; нет `os.Getenv` россыпью → `GOBOOT-X1`.
   - `APP_ENV=local|integration-test|production` — три состояния; профиль гейтится по `cfg.Env`, не жёстким кодом → `GOBOOT-3`.
   - Required-поля без `default` — fail-fast при старте; секреты только из env/Vault, не в коде → `GOBOOT-4`.

   ### Точка входа и DI (`GOBOOT-5/6/7`)
   - `main.go` — только точка входа; вся логика — в `run()` → `GOBOOT-5`.
   - Зависимости собираются конструкторами (`New*(...)`) в `run()`; нет пакетных глобальных переменных `var db *pgxpool.Pool` → `GOBOOT-X2`.
   - Нет `init()` для инициализации ресурсов → `GOBOOT-X3`.
   - `Clock` / `IDGenerator` за интерфейсом; production-реализация в сборщике → `GOBOOT-7`.

   ### Router и middleware (`GOBOOT-8/9/10`)
   - Router — `chi.NewRouter()`; middleware-стек в строгом порядке: Recoverer → correlation-ID → logging → metrics → tracing → auth → `GOBOOT-8`.
   - Correlation-ID пробрасывается в `context.Context` и в ответ → `GOBOOT-9`.
   - Recoverer-middleware перехватывает panic → 500, логирует с трейсом → `GOBOOT-10`.
   - Health-эндпоинты зарегистрированы **до** бизнес-роутов → нарушение `GOBOOT-X4`, если наоборот.

   ### Persistence-wiring (`GOBOOT-11/12`)
   - Persistence — `sqlc` + `pgx/v5`; `pgxpool.Pool` один на сервис, создаётся в `run()`, закрывается `defer pool.Close()` → `GOBOOT-11`.
   - Миграции — `golang-migrate` или Flyway в CI/деплое; нет `CREATE TABLE` / DDL в `main()` → `GOBOOT-X5`.
   - Нет `pgx.Connect` на каждый запрос вместо пула → `GOBOOT-X6`.
   - README содержит quickstart: `docker compose up -d postgres && migrate ... up && go run ./cmd/server` → `GOBOOT-12`.

   ### Graceful shutdown (`GOBOOT-13/14`)
   - `signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)` → `GOBOOT-13`.
   - `appState.SetNotReady()` **до** `srv.Shutdown(shutCtx)` — readiness → 503 первым → `GOBOOT-13`.
   - Явный таймаут контекста (20–25s) для `Shutdown` → `GOBOOT-13`.
   - `http.Server.Close()` вместо `Shutdown()` — рвёт in-flight запросы → `GOBOOT-X7`.
   - `os.Exit(0)` внутри сервисной логики — пропускает `defer`-цепочку → `GOBOOT-X8`.
   - Фоновые goroutine завершаются через `context.Context` с отменой; ждёт `sync.WaitGroup` → `GOBOOT-14`.

   ### Health-эндпоинты (`GOBOOT-15/16`)
   - Два раздельных эндпоинта `/health/live` (200 всегда) и `/health/ready` (503 при деградации/shutdown) → `GOBOOT-15`.
   - Единый `/health` без разделения live/ready → `GOBOOT-X9`.
   - `/health/ready` делает `pool.Ping(ctx)` с таймаутом 2s → `GOBOOT-16`.

   ### Логирование и observability bootstrap (`GOBOOT-17/18/19`)
   - Логгер — `log/slog`; JSON-handler в production, Text-handler в local; инициализируется один раз в `run()`, `slog.SetDefault` → `GOBOOT-17`.
   - `log.Printf(...)` стандартной `log`-пакет вместо `slog` — нет структуры → `GOBOOT-X10`.
   - `/metrics` — chi-роут `promhttp.Handler()`; `TracerProvider` инициализируется в `run()`, закрывается `defer tp.Shutdown(ctx)` → `GOBOOT-18`.
   - Несколько `TracerProvider` в одном процессе → `GOBOOT-X11`.
   - PII не в логах (cross-ref `AUTH-16`); ошибки логируются один раз — в edge error-renderer (cross-ref `R-ERR-LOG-4`) → `GOBOOT-19`.

   ### Структура пакетов (`GOBOOT-20/21/22`)
   - Раскладка: `cmd/<name>/`, `internal/config/`, `internal/server/`, `internal/health/`, `internal/<domain>/`, `internal/<domain>/http/`, `internal/<domain>/postgres/`, `db/` → `GOBOOT-20`.
   - Доменный код `internal/<domain>/` не импортирует `net/http`, `pgx`, `chi` — только интерфейсы портов → `GOBOOT-21`.
   - Импорт `internal/<domain>/http` или `internal/<domain>/postgres` из `internal/<domain>/` — инверсия нарушена → `GOBOOT-X12`.
   - Общий пакет `utils/` / `helpers/` — заменить на `internal/timeutil/`, `internal/idgen/` → `GOBOOT-X13`.
   - `golangci-lint` с `errcheck`, `errorlint`, `govet`, `staticcheck` в CI → `GOBOOT-22`.

4. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

5. **Серьёзность** (`RFF-12`):
   - **Критично** — `GOBOOT-X2` (глобальный ресурс/pool), `GOBOOT-X3` (`init()` для ресурсов), `GOBOOT-X5` (DDL в main), `GOBOOT-X7` (`Server.Close()` вместо `Shutdown`), `GOBOOT-X8` (`os.Exit` внутри логики), `GOBOOT-X12` (доменный код импортирует адаптер), секрет в git.
   - **Предупреждение** — `GOBOOT-X1` (`os.Getenv` россыпью), `GOBOOT-X4` (бизнес-роуты до health), `GOBOOT-X6` (соединение на запрос вместо пула), `GOBOOT-X9` (единый health-эндпоинт), `GOBOOT-X10` (`log.Printf` вместо `slog`), `GOBOOT-X11` (несколько TracerProvider), отсутствие Recoverer-middleware.
   - **Замечание** — `GOBOOT-X13` (`utils/helpers`-пакет), нет README quickstart (`GOBOOT-12`), нет `golangci-lint` в CI, PII в логах (cross-ref `AUTH-16`).

## Что не входит

- Бизнес-операции — `ucp-go-pattern-review`. Обработка ошибок (apperr/Kind/edge-renderer) — `ucp-go-error-handling-review`. Валидация — `ucp-go-validation-review`. Graceful shutdown детально — `ucp-shutdown-review`. Auth/JWT детально — `ucp-go-auth-review`. Observability детально — `ucp-go-observability-review`.

$ARGUMENTS
