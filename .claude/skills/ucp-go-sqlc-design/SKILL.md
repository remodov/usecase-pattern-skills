---
name: ucp-go-sqlc-design
lang: go
description: Сгенерировать persistence-слой на sqlc + pgx/v5 из доменного порта по UCP (коды R-SQLC-*) — PostgresXRepository реализует interface из core/, маппер sqlc↔domain, WithTx, *.sql-запросы, golang-migrate, testcontainers-go.
when_to_use: После ucp-go-pattern-design (есть порт-interface). Триггеры — «репозиторий на sqlc для X», «persistence для агрегата Y», «sqlc + pgx-репозиторий».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*) Bash(sqlc*)
---

# Проектирование persistence (Go / net/http + chi)

Ты генерируешь persistence-слой согласно `backend/go/sqlc/sqlc-rules.md` (`R-SQLC-*`). Репозиторий реализует
порт из `core/`, маппит sqlc-строки↔domain, граница транзакции — на Handler через `WithTx(pgx.Tx)`.

## Инструкции

1. **Прочитай** `.claude/docs/backend/go/sqlc/sqlc-rules.md` (`R-SQLC-*`). Связанные: `backend/usecase-pattern/go/...` (порт/слои), `backend/pg-types/pg-types-rules.md` (`PG-T-*` типы), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/pg-runtime-rules.md` (locks/bulk), `backend/error-handling/go/error-handling-style-guide.md` (ошибки-значения).

2. **Вход:** доменный `interface` из `core/<bc>/port/` (от `ucp-go-pattern-design`) + агрегат.

3. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев; коды правил НЕ цитируй):

   ### 3.1 `sqlc.yaml` + `db/queries/*.sql`
   `sqlc.yaml` с `engine: postgresql`, `emit_json_tags: true`, `emit_pointers_for_null_fields: true`, `overrides` для UUID (`github.com/google/uuid.UUID`), numeric (`github.com/shopspring/decimal.Decimal`), timestamptz (`time.Time`) (`R-SQLC-QF-3/4`).
   SQL-запросы в `db/queries/<entity>.sql`, каждый аннотирован `-- name: <Name> :one|:many|:exec|:batchexec` (`R-SQLC-QF-1/2`).

   ### 3.2 `infrastructure/postgres.go` — пул
   `NewPool(cfg Config) (*pgxpool.Pool, error)` через `pgxpool.ParseConfig` + `pgxpool.NewWithConfig`; `MaxConns`, `MinConns`, `MaxConnLifetime`, `HealthCheckPeriod`; DSN из env; `pool.Ping` при старте; `pool.Close()` в shutdown (`R-SQLC-POOL-1/2/3/4/5`).

   ### 3.3 `adapters/out/persistence/<x>_mapper.go` — маппер
   Явные функции `toDomain(row db.<X>) *<x>.<X>` и `toInsertParams(o *<x>.<X>) db.Insert<X>Params`; для nested-fetch — `to<X>WithItems(rows []db.List<X>Row) []*<x>.<X>` (сборка через `map[uuid.UUID]*<X>` + порядковый slice) (`R-SQLC-MAP-1/2/3`). Маппер не содержит бизнес-логики.

   ### 3.4 `adapters/out/persistence/postgres_<x>_repository.go` — репозиторий
   `Postgres<X>Repository` со структурой `{ q *db.Queries; pool *pgxpool.Pool }`; конструктор `NewPostgres<X>Repository(pool *pgxpool.Pool) *Postgres<X>Repository`; `WithTx(tx pgx.Tx) *Postgres<X>Repository`; public-методы принимают/возвращают доменные объекты (`R-SQLC-REPO-1/2/3`). Ошибки: `pgx.ErrNoRows` → доменная `NotFoundError`; `pgconn.PgError` Code `23505` → доменная ошибка конфликта; `23503` → бизнес-правило; все прочие — `fmt.Errorf("...: %w", err)` вверх (`R-SQLC-ERR-1/2/3`).

   ### 3.5 Read-проекции (CQRS)
   `<X>ViewRepository` с методами, возвращающими read-DTO; без полного агрегата; без транзакции или с `pgx.ReadOnly` (`R-SQLC-NEST-4`, `R-SQLC-TX-4`).

   ### 3.6 Bulk-операции (если применимо)
   `pgx.CopyFrom` для >1000 строк; `sqlc batchexec` для умеренного объёма; ошибки batch через `br.Close()` (`R-SQLC-BULK-1/2/3`).

   ### 3.7 Граница транзакции — на Handler
   Handler открывает `pool.Begin(ctx)`, `defer tx.Rollback(ctx)`, передаёт `repo.WithTx(tx)`, явный `tx.Commit(ctx)` после успеха; ошибки commit/rollback логируются через `slog` (`R-SQLC-TX-1/2/3`).

   ### 3.8 Миграции
   `golang-migrate` (или `goose`); папка `db/migrations/`; `migrate.Up()` при старте приложения или в отдельном шаге CI; `sqlc.yaml` ссылается на `db/migrations` (`R-SQLC-MIG-1/2/3/4`). Безопасность по `PG-M-*` (expand-contract, `CREATE INDEX CONCURRENTLY`, `lock_timeout`).

   ### 3.9 Интеграционные тесты
   `adapters/out/persistence/<x>_repository_test.go`; `TestMain` поднимает `testcontainers-go` Postgres один раз, применяет миграции, создаёт `pgxpool.Pool`; каждый тест — в транзакции с `tx.Rollback` в `t.Cleanup`; покрывает happy-path, `ErrNoRows` → `NotFoundError`, constraint-нарушение → доменная ошибка, откат TX (`R-SQLC-TEST-1/2/3/4`).

4. **Граница транзакции — НЕ в репозитории** (`Begin`/`Commit`/`Rollback` запрещены внутри, `R-SQLC-TX-X1`). Маппинг в домен — до возврата из репозитория. Сгенерированный `db/` не редактируется вручную (`R-SQLC-QF-X2`).

5. **Самопроверка** по чеклисту из `backend/go/sqlc/sqlc-rules.md` §«Чеклист подключения». Рекомендуй `errcheck` + `errorlint` в `golangci-lint`. Предложи `ucp-go-sqlc-review`. Для DDL/типов — `ucp-pg-schema-review`.

## Антипаттерны, которые НЕ генерировать

- Возврат сгенерированного `db.<X>` наружу из репозитория (`R-SQLC-REPO-X1`); бизнес-логика в репозитории (`R-SQLC-REPO-X2`); `pgxpool.Pool`/`db.Queries` в `core/` (`R-SQLC-REPO-X3`).
- `Begin`/`Commit`/`Rollback` внутри репозитория (`R-SQLC-TX-X1`); `pgx.Tx` через `context.Value` (`R-SQLC-TX-X2`); `COMMIT` без проверки ошибки (`R-SQLC-TX-X3`).
- SQL-строки с конкатенацией в Go-коде (`R-SQLC-QF-X1`); `sqlc.yaml` без `overrides` для UUID/numeric/timestamptz (`R-SQLC-QF-X3`).
- `return nil, nil` при `pgx.ErrNoRows` (`R-SQLC-ERR-X1`); логирование pgx-ошибок в репозитории + проброс (`R-SQLC-ERR-X2`); `panic(err)` на pgx-ошибке (`R-SQLC-ERR-X3`).
- N+1: цикл `for _, id := range ids { repo.FindByID(...) }` вместо `WHERE id = ANY($1)` (`R-SQLC-NEST-X1`); полный агрегат для read-only проекции (`R-SQLC-NEST-X2`).
- Цикл `exec` per-row для bulk-вставки (`R-SQLC-BULK-X1`); `pgx.Connect` вместо пула (`R-SQLC-POOL-X1`); глобальная `var pool` (`R-SQLC-POOL-X2`).
- Деньги во `float64`; `sql.NullString`/`sql.NullInt64` вместо `pgtype.*` (`R-SQLC-QF-X3`/`PG-T-*`).
- `AutoMigrate` из Go-структур вместо файлов миграций (`R-SQLC-MIG-X2`); mock `pgx.Tx`/`pgxpool.Pool` в тестах (`R-SQLC-TEST-X1`).

После работы скилла — обязательно `ucp-go-sqlc-review`.

$ARGUMENTS
