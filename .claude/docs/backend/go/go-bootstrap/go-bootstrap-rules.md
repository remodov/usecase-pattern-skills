# Go Bootstrap — индекс правил (net/http + chi)

> **Что это.** Bootstrap-конфигурация Go-сервиса по UCP: конфигурация через envconfig, конструкторная
> сборка зависимостей, net/http + chi сервер, graceful shutdown, health-эндпоинты. Языко-специфичный
> concern (аналог Java `spring-bootstrap` / `BS-*` и Python `python-bootstrap` / `PYBOOT-*`) — **только Go**,
> пара кодов `GOBOOT-*`. Скиллы читают этот файл; код-примеры включены (отдельного style-guide нет).
> Коды: `GOBOOT-<N>` — обязательно, `GOBOOT-X<N>` — антипаттерн (запрещено).
> Cross-ref: `R-SHUT-*` (graceful-shutdown), `R-ERR-*` (error-handling), `R-OBS-*` (observability).

Базовый принцип (`GOBOOT-1`): **сервис запускается локально одной командой, без живых внешних зависимостей**
(кроме Postgres из docker-compose). Нужен живой Keycloak/Kafka для `go run ./cmd/server` — баг настройки.

## 1. Конфигурация и профили

**MUST:**
- **GOBOOT-2.** Три состояния через `APP_ENV=local|integration-test|production`: production (реальные сервисы), local (Postgres docker-compose, auth off), integration-test (Postgres+стабы внешних сервисов, фоновые задачи off). Конфиг — `envconfig.Process` с тегом `envconfig` на полях структуры.
- **GOBOOT-3.** Профиль не активируется кодом — только через `APP_ENV`. Код, специфичный профилю, гейтится по `cfg.Env`.
- **GOBOOT-4.** Конфиг-структура валидируется на старте (fail-fast): required-поля без `default`, типобезопасно через `envconfig`. Секреты — из env/Vault, не в коде и не в git.

```go
// internal/config/config.go
package config

import "github.com/kelseyhightower/envconfig"

type Config struct {
    Env             string `envconfig:"APP_ENV" required:"true"`
    HTTPAddr        string `envconfig:"HTTP_ADDR" default:":8080"`
    ShutdownTimeout int    `envconfig:"SHUTDOWN_TIMEOUT_SEC" default:"25"`
    DatabaseURL     string `envconfig:"DATABASE_URL" required:"true"`
    JWKSEndpoint    string `envconfig:"JWKS_ENDPOINT"`
}

func Load() (Config, error) {
    var cfg Config
    return cfg, envconfig.Process("", &cfg)
}
```

**MUST NOT:**
- **GOBOOT-X1.** `os.Getenv(...)` россыпью по пакетам вместо единственного `Config`-объекта — нетипизировано, не валидируется на старте.

## 2. Точка входа и сборка зависимостей

**MUST:**
- **GOBOOT-5.** `main.go` — только точка входа: загружает конфиг, собирает граф зависимостей, вызывает `run()`, передаёт код выхода. Вся логика старта — в `run()` или `internal/server`.
- **GOBOOT-6.** Зависимости собираются **конструкторной функцией** (ручная сборка или `google/wire`); нет глобальных синглтонов на уровне пакета. Функция-сборщик возвращает все ресурсы, требующие закрытия.
- **GOBOOT-7.** Источники недетерминизма (время, UUID) — за интерфейсом (`Clock`, `IDGenerator`), production-реализация — в сборщике, тест подменяет (cross-ref `R-HND-5`).

```go
// cmd/server/main.go
func main() {
    if err := run(); err != nil {
        slog.Error("server failed", "error", err)
        os.Exit(1)
    }
}

func run() error {
    cfg, err := config.Load()
    if err != nil {
        return fmt.Errorf("config: %w", err)
    }

    ctx := context.Background()

    poolCfg, err := pgxpool.ParseConfig(cfg.DatabaseURL)
    if err != nil {
        return fmt.Errorf("parse db url: %w", err)
    }
    poolCfg.MaxConns = 20
    poolCfg.MinConns = 2
    pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
    if err != nil {
        return fmt.Errorf("db pool: %w", err)
    }
    defer pool.Close()

    queries := db.New(pool)             // sqlc-сгенерированный слой
    repo    := order.NewRepository(queries)
    handler := order.NewCreateHandler(repo, realclock.New())
    ctrl    := orderhttp.NewController(handler)

    appState := health.NewState()
    r := buildRouter(ctrl, cfg, appState)
    srv := &http.Server{Addr: cfg.HTTPAddr, Handler: r}
    return server.Run(ctx, srv, appState, cfg)
}
```

**MUST NOT:**
- **GOBOOT-X2.** Глобальные переменные с ресурсами на уровне пакета (`var db *pgxpool.Pool` в глобале) — ломает тесты, нарушает видимость жизненного цикла.
- **GOBOOT-X3.** `init()` для инициализации ресурсов — `init` нельзя вернуть ошибку и нельзя контролировать порядок; use `New*(...)` конструкторы.

## 3. Router и middleware

**MUST:**
- **GOBOOT-8.** Router — `github.com/go-chi/chi/v5`. Middleware-стек регистрируется в функции-сборщике роутера: Recoverer, logging, correlation-ID, metrics, tracing, auth (в таком порядке — снаружи вовнутрь).
- **GOBOOT-9.** Correlation-ID — middleware устанавливает `X-Correlation-ID` в `context.Context` и пробрасывает в ответ. Логгер и трейс подхватывают из контекста (cross-ref `R-OBS-*`).
- **GOBOOT-10.** Recoverer-middleware из `chi.Middleware` или собственный — перехватывает panic, логирует с трейсом, возвращает 500 (cross-ref `R-ERR-MAP-5`).

```go
// internal/server/router.go
func buildRouter(ctrl *orderhttp.Controller, cfg config.Config, appState *health.State) http.Handler {
    r := chi.NewRouter()
    r.Use(middleware.Recoverer)
    r.Use(correlationid.Middleware)
    r.Use(httplog.RequestLogger(slog.Default()))
    r.Use(httpmetrics.Middleware)
    r.Use(tracing.Middleware)

    r.Get("/health/live",  health.LiveHandler())
    r.Get("/health/ready", health.ReadyHandler(appState))

    r.Route("/api/v1", func(r chi.Router) {
        if cfg.Env != "local" {
            r.Use(authmw.JWTMiddleware(cfg.JWKSEndpoint))
        }
        r.Post("/orders", ctrl.Create)
    })
    return r
}
```

**MUST NOT:**
- **GOBOOT-X4.** Регистрировать бизнес-роуты до health-эндпоинтов — `/health/*` должны отвечать даже при не полностью инициализированном сервисе.

## 4. Persistence-wiring

**MUST:**
- **GOBOOT-11.** Persistence — `sqlc` + `pgx/v5`; `pgxpool.Pool` — один на весь сервис, создаётся в `run()`, закрывается через `defer pool.Close()`. Миграции — **отдельно от рантайма**: `golang-migrate` или Flyway в CI/деплое, не в `main()`.
- **GOBOOT-12.** Локальный quickstart документирован в README: `docker compose up -d postgres && migrate -path migrations -database $DATABASE_URL up && go run ./cmd/server`.

```go
// pgxpool с разумными дефолтами
poolCfg, err := pgxpool.ParseConfig(cfg.DatabaseURL)
if err != nil {
    return fmt.Errorf("parse db url: %w", err)
}
poolCfg.MaxConns = 20
poolCfg.MinConns = 2
pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
```

**MUST NOT:**
- **GOBOOT-X5.** Выполнять `CREATE TABLE` / DDL в `main()` при старте сервиса — только миграционный инструмент в CI/деплое.
- **GOBOOT-X6.** Открывать новое соединение на каждый запрос вместо пула — `pgxpool` обязателен.

## 5. Graceful shutdown

**MUST:**
- **GOBOOT-13.** Shutdown — `http.Server.Shutdown(ctx)` с явным таймаутом (20–25s); `signal.Notify` на `SIGTERM` + `SIGINT`. Readiness-флаг (`atomic.Bool`) переводится в `false` **до** вызова `Shutdown` (cross-ref `R-SHUT-CFG-1..3`).
- **GOBOOT-14.** Фоновые goroutine (Kafka consumer, scheduler) — завершаются через общий `context.Context` с отменой; ждёт `sync.WaitGroup` до возврата из `run()` (cross-ref `R-SHUT-WORK-*`).

```go
// internal/server/server.go
func Run(ctx context.Context, srv *http.Server, appState *health.State, cfg config.Config) error {
    sigC := make(chan os.Signal, 1)
    signal.Notify(sigC, syscall.SIGTERM, syscall.SIGINT)
    defer signal.Stop(sigC)

    errC := make(chan error, 1)
    go func() { errC <- srv.ListenAndServe() }()

    select {
    case <-sigC:
        slog.InfoContext(ctx, "SIGTERM received, starting graceful shutdown")
    case err := <-errC:
        return fmt.Errorf("server: %w", err)
    }

    appState.SetNotReady() // readiness → 503 первым

    shutCtx, cancel := context.WithTimeout(context.Background(),
        time.Duration(cfg.ShutdownTimeout)*time.Second)
    defer cancel()
    return srv.Shutdown(shutCtx)
}
```

**MUST NOT:**
- **GOBOOT-X7.** `http.Server.Close()` вместо `Shutdown` — Close() рвёт in-flight запросы немедленно.
- **GOBOOT-X8.** `os.Exit(0)` внутри сервисной логики — прерывает `defer`-цепочку и пропускает закрытие ресурсов.

## 6. Health-эндпоинты

**MUST:**
- **GOBOOT-15.** Два раздельных эндпоинта: `/health/live` (процесс жив, всегда 200) и `/health/ready` (зависимости готовы — Postgres ping, флаг `atomic.Bool`). `ready` возвращает 503 при деградации или в фазе shutdown (cross-ref `R-SHUT-CFG-3`).
- **GOBOOT-16.** `/health/ready` проверяет БД через `pool.Ping(ctx)` с таймаутом 2s. Внешние сервисы — не блокируют readiness, если не критичны для запросов.

```go
// internal/health/handler.go
func ReadyHandler(s *State, pool *pgxpool.Pool) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        if !s.IsReady() {
            http.Error(w, "shutting down", http.StatusServiceUnavailable)
            return
        }
        ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
        defer cancel()
        if err := pool.Ping(ctx); err != nil {
            http.Error(w, "db unavailable", http.StatusServiceUnavailable)
            return
        }
        w.WriteHeader(http.StatusOK)
    }
}
```

**MUST NOT:**
- **GOBOOT-X9.** Объединять live и ready в один эндпоинт — k8s использует их по-разному: liveness-перезапуск vs readiness-исключение из балансировки.

## 7. Логирование и observability bootstrap

**MUST:**
- **GOBOOT-17.** Логгер — `log/slog`; JSON-handler в production, Text-handler в local. Инициализируется один раз в `run()`, устанавливается через `slog.SetDefault`. Correlation-ID и trace-ID — в `context.Context`, вытаскиваются из него в обработчиках через `slog.With`.
- **GOBOOT-18.** Метрики — `promauto` из `github.com/prometheus/client_golang`; endpoint `/metrics` — chi-роут `promhttp.Handler()`. Трейсинг — `go.opentelemetry.io/otel`; `TracerProvider` инициализируется в `run()`, закрывается через `defer tp.Shutdown(ctx)`.
- **GOBOOT-19.** PII не попадает в логи (cross-ref `AUTH-16`). Ошибки логируются **один раз** — в edge error-renderer (cross-ref `R-ERR-LOG-4`).

```go
// cmd/server/main.go — инициализация логгера
func initLogger(env string) {
    var h slog.Handler
    if env == "production" {
        h = slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})
    } else {
        h = slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug})
    }
    slog.SetDefault(slog.New(h))
}
```

**MUST NOT:**
- **GOBOOT-X10.** `log.Printf(...)` (стандартный `log`) вместо `slog` — нет структуры и уровней.
- **GOBOOT-X11.** Инициализировать несколько `TracerProvider` — один на процесс, создаётся в `run()`.

## 8. Структура пакетов

**MUST:**
- **GOBOOT-20.** Раскладка: `cmd/<name>/` (main + run), `internal/` (весь код сервиса), `internal/config/`, `internal/server/`, `internal/health/`, `internal/<domain>/` (домен + usecases + порты), `internal/<domain>/http/` (http-адаптер), `internal/<domain>/postgres/` (persistence-адаптер), `db/` (sqlc-сгенерированный код). Публичные пакеты (`pkg/`) — только для реально переиспользуемого кода между сервисами.
- **GOBOOT-21.** Доменный код (`internal/<domain>/`) не импортирует `net/http`, `pgx`, `chi` — только интерфейсы портов. Зависимости направлены внутрь (cross-ref `R-HEX-2`).
- **GOBOOT-22.** Линтер — `golangci-lint` с `errcheck`, `errorlint`, `govet`, `staticcheck` в CI. `gofmt` обязателен перед коммитом.

**MUST NOT:**
- **GOBOOT-X12.** Импорт `internal/<domain>/http` или `internal/<domain>/postgres` из `internal/<domain>/` (домен) — инверсия зависимостей нарушена.
- **GOBOOT-X13.** Общий пакет `utils/` или `helpers/` — концептуально пустое имя; вместо него — `internal/timeutil/`, `internal/idgen/` с конкретными ответственностями.

## Quickstart-чеклист (сервис не стартует)

1. `APP_ENV` выставлен? (`local` для разработки)
2. `envconfig.Process` не упал — нет ли missing required env?
3. Postgres поднят (`docker compose up -d postgres`) и миграции накатаны (`migrate ... up`)?
4. Ресурсы создаются в `run()`, не в `init()` / глобальных переменных (`GOBOOT-X2`, `GOBOOT-X3`)?
5. На local `cfg.Env == "local"` — JWT-middleware не подключается, auth off?
6. `/health/ready` — возвращает 200? (`pool.Ping` проходит?)
7. `golangci-lint run` — `errcheck`/`errorlint` не ругается?
