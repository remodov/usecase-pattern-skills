# sqlc — индекс правил (Go persistence)

> **Что это.** Persistence-слой на sqlc codegen + pgx/v5 по UCP. Языко-специфичный concern (аналог
> Python `R-SQLA-*`) — **только Go**, префикс `R-SQLC-*`. Скиллы читают этот файл; код-примерами включены.
> Коды: `R-SQLC-<N>` — обязательно (MUST), `R-SQLC-X<N>` — антипаттерн (MUST NOT).
> PostgreSQL-правила (типы/индексы/миграции/runtime) — язык-нейтральны, см. `pg-*-rules.md`.
> Ошибки — значения (`apperr.Kind` + `errors.As` + `%w`), как в `error-handling/go/error-handling-style-guide.md`.

Суть: репозиторий реализует **порт из `core/`**, принимает/возвращает **доменные объекты** (не сгенерированные sqlc-модели); sqlc-тип — деталь persistence; граница транзакции — на Handler; `pgxpool.Pool` — singleton, `pgx.Tx` передаётся явно.

---

## 1. Repository-pattern

**MUST:**
- **R-SQLC-REPO-1.** Доменный порт — `interface` в `core/<bc>/port/`; реализация — `Postgres<X>Repository` в `adapters/out/persistence/`.
- **R-SQLC-REPO-2.** Public-методы принимают/возвращают **доменные объекты** (Aggregate/VO/read-DTO), не сгенерированные sqlc-строки/модели и не `pgx.Row`.
- **R-SQLC-REPO-3.** `*db.Queries` (или `pgxpool.Pool`) инжектируется конструктором — не создаётся внутри репозитория.
- **R-SQLC-REPO-4.** Каждый репозиторий покрыт интеграционным тестом против Testcontainers Postgres; mock `pgx` запрещён (cross-ref `R-SQLC-TEST-1`).

```go
// core/order/port/order_repository.go
type OrderRepository interface {
    Save(ctx context.Context, o *Order) error
    FindByID(ctx context.Context, id uuid.UUID) (*Order, error)
}

// adapters/out/persistence/postgres_order_repository.go
type PostgresOrderRepository struct {
    q  *db.Queries
    pool *pgxpool.Pool
}

func NewPostgresOrderRepository(pool *pgxpool.Pool) *PostgresOrderRepository {
    return &PostgresOrderRepository{q: db.New(pool), pool: pool}
}
```

**MUST NOT:**
- **R-SQLC-REPO-X1.** Возврат сгенерированного sqlc-типа (`db.Order`) наружу из репозитория.
- **R-SQLC-REPO-X2.** Бизнес-логика в репозитории (`if order.Status == ...`) — только CRUD.
- **R-SQLC-REPO-X3.** Прямое использование `pgxpool.Pool`/`db.Queries` в `core/` (домене или хендлере) — только через порт.

---

## 2. sqlc codegen и query-файлы

**MUST:**
- **R-SQLC-QF-1.** SQL-запросы — в `*.sql`-файлах под `db/queries/` (или рядом с репозиторием); не строки в Go-коде.
- **R-SQLC-QF-2.** Каждый запрос аннотирован: `-- name: <Name> :one|:many|:exec|:execrows|:batchexec`; имя отражает действие (`GetOrderByID`, `ListActiveOrders`, `InsertOrder`).
- **R-SQLC-QF-3.** `sqlc.yaml` задаёт: `engine: postgresql`, `emit_json_tags: true`, `emit_pointers_for_null_fields: true` (для nullable-колонок), `overrides` для кастомных Go-типов (UUID, деньги, время).
- **R-SQLC-QF-4.** Nullable-поля — через `pgtype.*` (pgx/v5) или кастомный тип из `overrides`; не `sql.NullString` / `sql.NullInt64` (cross-ref `PG-T-*`).
- **R-SQLC-QF-5.** Сгенерированный код (`db/`) — в `.gitignore` либо коммитится вместе с `*.sql`-изменением (выбрать одно, зафиксировать в `sqlc.yaml`).

```yaml
# sqlc.yaml
version: "2"
sql:
  - engine: "postgresql"
    queries: "db/queries"
    schema: "db/migrations"
    gen:
      go:
        package: "db"
        out: "db"
        emit_json_tags: true
        emit_pointers_for_null_fields: true
        overrides:
          - db_type: "uuid"
            go_type: "github.com/google/uuid.UUID"
          - db_type: "pg_catalog.numeric"
            go_type: "github.com/shopspring/decimal.Decimal"
          - db_type: "timestamptz"
            go_type: "time.Time"
```

```sql
-- db/queries/orders.sql

-- name: GetOrderByID :one
SELECT id, customer_id, amount, status, created_at
FROM orders
WHERE id = $1;

-- name: InsertOrder :exec
INSERT INTO orders (id, customer_id, amount, status, created_at)
VALUES ($1, $2, $3, $4, $5);

-- name: ListOrdersByCustomer :many
SELECT id, customer_id, amount, status, created_at
FROM orders
WHERE customer_id = $1
ORDER BY created_at DESC
LIMIT $2 OFFSET $3;
```

**MUST NOT:**
- **R-SQLC-QF-X1.** SQL в Go-строках с конкатенацией (`"SELECT ... WHERE id = " + id`) — SQL-инъекция; параметры только через `$1`/`$2` в `*.sql`.
- **R-SQLC-QF-X2.** Модификация сгенерированных файлов `db/*.go` вручную — перезаписываются `sqlc generate`.
- **R-SQLC-QF-X3.** `sqlc.yaml` без `overrides` для UUID/numeric/timestamptz — типы деградируют до `string`/`float64`/`time.Time` без timezone-aware гарантий.

---

## 3. Маппинг sqlc ↔ domain

**MUST:**
- **R-SQLC-MAP-1.** Явные функции-маппера `toDomain(row db.Order) *order.Order` и `toInsertParams(o *order.Order) db.InsertOrderParams`, расположенные рядом с репозиторием (не внутри него).
- **R-SQLC-MAP-2.** Сборка агрегата из нескольких sqlc-строк (nested-fetch) — в маппере, не размазана по репозиторию.
- **R-SQLC-MAP-3.** Маппер не содержит бизнес-логики — только структурная конвертация полей.

```go
// adapters/out/persistence/order_mapper.go
package persistence

func toDomain(row db.GetOrderByIDRow) *order.Order {
    return &order.Order{
        ID:         row.ID,
        CustomerID: row.CustomerID,
        Amount:     row.Amount,
        Status:     order.Status(row.Status),
        CreatedAt:  row.CreatedAt,
    }
}

func toInsertParams(o *order.Order) db.InsertOrderParams {
    return db.InsertOrderParams{
        ID:         o.ID,
        CustomerID: o.CustomerID,
        Amount:     o.Amount,
        Status:     string(o.Status),
        CreatedAt:  o.CreatedAt,
    }
}
```

**MUST NOT:**
- **R-SQLC-MAP-X1.** Использование `reflect`/`json.Marshal`-`Unmarshal` для маппинга sqlc → domain — нет безопасности типов.
- **R-SQLC-MAP-X2.** Прямой возврат sqlc-строки из репозитория «для экономии» — sqlc-тип протекает в домен.

---

## 4. Транзакции

**MUST:**
- **R-SQLC-TX-1.** Граница транзакции — на Handler; репозиторий принимает транзакционный контекст через `pgx.Tx` (или `*db.Queries` созданный из `tx`) — не открывает `Begin` самостоятельно.
- **R-SQLC-TX-2.** `WithTx(tx pgx.Tx) *db.Queries` (сгенерированный sqlc) используется для передачи транзакции в `Queries`; репозиторий предоставляет метод `WithTx(tx pgx.Tx) <Repository>`.
- **R-SQLC-TX-3.** Откат — через `defer tx.Rollback(ctx)`; commit — явный `tx.Commit(ctx)` после успеха; ошибки коммита и ролбэка логируются (cross-ref `R-ERR-WHERE-1`).
- **R-SQLC-TX-4.** Read-only запросы (CQRS-запрос) — без транзакции или с `pgx.TxOptions{AccessMode: pgx.ReadOnly}`.

```go
// adapters/out/persistence/postgres_order_repository.go
func (r *PostgresOrderRepository) WithTx(tx pgx.Tx) *PostgresOrderRepository {
    return &PostgresOrderRepository{q: r.q.WithTx(tx), pool: r.pool}
}

// core/order/handler/place_order_handler.go
func (h *PlaceOrderHandler) Handle(ctx context.Context, cmd PlaceOrderCommand) error {
    tx, err := h.pool.Begin(ctx)
    if err != nil {
        return fmt.Errorf("begin tx: %w", err)
    }
    defer tx.Rollback(ctx) // no-op if committed

    repo := h.repo.WithTx(tx)
    if err := repo.Save(ctx, cmd.toOrder()); err != nil {
        return fmt.Errorf("save order: %w", err)
    }
    return tx.Commit(ctx)
}
```

**MUST NOT:**
- **R-SQLC-TX-X1.** `Begin`/`Commit`/`Rollback` внутри репозитория — граница TX на Handler.
- **R-SQLC-TX-X2.** Передача `pgx.Tx` через `context.Value` («скрытая TX») — передавать явно через `WithTx`.
- **R-SQLC-TX-X3.** `COMMIT` без проверки ошибки — ошибка коммита молча теряется, данные не сохранены.

---

## 5. pgxpool и соединение

**MUST:**
- **R-SQLC-POOL-1.** `pgxpool.Pool` — singleton, создаётся при старте приложения и инжектируется через конструктор; не создаётся per-request.
- **R-SQLC-POOL-2.** `pgxpool.ParseConfig` + `pgxpool.NewWithConfig` для настройки пула (MinConns, MaxConns, MaxConnLifetime, HealthCheckPeriod); не хардкод-строка DSN напрямую в `pgxpool.New`.
- **R-SQLC-POOL-3.** DSN читается из env через `envconfig`/`os.Getenv`; не хардкодится в коде.
- **R-SQLC-POOL-4.** `pool.Ping(ctx)` при старте — fail-fast если БД недоступна.
- **R-SQLC-POOL-5.** `pool.Close()` в `defer` или `gracefulShutdown` — освобождение соединений при остановке.

```go
// infrastructure/postgres.go
func NewPool(cfg Config) (*pgxpool.Pool, error) {
    poolCfg, err := pgxpool.ParseConfig(cfg.DSN)
    if err != nil {
        return nil, fmt.Errorf("parse pool config: %w", err)
    }
    poolCfg.MaxConns = int32(cfg.MaxConns)
    poolCfg.MinConns = int32(cfg.MinConns)
    poolCfg.MaxConnLifetime = cfg.MaxConnLifetime
    poolCfg.HealthCheckPeriod = 30 * time.Second

    pool, err := pgxpool.NewWithConfig(context.Background(), poolCfg)
    if err != nil {
        return nil, fmt.Errorf("create pool: %w", err)
    }
    if err := pool.Ping(context.Background()); err != nil {
        return nil, fmt.Errorf("ping db: %w", err)
    }
    return pool, nil
}
```

**MUST NOT:**
- **R-SQLC-POOL-X1.** `pgx.Connect` (одиночное соединение) в production-коде — нет пула, нет reconnect.
- **R-SQLC-POOL-X2.** Глобальная переменная `var pool *pgxpool.Pool` — инжекция через конструктор.
- **R-SQLC-POOL-X3.** Игнорирование `pool.Ping` при старте — приложение поднимается без БД и падает на первом запросе.

---

## 6. Ошибки и pgx

**MUST:**
- **R-SQLC-ERR-1.** `pgx.ErrNoRows` → доменная `NotFoundError` с контекстом (`EntityType`, `ID`); не возврат `nil, nil` (cross-ref `R-ERR-WHERE-X3`).
- **R-SQLC-ERR-2.** Ошибки нарушения ограничений (`pgconn.PgError`, `Code`): `23505` (unique) → доменная ошибка конфликта; `23503` (fk) → доменная ошибка бизнес-правила; остальные — технические (cross-ref `R-ERR-HIER-1`).
- **R-SQLC-ERR-3.** Все pgx-ошибки оборачиваются с контекстом (`fmt.Errorf("find order %s: %w", id, err)`) и всплывают вверх — не логируются в репозитории (cross-ref `R-ERR-LOG-4`).
- **R-SQLC-ERR-4.** Таймаут запроса через `context.WithTimeout` на хендлере или middleware — не через pgx-параметры напрямую в репозитории.

```go
// adapters/out/persistence/postgres_order_repository.go
func (r *PostgresOrderRepository) FindByID(ctx context.Context, id uuid.UUID) (*order.Order, error) {
    row, err := r.q.GetOrderByID(ctx, id)
    if err != nil {
        if errors.Is(err, pgx.ErrNoRows) {
            return nil, &order.NotFoundError{ID: id}
        }
        return nil, fmt.Errorf("find order %s: %w", id, err)
    }
    return toDomain(row), nil
}

func (r *PostgresOrderRepository) Save(ctx context.Context, o *order.Order) error {
    err := r.q.InsertOrder(ctx, toInsertParams(o))
    if err != nil {
        var pgErr *pgconn.PgError
        if errors.As(err, &pgErr) && pgErr.Code == "23505" {
            return &order.AlreadyExistsError{ID: o.ID}
        }
        return fmt.Errorf("save order %s: %w", o.ID, err)
    }
    return nil
}
```

**MUST NOT:**
- **R-SQLC-ERR-X1.** `return nil, nil` при `pgx.ErrNoRows` — вызывающий получает nil-агрегат без сигнала об ошибке.
- **R-SQLC-ERR-X2.** Логирование pgx-ошибок в репозитории + проброс вверх — двойное логирование (cross-ref `R-ERR-LOG-X1`).
- **R-SQLC-ERR-X3.** Прямой `panic(err)` на pgx-ошибке — ошибки persistence — значения, не панические (cross-ref `R-ERR-RESULT-1`).

---

## 7. Nested-fetch и связанные агрегаты

**MUST:**
- **R-SQLC-NEST-1.** Загрузка агрегата с вложенными сущностями — `sqlc.many` (`:many` + сборка в маппере) или `batchexec`; не N+1 запросов в цикле репозитория.
- **R-SQLC-NEST-2.** Сборка вложенных коллекций из flat-результата — в маппере через `map[uuid.UUID]*Order` и цикл; не несколько отдельных вызовов репозитория из хендлера без необходимости.
- **R-SQLC-NEST-3.** JOIN с агрегацией (`array_agg`, `json_agg`) — допустим для простых вложений; для сложных агрегатов — два запроса + сборка в репозитории (в рамках одной TX).
- **R-SQLC-NEST-4.** Read-проекции (CQRS-запрос) — отдельный `<X>ViewRepository`, возвращает read-DTO; не полный агрегат (cross-ref `R-CQRS-4`).

```go
// db/queries/orders.sql

-- name: ListOrdersWithItems :many
SELECT
    o.id          AS order_id,
    o.customer_id,
    o.status,
    oi.id         AS item_id,
    oi.product_id,
    oi.quantity,
    oi.price
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
WHERE o.customer_id = $1
ORDER BY o.created_at DESC;
```

```go
// adapters/out/persistence/order_mapper.go
func toOrdersWithItems(rows []db.ListOrdersWithItemsRow) []*order.Order {
    index := make(map[uuid.UUID]*order.Order)
    var ordered []uuid.UUID

    for _, row := range rows {
        if _, ok := index[row.OrderID]; !ok {
            index[row.OrderID] = &order.Order{
                ID:         row.OrderID,
                CustomerID: row.CustomerID,
                Status:     order.Status(row.Status),
            }
            ordered = append(ordered, row.OrderID)
        }
        index[row.OrderID].Items = append(index[row.OrderID].Items, order.Item{
            ID:        row.ItemID,
            ProductID: row.ProductID,
            Quantity:  int(row.Quantity),
            Price:     row.Price,
        })
    }

    result := make([]*order.Order, 0, len(ordered))
    for _, id := range ordered {
        result = append(result, index[id])
    }
    return result
}
```

**MUST NOT:**
- **R-SQLC-NEST-X1.** N+1: цикл `for _, id := range orderIDs { repo.FindByID(ctx, id) }` — один запрос с `WHERE id = ANY($1)`.
- **R-SQLC-NEST-X2.** Загрузка полного агрегата для read-only проекции — возвращать DTO напрямую из SQL.

---

## 8. Bulk-операции

**MUST:**
- **R-SQLC-BULK-1.** Bulk-вставка — `COPY` (`pgx.CopyFrom`) для больших объёмов (>500 строк) или `INSERT ... VALUES ($1,$2), ($3,$4)` с `sqlc batchexec` для умеренных объёмов; не цикл `exec` per-row.
- **R-SQLC-BULK-2.** `pgx.CopyFrom` предпочтителен для >1000 строк: не парсирует SQL per-row, скорость в 5–10× vs single insert (cross-ref `PG-W-010`).
- **R-SQLC-BULK-3.** Batch-запросы `db.Queries.Batch*` (sqlc batchexec) — для умеренного объёма; ошибки из batch читаются через `br.Close()`.

```go
// adapters/out/persistence/postgres_order_repository.go
func (r *PostgresOrderRepository) BulkInsertItems(ctx context.Context, items []order.Item) error {
    rows := make([][]any, len(items))
    for i, item := range items {
        rows[i] = []any{item.ID, item.OrderID, item.ProductID, item.Quantity, item.Price}
    }
    _, err := r.pool.CopyFrom(
        ctx,
        pgx.Identifier{"order_items"},
        []string{"id", "order_id", "product_id", "quantity", "price"},
        pgx.CopyFromRows(rows),
    )
    if err != nil {
        return fmt.Errorf("bulk insert items: %w", err)
    }
    return nil
}
```

**MUST NOT:**
- **R-SQLC-BULK-X1.** `for _, item := range items { q.InsertOrderItem(ctx, ...) }` — N round-trips для N строк.
- **R-SQLC-BULK-X2.** Одна большая `VALUES`-строка, конкатенированная в Go-коде — SQL-инъекция + нет параметризации.

---

## 9. Миграции

**MUST:**
- **R-SQLC-MIG-1.** Схема — через **golang-migrate** (`migrate -path db/migrations -database $DSN up`) или **goose**; не `pgxpool.Exec` с `CREATE TABLE` в application-коде.
- **R-SQLC-MIG-2.** `sqlc.yaml` указывает на папку миграций (`schema: "db/migrations"`); `sqlc generate` перечитывает схему из файлов миграций — не из live-БД.
- **R-SQLC-MIG-3.** Безопасность миграций (expand-contract, `CREATE INDEX CONCURRENTLY`, `lock_timeout`) — по `pg-migrations-rules.md` (`PG-M-*`).
- **R-SQLC-MIG-4.** Миграция применяется при старте (`migrate.Up()`) или отдельным шагом CI — не вручную.

**MUST NOT:**
- **R-SQLC-MIG-X1.** Изменение уже применённой миграции — добавлять новую.
- **R-SQLC-MIG-X2.** `AutoMigrate`-паттерн (создание таблиц из Go-структур) — нет версионирования, нет rollback.

---

## 10. Тестирование

**MUST:**
- **R-SQLC-TEST-1.** Интеграционные тесты репозитория — против реального Postgres через `testcontainers-go`; не mock `pgx.Tx`/`pgxpool.Pool`.
- **R-SQLC-TEST-2.** Каждый тест запускает миграции на чистой БД (`migrate.Up()` в `TestMain` или per-test schema); данные изолированы транзакцией с `tx.Rollback` в `t.Cleanup`.
- **R-SQLC-TEST-3.** Тест покрывает: happy-path, `ErrNoRows` → `NotFoundError`, constraint-нарушение → доменная ошибка, транзакционный откат при ошибке.
- **R-SQLC-TEST-4.** `TestMain` инициализирует контейнер один раз (`suite`-уровень); не per-test поднятие контейнера.

```go
// adapters/out/persistence/postgres_order_repository_test.go
func TestMain(m *testing.M) {
    ctx := context.Background()
    container, err := postgres.Run(ctx, "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        testcontainers.WithWaitStrategy(wait.ForListeningPort("5432/tcp")),
    )
    if err != nil {
        log.Fatalf("start container: %v", err)
    }
    dsn, _ := container.ConnectionString(ctx, "sslmode=disable")
    testPool, _ = pgxpool.New(ctx, dsn)
    runMigrations(dsn)

    code := m.Run()
    container.Terminate(ctx)
    os.Exit(code)
}

func TestPostgresOrderRepository_FindByID_NotFound(t *testing.T) {
    ctx := context.Background()
    tx, _ := testPool.Begin(ctx)
    t.Cleanup(func() { tx.Rollback(ctx) })

    repo := NewPostgresOrderRepository(testPool).WithTx(tx)
    _, err := repo.FindByID(ctx, uuid.New())

    var notFound *order.NotFoundError
    require.ErrorAs(t, err, &notFound)
}
```

**MUST NOT:**
- **R-SQLC-TEST-X1.** Mock-реализации `pgxpool.Pool`/`pgx.Tx` — не тестируют реальный SQL.
- **R-SQLC-TEST-X2.** Тесты без изоляции (shared state между тестами через общую БД без rollback).
- **R-SQLC-TEST-X3.** Тест только happy-path без проверки ошибок persistence.

---

## Чеклист подключения к новому сервису (Go / sqlc + pgx)

- [ ] `pgxpool.Pool` — singleton, настроен через `pgxpool.ParseConfig` + env (`envconfig`), `Ping` при старте
- [ ] `sqlc.yaml` с `engine: postgresql`, `overrides` для UUID/numeric/timestamptz
- [ ] `*.sql`-файлы в `db/queries/`, аннотированы `-- name: ... :one|:many|:exec`
- [ ] Сгенерированный `db/` — статус (в gitignore или коммитится) зафиксирован в `sqlc.yaml` и CI
- [ ] Доменный `interface` в `core/<bc>/port/`; `Postgres<X>Repository` в `adapters/out/persistence/`
- [ ] Маппер `toDomain`/`toInsertParams` рядом с репозиторием; sqlc-тип не вытекает наружу
- [ ] Транзакция — на Handler; репозиторий предоставляет `WithTx(pgx.Tx)`
- [ ] `pgx.ErrNoRows` → доменная `NotFoundError`; `23505`/`23503` → доменные ошибки; остальные — техническая обёртка с `%w`
- [ ] Bulk-вставка — `pgx.CopyFrom` (>1000 строк) или `sqlc batchexec` (умеренный объём)
- [ ] Nested-fetch — JOIN + сборка в маппере через `map`; не N+1
- [ ] Read-проекции (CQRS) — отдельный `<X>ViewRepository`, возвращает DTO
- [ ] Миграции — `golang-migrate` или `goose`; `migrate.Up()` при старте/CI
- [ ] Интеграционные тесты через `testcontainers-go`; изоляция через `tx.Rollback` в `t.Cleanup`
- [ ] `errcheck` / `errorlint` в линтере — ловят непроверенные ошибки pgx
