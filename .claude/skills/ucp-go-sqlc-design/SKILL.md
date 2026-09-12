---
name: ucp-go-sqlc-design
lang: go
description: Сгенерировать persistence-слой на sqlc + pgx/v5 из доменного порта по UCP (требования sqlc/*) — PostgresXRepository реализует interface из core/, маппер sqlc↔domain, WithTx, *.sql-запросы, golang-migrate, testcontainers-go.
when_to_use: После ucp-go-pattern-design (есть порт-interface). Триггеры — «репозиторий на sqlc для X», «persistence для агрегата Y», «sqlc + pgx-репозиторий».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*) Bash(sqlc*)
---

# Проектирование persistence (Go / net/http + chi)

Ты генерируешь persistence-слой согласно `backend/go/sqlc/spec.md` (`R-SQLC-*`). Репозиторий реализует
порт из `core/`, маппит sqlc-строки↔domain, граница транзакции — на Handler через `WithTx(pgx.Tx)`.

## Инструкции

1. **Прочитай** `.claude/docs/backend/go/sqlc/spec.md` (`R-SQLC-*`). Связанные: `backend/usecase-pattern/go/...` (порт/слои), `backend/pg-types/spec.md` (`PG-T-*` типы), `backend/pg-migrations/spec.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/spec.md` (locks/bulk), `backend/error-handling/references/go/implementation.md` (ошибки-значения).

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
   `<X>ViewRepository` с методами, возвращающими read-DTO; без полного агрегата; без транзакции или с `pgx.ReadOnly` (`sqlc/view-repository-for-projections`, `sqlc/reads-are-read-only`).

   ### 3.6 Bulk-операции (если применимо)
   `pgx.CopyFrom` для >1000 строк; `sqlc batchexec` для умеренного объёма; ошибки batch через `br.Close()` (`R-SQLC-BULK-1/2/3`).

   ### 3.7 Граница транзакции — на Handler
   Handler открывает `pool.Begin(ctx)`, `defer tx.Rollback(ctx)`, передаёт `repo.WithTx(tx)`, явный `tx.Commit(ctx)` после успеха; ошибки commit/rollback логируются через `slog` (`R-SQLC-TX-1/2/3`).

   ### 3.8 Миграции
   `golang-migrate` (или `goose`); папка `db/migrations/`; `migrate.Up()` при старте приложения или в отдельном шаге CI; `sqlc.yaml` ссылается на `db/migrations` (`R-SQLC-MIG-1/2/3/4`). Безопасность по `PG-M-*` (expand-contract, `CREATE INDEX CONCURRENTLY`, `lock_timeout`).

   ### 3.9 Интеграционные тесты
   `adapters/out/persistence/<x>_repository_test.go`; `TestMain` поднимает `testcontainers-go` Postgres один раз, применяет миграции, создаёт `pgxpool.Pool`; каждый тест — в транзакции с `tx.Rollback` в `t.Cleanup`; покрывает happy-path, `ErrNoRows` → `NotFoundError`, constraint-нарушение → доменная ошибка, откат TX (`R-SQLC-TEST-1/2/3/4`).

4. **Граница транзакции — НЕ в репозитории** (`Begin`/`Commit`/`Rollback` запрещены внутри, `sqlc/transaction-passed-explicitly`). Маппинг в домен — до возврата из репозитория. Сгенерированный `db/` не редактируется вручную (`sqlc/generated-code-not-edited`).

5. **Самопроверка** по чеклисту из `backend/go/sqlc/spec.md` §«Чеклист подключения». Рекомендуй `errcheck` + `errorlint` в `golangci-lint`. Предложи `ucp-go-sqlc-review`. Для DDL/типов — `ucp-pg-schema-review`.

## Антипаттерны, которые НЕ генерировать

- Возврат сгенерированного `db.<X>` наружу из репозитория (`sqlc/repository-speaks-domain-types`); бизнес-логика в репозитории (`sqlc/no-business-logic-in-repository`); `pgxpool.Pool`/`db.Queries` в `core/` (`sqlc/port-in-core-implementation-in-adapter`).
- `Begin`/`Commit`/`Rollback` внутри репозитория (`sqlc/transaction-passed-explicitly`); `pgx.Tx` через `context.Value` (`sqlc/transaction-passed-explicitly`); `COMMIT` без проверки ошибки (`sqlc/rollback-deferred-commit-checked`).
- SQL-строки с конкатенацией в Go-коде (`sqlc/queries-live-in-files`); `sqlc.yaml` без `overrides` для UUID/numeric/timestamptz (`sqlc/codegen-config-sets-types`).
- `return nil, nil` при `pgx.ErrNoRows` (`sqlc/no-rows-becomes-domain-error`); логирование pgx-ошибок в репозитории + проброс (`sqlc/errors-wrapped-not-logged`); `panic(err)` на pgx-ошибке (`sqlc/errors-wrapped-not-logged`).
- N+1: цикл `for _, id := range ids { repo.FindByID(...) }` вместо `WHERE id = ANY($1)` (`sqlc/no-query-per-row`); полный агрегат для read-only проекции (`sqlc/view-repository-for-projections`).
- Цикл `exec` per-row для bulk-вставки (`sqlc/bulk-insert-not-row-by-row`); `pgx.Connect` вместо пула (`sqlc/pool-is-singleton-and-configured`); глобальная `var pool` (`sqlc/pool-is-singleton-and-configured`).
- Деньги во `float64`; `sql.NullString`/`sql.NullInt64` вместо `pgtype.*` (`sqlc/codegen-config-sets-types`/`PG-T-*`).
- `AutoMigrate` из Go-структур вместо файлов миграций (`sqlc/schema-via-migration-tool`); mock `pgx.Tx`/`pgxpool.Pool` в тестах (`sqlc/repository-tested-against-real-database`).

После работы скилла — обязательно `ucp-go-sqlc-review`.

$ARGUMENTS
