---
name: ucp-go-bootstrap-design
lang: go
description: Спроектировать или починить bootstrap Go-сервиса (net/http + chi) по UCP (коды GOBOOT-*) — envconfig fail-fast, конструкторная DI без синглтонов, chi-middleware-стек, sqlc+pgx/v5, graceful shutdown с SIGTERM, health live/ready, slog+prometheus+OTel.
when_to_use: Триггеры — «настрой bootstrap Go-сервиса», «конструкторная DI + chi», «почему сервис не стартует». При старте сервиса или падении на конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*) Bash(golangci-lint*)
---

# Проектирование bootstrap (Go / net/http + chi)

Ты настраиваешь bootstrap-слой Go-сервиса по UCP согласно `backend/go/go-bootstrap/go-bootstrap-rules.md`
(`GOBOOT-*`). Цель — сервис стартует локально одной командой, конфиг валидируется fail-fast, ресурсы собираются
конструкторной DI, chi-роутер с полным middleware-стеком, graceful shutdown через SIGTERM.

## Инструкции

1. **Прочитай** `.claude/docs/backend/go/go-bootstrap/go-bootstrap-rules.md` (`GOBOOT-*`). Связанные по кодам:
   `backend/error-handling/go/error-handling-style-guide.md` (edge error-renderer, `R-ERR-*`),
   `backend/validation/go/validation-style-guide.md` (валидация входа, `R-VLD-*`),
   `backend/observability/go/observability-style-guide.md` (slog/OTel/prometheus, `R-OBS-*`),
   `backend/graceful-shutdown/go/graceful-shutdown-style-guide.md` (SIGTERM, `R-SHUT-*`).

2. **Диагноз: починка или с нуля.** Для починки воспроизведи ошибку (`go run ./cmd/server`); пройди
   Quickstart-чеклист (§ конец rules) — missing env / ресурс в глобале / нет миграций / отсутствует `APP_ENV`.

3. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев — соответствие выражается именами/типами/структурой;
   коды правил в коде НЕ цитируй):

   ### 3.1 `internal/config/config.go` — конфигурация
   `Config`-структура с тегами `envconfig`; обязательные поля без `default`; `Load() (Config, error)` через
   `envconfig.Process("", &cfg)` (`GOBOOT-2/4`). `APP_ENV=local|integration-test|production`.

   ### 3.2 `cmd/server/main.go` — точка входа
   `main()` вызывает `run()`, при ошибке `slog.Error` + `os.Exit(1)`. Вся логика — в `run()`: загрузка конфига,
   инициализация логгера, создание пула, конструкторная сборка репозиториев / хендлеров / контроллеров,
   вызов `server.Run(...)` (`GOBOOT-5/6`). Нет глобальных переменных с ресурсами.

   ### 3.3 `internal/config/interfaces.go` — источники недетерминизма
   Интерфейсы `Clock` и `IDGenerator`; production-реализации (`realclock`, `uuidgen`) в пакетах `internal/timeutil/`
   и `internal/idgen/`; в `run()` создаются и передаются в хендлеры (`GOBOOT-7`).

   ### 3.4 `internal/server/router.go` — chi-роутер
   `buildRouter(...)` собирает `chi.NewRouter()` с полным middleware-стеком: `Recoverer`, `correlationid.Middleware`,
   `httplog.RequestLogger(slog.Default())`, `httpmetrics.Middleware`, `tracing.Middleware`. Регистрирует
   `/health/live`, `/health/ready` перед API-роутами. JWT-middleware (`authmw.JWTMiddleware`) — только если
   `cfg.Env != "local"` (`GOBOOT-8/9/10`).

   ### 3.5 Persistence-wiring
   `pgxpool.NewWithConfig` с `MaxConns/MinConns` в `run()`, `defer pool.Close()`. `sqlc`-сгенерированный пакет `db`
   получает пул. Миграции — `golang-migrate` в CI/деплое, не в `main()` (`GOBOOT-11`).

   ### 3.6 `internal/server/server.go` — graceful shutdown
   `signal.Notify` на `syscall.SIGTERM` + `syscall.SIGINT`; `appState.SetNotReady()` до вызова
   `srv.Shutdown(shutCtx)`; таймаут shutdown 20–25s через `context.WithTimeout` (`GOBOOT-13`). Фоновые
   goroutine (Kafka consumer, scheduler) — через общий `context.Context` + `sync.WaitGroup` (`GOBOOT-14`).

   ### 3.7 `internal/health/handler.go` — health-эндпоинты
   Два раздельных хендлера: `LiveHandler()` всегда 200; `ReadyHandler(s *State, pool *pgxpool.Pool)` — проверяет
   `s.IsReady()` + `pool.Ping` с таймаутом 2s, 503 при деградации или в фазе shutdown (`GOBOOT-15/16`).

   ### 3.8 Observability bootstrap
   `initLogger(env string)` — JSON-handler в production, Text-handler в local, `slog.SetDefault(...)`. `TracerProvider`
   от `go.opentelemetry.io/otel` инициализируется в `run()`, `defer tp.Shutdown(ctx)`. `/metrics` → `promhttp.Handler()`
   (`GOBOOT-17/18`).

   ### 3.9 README quickstart
   Раздел «Запуск локально»: `docker compose up -d postgres && migrate -path migrations -database $DATABASE_URL up && go run ./cmd/server` (`GOBOOT-12`).

4. **Структура пакетов** — строго по `GOBOOT-20/21`:
   ```
   cmd/<name>/          # main.go + run()
   internal/
     config/            # Config + Load()
     server/            # router.go + server.go
     health/            # handler.go + State
     timeutil/          # Clock-реализация
     idgen/             # IDGenerator-реализация
     <domain>/          # домен + usecases + интерфейсы портов
     <domain>/http/     # chi-контроллер
     <domain>/postgres/ # pgx/sqlc-репозиторий
   db/                  # sqlc-сгенерированный код
   migrations/          # SQL-миграции (golang-migrate)
   ```
   Доменный код не импортирует `net/http`, `pgx`, `chi` — только интерфейсы портов.

5. **Самопроверка** — Quickstart-чеклист из `go-bootstrap-rules.md`:
   `APP_ENV` выставлен; `envconfig.Process` не упал; Postgres поднят и миграции накатаны;
   ресурсы в `run()`, не в `init()` / глобальных переменных; JWT off на `local`; `/health/ready` → 200;
   `golangci-lint run` с `errcheck`/`errorlint`/`govet`/`staticcheck` чист (`GOBOOT-22`).

6. **Финальный шаг:** предложи `ucp-go-bootstrap-review`; для бизнес-операций — `ucp-go-pattern-design`.

## Антипаттерны, которые НЕ генерировать

- `os.Getenv(...)` россыпью вместо единственного `Config` (`GOBOOT-X1`).
- `var pool *pgxpool.Pool` на уровне пакета (`GOBOOT-X2`); `init()` для инициализации ресурсов (`GOBOOT-X3`).
- Бизнес-роуты до `/health/*` (`GOBOOT-X4`).
- DDL / `CREATE TABLE` в `main()` вместо миграционного инструмента (`GOBOOT-X5`); открытие нового соединения на каждый запрос вместо пула (`GOBOOT-X6`).
- `http.Server.Close()` вместо `Shutdown` (`GOBOOT-X7`); `os.Exit(0)` внутри сервисной логики (`GOBOOT-X8`).
- Объединение `/health/live` и `/health/ready` в один эндпоинт (`GOBOOT-X9`).
- `log.Printf(...)` вместо `slog` (`GOBOOT-X10`); несколько `TracerProvider` на процесс (`GOBOOT-X11`).
- Импорт `internal/<domain>/http` или `internal/<domain>/postgres` из доменного пакета (`GOBOOT-X12`).
- Пакет `utils/` или `helpers/` — заменить на `internal/timeutil/`, `internal/idgen/` и т.п. (`GOBOOT-X13`).

После работы скилла — обязательно `ucp-go-bootstrap-review`.

$ARGUMENTS
