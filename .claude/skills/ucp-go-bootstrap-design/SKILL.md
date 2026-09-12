---
name: ucp-go-bootstrap-design
lang: go
description: Спроектировать или починить bootstrap Go-сервиса (net/http + chi) по UCP — envconfig fail-fast, конструкторная DI без синглтонов, chi-middleware-стек, sqlc+pgx/v5, graceful shutdown с SIGTERM, health live/ready, slog+prometheus+OTel.
when_to_use: Триггеры — «настрой bootstrap Go-сервиса», «конструкторная DI + chi», «почему сервис не стартует». При старте сервиса или падении на конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*) Bash(golangci-lint*)
---

# Проектирование bootstrap (Go / net/http + chi)

Ты настраиваешь bootstrap-слой Go-сервиса по UCP согласно `backend/go/go-bootstrap/spec.md`
(`GOBOOT-*`). Цель — сервис стартует локально одной командой, конфиг валидируется fail-fast, ресурсы собираются
конструкторной DI, chi-роутер с полным middleware-стеком, graceful shutdown через SIGTERM.

## Инструкции

1. **Прочитай** `.claude/docs/backend/go/go-bootstrap/spec.md` (`GOBOOT-*`). Связанные по кодам:
   `backend/error-handling/references/go/implementation.md` (edge error-renderer, `R-ERR-*`),
   `backend/validation/references/go/implementation.md` (валидация входа, `R-VLD-*`),
   `backend/observability/references/go/implementation.md` (slog/OTel/prometheus, `R-OBS-*`),
   `backend/graceful-shutdown/references/go/implementation.md` (SIGTERM, `R-SHUT-*`).

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
   и `internal/idgen/`; в `run()` создаются и передаются в хендлеры (`go-bootstrap/clock-and-ids-behind-interfaces`).

   ### 3.4 `internal/server/router.go` — chi-роутер
   `buildRouter(...)` собирает `chi.NewRouter()` с полным middleware-стеком: `Recoverer`, `correlationid.Middleware`,
   `httplog.RequestLogger(slog.Default())`, `httpmetrics.Middleware`, `tracing.Middleware`. Регистрирует
   `/health/live`, `/health/ready` перед API-роутами. JWT-middleware (`authmw.JWTMiddleware`) — только если
   `cfg.Env != "local"` (`GOBOOT-8/9/10`).

   ### 3.5 Persistence-wiring
   `pgxpool.NewWithConfig` с `MaxConns/MinConns` в `run()`, `defer pool.Close()`. `sqlc`-сгенерированный пакет `db`
   получает пул. Миграции — `golang-migrate` в CI/деплое, не в `main()` (`go-bootstrap/pool-and-migrations`).

   ### 3.6 `internal/server/server.go` — graceful shutdown
   `signal.Notify` на `syscall.SIGTERM` + `syscall.SIGINT`; `appState.SetNotReady()` до вызова
   `srv.Shutdown(shutCtx)`; таймаут shutdown 20–25s через `context.WithTimeout` (`go-bootstrap/graceful-shutdown`). Фоновые
   goroutine (Kafka consumer, scheduler) — через общий `context.Context` + `sync.WaitGroup` (`go-bootstrap/background-goroutines-awaited`).

   ### 3.7 `internal/health/handler.go` — health-эндпоинты
   Два раздельных хендлера: `LiveHandler()` всегда 200; `ReadyHandler(s *State, pool *pgxpool.Pool)` — проверяет
   `s.IsReady()` + `pool.Ping` с таймаутом 2s, 503 при деградации или в фазе shutdown (`GOBOOT-15/16`).

   ### 3.8 Observability bootstrap
   `initLogger(env string)` — JSON-handler в production, Text-handler в local, `slog.SetDefault(...)`. `TracerProvider`
   от `go.opentelemetry.io/otel` инициализируется в `run()`, `defer tp.Shutdown(ctx)`. `/metrics` → `promhttp.Handler()`
   (`GOBOOT-17/18`).

   ### 3.9 README quickstart
   Раздел «Запуск локально»: `docker compose up -d postgres && migrate -path migrations -database $DATABASE_URL up && go run ./cmd/server` (`go-bootstrap/local-quickstart-documented`).

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

5. **Самопроверка** — Quickstart-чеклист из `go-bootstrap/spec.md`:
   `APP_ENV` выставлен; `envconfig.Process` не упал; Postgres поднят и миграции накатаны;
   ресурсы в `run()`, не в `init()` / глобальных переменных; JWT off на `local`; `/health/ready` → 200;
   `golangci-lint run` с `errcheck`/`errorlint`/`govet`/`staticcheck` чист (`go-bootstrap/lint-and-format-required`).

6. **Финальный шаг:** предложи `ucp-go-bootstrap-review`; для бизнес-операций — `ucp-go-pattern-design`.

## Антипаттерны, которые НЕ генерировать

- `os.Getenv(...)` россыпью вместо единственного `Config` (`go-bootstrap/single-config-object`).
- `var pool *pgxpool.Pool` на уровне пакета (`go-bootstrap/dependencies-via-constructors`); `init()` для инициализации ресурсов (`go-bootstrap/dependencies-via-constructors`).
- Бизнес-роуты до `/health/*` (`go-bootstrap/health-routes-first`).
- DDL / `CREATE TABLE` в `main()` вместо миграционного инструмента (`go-bootstrap/pool-and-migrations`); открытие нового соединения на каждый запрос вместо пула (`go-bootstrap/pool-and-migrations`).
- `http.Server.Close()` вместо `Shutdown` (`go-bootstrap/graceful-shutdown`); `os.Exit(0)` внутри сервисной логики (`go-bootstrap/graceful-shutdown`).
- Объединение `/health/live` и `/health/ready` в один эндпоинт (`go-bootstrap/liveness-and-readiness-split`).
- `log.Printf(...)` вместо `slog` (`go-bootstrap/structured-logging`); несколько `TracerProvider` на процесс (`go-bootstrap/metrics-and-tracing-initialized-once`).
- Импорт `internal/<domain>/http` или `internal/<domain>/postgres` из доменного пакета (`GOBOOT-X12`).
- Пакет `utils/` или `helpers/` — заменить на `internal/timeutil/`, `internal/idgen/` и т.п. (`GOBOOT-X13`).

После работы скилла — обязательно `ucp-go-bootstrap-review`.

$ARGUMENTS

## Гейты проекта

Каталог — `.claude/docs/_meta/project-gates.md`. Эти проверки методология
определяет сама, и генерируешь их **ты**: пока их нет в проекте, требования,
которые на них ссылаются, фактически держатся ревью.

Сгенерируй четыре скрипта и привяжи их к общей задаче проверки и в конвейер:

| Скрипт | Что читает | Что делает |
| --- | --- | --- |
| `ddl-check` | файлы миграций | разбирает объявления таблиц, колонок, индексов и ограничений; проверяет типы, именование, безопасность изменений |
| `config-check` | конфигурацию по профилям | сверяет значения, от которых зависит поведение под отказом: брокер, кеш, пул, обслуживание, остановка, устойчивость |
| `manifest-check` | манифесты развёртывания | сверяет бюджет остановки, паузу перед ней, раздельные пробы, правила обновления, запуск не от суперпользователя |
| `test-lint` | исходники тестов | ловит ожидания, обращения к настоящим часам, контейнеры брокера в подготовке, подмену портов в интеграционных тестах |

Полный перечень проверок каждого скрипта — таблицы каталога. Каждая строка
таблицы называет требование, которое проверка закрывает: **проверка без
требования не заводится**, требование без проверки остаётся с гейтом `ревью`.

Структурные правила этого трека — контракт импортов и запреты зависимостей;
их набор перечислен в полях «Гейт» самих требований. Правила, названные
в каталоге для Java, здесь остаются на ревью — это записано в поле «Не ловит»
соответствующих требований, выдумывать им аналоги не нужно.

Проверка, которую сервис не может пройти сразу, заводится **с файлом
исключений** — по образцу подавлений анализаторов: причина и срок. Отключать
проверку целиком нельзя.
