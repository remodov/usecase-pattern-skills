---
name: ucp-go-sqlc-review
lang: go
description: Ревью persistence-слоя Go-сервиса по UCP (требования sqlc/*) — порт/маппер sqlc↔domain, TX на Handler через WithTx(pgx.Tx), pgxpool singleton, ErrNoRows→NotFoundError, ViewRepository, testcontainers-go.
when_to_use: Изменения в adapters/out/persistence (postgres_*_repository.go, *_mapper.go, *_view_repository.go), db/queries/*.sql, sqlc.yaml или db/migrations.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью persistence (Go / sqlc + pgx)

Ты ревьюишь persistence-слой Go-сервиса на соответствие `backend/go/sqlc/spec.md` (`R-SQLC-*`).
Репозиторий реализует порт из `core/`, маппит sqlc-строки↔domain, граница транзакции — на Handler через
`WithTx(pgx.Tx)`. Статические нарушения (SQL-инъекция в строках, необработанные ошибки) ловит CI (`errcheck`,
`errorlint`, `golangci-lint`); здесь — семантика и архитектурные инварианты.

## Зависимости

- **`.claude/docs/backend/go/sqlc/spec.md`** — правила `R-SQLC-*` (с код-примерами).
- Парные: `backend/usecase-pattern/go/...` (порт/слои, `R-LAY-*`/`R-HEX-*`/`R-TX-*`), `backend/error-handling/references/go/implementation.md` (`R-ERR-HIER-*`/`R-ERR-WHERE-*`), `backend/pg-types/spec.md` (`PG-T-*` типы), `backend/pg-migrations/spec.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/spec.md` (`PG-W-*` locks/bulk), `backend/cqrs/spec.md` (`usecase-pattern/reads-via-read-model` read-проекции).

## Инструкции

1. **Прочти** `sqlc/spec.md`. Цитируй конкретные коды (`sqlc/repository-speaks-domain-types`), не только префикс.

2. **Скоп.** `adapters/out/persistence/**` (`postgres_*_repository.go`, `*_mapper.go`, `*_view_repository.go`), `db/queries/*.sql`, `sqlc.yaml`, `db/migrations/**`, порт-`interface` в `core/<bc>/port/`, `git diff` на `.go` и `.sql`.

3. **Прогон.**

   ### Repository-pattern (`R-SQLC-REPO-*`)
   - Доменный порт — `interface` в `core/<bc>/port/`; реализация — `Postgres<X>Repository` в `adapters/out/persistence/`? — `sqlc/port-in-core-implementation-in-adapter`.
   - Public-методы принимают/возвращают доменные объекты (Aggregate/VO/read-DTO), не сгенерированные sqlc-строки и не `pgx.Row`? — `sqlc/repository-speaks-domain-types`.
   - `*db.Queries` / `pgxpool.Pool` инжектируется конструктором, не создаётся внутри? — `sqlc/dependencies-via-constructor`.
   - Покрыт интеграционным тестом против `testcontainers-go`? — `sqlc/repository-tested-against-real-database`.
   - Возврат `db.<X>` (sqlc-тип) наружу → `sqlc/repository-speaks-domain-types`.
   - Бизнес-логика в репозитории (`if order.Status == ...`) → `sqlc/no-business-logic-in-repository`.
   - `pgxpool.Pool`/`db.Queries` напрямую в `core/` (Handler/Service/Aggregate) → `sqlc/port-in-core-implementation-in-adapter` (cross-ref `hexagonal/outbound-port-interface-in-core`).

   ### sqlc codegen и query-файлы (`R-SQLC-QF-*`)
   - SQL — в `*.sql`-файлах под `db/queries/`; не строки в Go-коде? — `sqlc/queries-live-in-files`.
   - Каждый запрос аннотирован `-- name: <Name> :one|:many|:exec|:execrows|:batchexec`? — `sqlc/queries-live-in-files`.
   - `sqlc.yaml`: `engine: postgresql`, `emit_json_tags`, `emit_pointers_for_null_fields`, `overrides` для UUID/numeric/timestamptz? — `sqlc/codegen-config-sets-types`.
   - Nullable-поля через `pgtype.*` (pgx/v5) или кастомный тип из `overrides`; не `sql.NullString`/`sql.NullInt64`? — `sqlc/codegen-config-sets-types`.
   - Статус сгенерированного `db/` (`.gitignore` или коммитится с `*.sql`) зафиксирован в `sqlc.yaml` и CI? — `sqlc/generated-code-not-edited`.
   - SQL с конкатенацией строк в Go (`"SELECT ... WHERE id = " + id`) → `sqlc/queries-live-in-files`.
   - Ручная правка файлов `db/*.go` → `sqlc/generated-code-not-edited`.
   - `sqlc.yaml` без `overrides` для UUID/numeric/timestamptz → `sqlc/codegen-config-sets-types`.

   ### Маппинг sqlc ↔ domain (`R-SQLC-MAP-*`)
   - Явные функции-маппера `toDomain(row db.X) *domain.X` и `toInsertParams(o *domain.X) db.XParams`, расположенные рядом с репозиторием (не внутри него)? — `sqlc/explicit-mapping`.
   - Сборка агрегата из нескольких sqlc-строк (nested-fetch) — в маппере, не размазана по репозиторию? — `sqlc/explicit-mapping`.
   - Маппер без бизнес-логики — только структурная конвертация? — `sqlc/explicit-mapping`.
   - `reflect`/`json.Marshal`+`json.Unmarshal` для маппинга sqlc→domain → `sqlc/explicit-mapping`.
   - Прямой возврат sqlc-строки из репозитория «для экономии» → `sqlc/repository-speaks-domain-types`.

   ### Транзакции (`R-SQLC-TX-*`)
   - Граница транзакции на Handler; репозиторий получает `pgx.Tx` через `WithTx(pgx.Tx)`, не открывает `Begin` самостоятельно? — `R-SQLC-TX-1/2`.
   - `defer tx.Rollback(ctx)` + явный `tx.Commit(ctx)` с проверкой ошибки? — `sqlc/rollback-deferred-commit-checked`.
   - Read-only запросы без транзакции или с `pgx.TxOptions{AccessMode: pgx.ReadOnly}`? — `sqlc/reads-are-read-only`.
   - `Begin`/`Commit`/`Rollback` внутри репозитория → `sqlc/transaction-passed-explicitly`.
   - `pgx.Tx` через `context.Value` («скрытая TX») → `sqlc/transaction-passed-explicitly` (передавать явно через `WithTx`).
   - `tx.Commit(ctx)` без проверки ошибки → `sqlc/rollback-deferred-commit-checked`.

   ### pgxpool и соединение (`R-SQLC-POOL-*`)
   - `pgxpool.Pool` — singleton, инжектируется конструктором; не создаётся per-request? — `sqlc/pool-is-singleton-and-configured`.
   - `pgxpool.ParseConfig` + `pgxpool.NewWithConfig` с настройкой MinConns/MaxConns/MaxConnLifetime/HealthCheckPeriod? — `sqlc/pool-is-singleton-and-configured`.
   - DSN из env (`envconfig`/`os.Getenv`); не хардкодится? — `sqlc/dsn-from-environment`.
   - `pool.Ping(ctx)` при старте — fail-fast если БД недоступна? — `sqlc/ping-on-start-close-on-stop`.
   - `pool.Close()` в `defer` или graceful-shutdown? — `sqlc/ping-on-start-close-on-stop`.
   - `pgx.Connect` (одиночное соединение) в production-коде → `sqlc/pool-is-singleton-and-configured`.
   - `var pool *pgxpool.Pool` глобально → `sqlc/pool-is-singleton-and-configured`.
   - Пропущен `pool.Ping` при старте → `sqlc/ping-on-start-close-on-stop`.

   ### Ошибки и pgx (`R-SQLC-ERR-*`)
   - `pgx.ErrNoRows` → доменная `NotFoundError` с контекстом (`EntityType`, `ID`); не `nil, nil`? — `sqlc/no-rows-becomes-domain-error` (cross-ref `error-handling/catch-does-not-swallow`).
   - `pgconn.PgError` с `Code`: `23505` (unique) → ошибка конфликта; `23503` (fk) → доменная; остальные — техническая обёртка? — `sqlc/constraint-violations-become-domain-errors` (cross-ref `error-handling/four-exception-kinds`).
   - pgx-ошибки оборачиваются `fmt.Errorf("find order %s: %w", id, err)` и всплывают вверх; не логируются в репозитории? — `sqlc/errors-wrapped-not-logged` (cross-ref `error-handling/log-once-with-exception`).
   - Таймаут через `context.WithTimeout` на хендлере или middleware; не внутри репозитория? — `sqlc/timeout-comes-from-context`.
   - `return nil, nil` при `pgx.ErrNoRows` → `sqlc/no-rows-becomes-domain-error`.
   - Логирование pgx-ошибки в репозитории + проброс вверх (двойное логирование) → `sqlc/errors-wrapped-not-logged`.
   - `panic(err)` на pgx-ошибке → `sqlc/errors-wrapped-not-logged` (cross-ref `error-handling/result-type-is-local-choice`).

   ### Nested-fetch и связанные агрегаты (`R-SQLC-NEST-*`)
   - Загрузка агрегата с вложенными сущностями — `:many` JOIN + сборка в маппере через `map[uuid.UUID]*X`? — `R-SQLC-NEST-1/2`.
   - `JOIN` с `array_agg`/`json_agg` допустим для простых вложений; сложные — два запроса в рамках одной TX? — `sqlc/no-query-per-row`.
   - Read-проекции (CQRS) — отдельный `<X>ViewRepository`, возвращает read-DTO, не полный агрегат? — `sqlc/view-repository-for-projections` (cross-ref `usecase-pattern/reads-via-read-model`).
   - N+1: `for _, id := range ids { repo.FindByID(ctx, id) }` → `sqlc/no-query-per-row` (заменить на `WHERE id = ANY($1)`).
   - Загрузка полного агрегата для read-only проекции → `sqlc/view-repository-for-projections`.

   ### Bulk-операции (`R-SQLC-BULK-*`)
   - Bulk-вставка >1000 строк — `pgx.CopyFrom`; умеренный объём — `sqlc batchexec`? — `R-SQLC-BULK-1/2`.
   - Ошибки `batchexec` читаются через `br.Close()`? — `sqlc/bulk-insert-not-row-by-row`.
   - `for _, x := range items { q.Insert(ctx, ...) }` N раз → `sqlc/bulk-insert-not-row-by-row`.
   - Одна большая VALUES-строка конкатенацией в Go → `sqlc/bulk-insert-not-row-by-row`.

   ### Миграции (`R-SQLC-MIG-*`)
   - Схема через `golang-migrate` или `goose`; не `pgxpool.Exec("CREATE TABLE ...")` в application-коде? — `sqlc/schema-via-migration-tool`.
   - `sqlc.yaml` указывает `schema: "db/migrations"`; `sqlc generate` читает из файлов, не live-БД? — `sqlc/schema-via-migration-tool`.
   - Безопасность миграций (`expand-contract`, `CREATE INDEX CONCURRENTLY`, `lock_timeout`) по `pg-migrations/spec.md`? — `sqlc/schema-via-migration-tool`.
   - `migrate.Up()` при старте или отдельным CI-шагом; не вручную? — `sqlc/schema-via-migration-tool`.
   - Изменение уже применённой миграции → `sqlc/schema-via-migration-tool`.
   - `AutoMigrate`-паттерн (создание таблиц из Go-структур) → `sqlc/schema-via-migration-tool`.

   ### Тестирование (`R-SQLC-TEST-*`)
   - Интеграционные тесты репозитория против реального Postgres через `testcontainers-go`; не mock `pgx.Tx`/`pgxpool.Pool`? — `sqlc/repository-tested-against-real-database`.
   - Тест запускает миграции на чистой БД (`migrate.Up()` в `TestMain` или per-test); данные изолированы `tx.Rollback` в `t.Cleanup`? — `sqlc/tests-are-isolated-and-cover-errors`.
   - Тест покрывает: happy-path, `pgx.ErrNoRows`→`NotFoundError`, constraint-нарушение→доменная ошибка, откат при ошибке? — `sqlc/tests-are-isolated-and-cover-errors`.
   - `TestMain` инициализирует контейнер один раз (suite-уровень); не per-test поднятие? — `sqlc/repository-tested-against-real-database`.
   - Mock-реализации `pgxpool.Pool`/`pgx.Tx` вместо Testcontainers → `sqlc/repository-tested-against-real-database`.
   - Тесты без изоляции (shared state, нет rollback) → `sqlc/tests-are-isolated-and-cover-errors`.
   - Тест только happy-path без ошибок persistence → `sqlc/tests-are-isolated-and-cover-errors`.

4. **Cross-check:** DDL/типы колонок — `ucp-pg-schema-review` (`PG-T-*`); безопасность миграций — `ucp-pg-migration-review` (`PG-M-*`); блокировки/bulk под нагрузкой — `ucp-pg-runtime-review` (`PG-W-*`); CQRS-разделение — `ucp-go-cqrs-review`; ошибки-значения / apperr.Kind / errors.As — `ucp-go-error-handling-review`. Рекомендуй `errcheck`+`errorlint` в `golangci-lint`, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — возврат sqlc-типа наружу (`sqlc/repository-speaks-domain-types`), `pgxpool.Pool`/`db.Queries` в `core/` (`sqlc/port-in-core-implementation-in-adapter`), `nil, nil` при `ErrNoRows` (`sqlc/no-rows-becomes-domain-error`), `panic(err)` на pgx-ошибке (`sqlc/errors-wrapped-not-logged`), SQL с конкатенацией строк (`sqlc/queries-live-in-files`), `Begin`/`Commit` в репозитории (`sqlc/transaction-passed-explicitly`), `COMMIT` без проверки ошибки (`sqlc/rollback-deferred-commit-checked`), `AutoMigrate`-паттерн (`sqlc/schema-via-migration-tool`).
   - **Предупреждение** — бизнес-логика в репозитории (`sqlc/no-business-logic-in-repository`), `reflect`/json-маппинг (`sqlc/explicit-mapping`), `pgx.Tx` через `context.Value` (`sqlc/transaction-passed-explicitly`), двойное логирование pgx-ошибок (`sqlc/errors-wrapped-not-logged`), N+1 в цикле (`sqlc/no-query-per-row`), цикл `Insert` вместо bulk (`sqlc/bulk-insert-not-row-by-row`), `pgx.Connect` вместо pool (`sqlc/pool-is-singleton-and-configured`), изменение применённой миграции (`sqlc/schema-via-migration-tool`).
   - **Замечание** — маппинг размазан по репозиторию (`sqlc/explicit-mapping`), нет `overrides` в `sqlc.yaml` (`sqlc/codegen-config-sets-types`), нет интеграционного теста (`sqlc/repository-tested-against-real-database`), тест только happy-path (`sqlc/tests-are-isolated-and-cover-errors`), нет `pool.Ping` при старте (`sqlc/ping-on-start-close-on-stop`).

## Что не входит

- Бизнес-операции (Handler/UseCase) — `ucp-go-pattern-review`. Доменные инварианты — `ucp-go-ddd-tactical-review`.
- Типы колонок и безопасность миграций — `ucp-pg-schema-review` / `ucp-pg-migration-review`.
- Ошибки-значения, apperr.Kind, chi-middleware — `ucp-go-error-handling-review`.

$ARGUMENTS
