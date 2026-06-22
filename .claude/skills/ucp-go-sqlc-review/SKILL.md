---
name: ucp-go-sqlc-review
lang: go
description: Ревью persistence-слоя Go-сервиса по UCP (коды R-SQLC-*) — порт/маппер sqlc↔domain, TX на Handler через WithTx(pgx.Tx), pgxpool singleton, ErrNoRows→NotFoundError, ViewRepository, testcontainers-go.
when_to_use: Изменения в adapters/out/persistence (postgres_*_repository.go, *_mapper.go, *_view_repository.go), db/queries/*.sql, sqlc.yaml или db/migrations.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью persistence (Go / sqlc + pgx)

Ты ревьюишь persistence-слой Go-сервиса на соответствие `backend/go/sqlc/sqlc-rules.md` (`R-SQLC-*`).
Репозиторий реализует порт из `core/`, маппит sqlc-строки↔domain, граница транзакции — на Handler через
`WithTx(pgx.Tx)`. Статические нарушения (SQL-инъекция в строках, необработанные ошибки) ловит CI (`errcheck`,
`errorlint`, `golangci-lint`); здесь — семантика и архитектурные инварианты.

## Зависимости

- **`.claude/docs/backend/go/sqlc/sqlc-rules.md`** — правила `R-SQLC-*` (с код-примерами).
- Парные: `backend/usecase-pattern/go/...` (порт/слои, `R-LAY-*`/`R-HEX-*`/`R-TX-*`), `backend/error-handling/go/error-handling-style-guide.md` (`R-ERR-HIER-*`/`R-ERR-WHERE-*`), `backend/pg-types/pg-types-rules.md` (`PG-T-*` типы), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/pg-runtime-rules.md` (`PG-W-*` locks/bulk), `backend/cqrs/cqrs-rules.md` (`R-CQRS-4` read-проекции).

## Инструкции

1. **Прочти** `sqlc-rules.md`. Цитируй конкретные коды (`R-SQLC-REPO-X1`), не только префикс.

2. **Скоп.** `adapters/out/persistence/**` (`postgres_*_repository.go`, `*_mapper.go`, `*_view_repository.go`), `db/queries/*.sql`, `sqlc.yaml`, `db/migrations/**`, порт-`interface` в `core/<bc>/port/`, `git diff` на `.go` и `.sql`.

3. **Прогон.**

   ### Repository-pattern (`R-SQLC-REPO-*`)
   - Доменный порт — `interface` в `core/<bc>/port/`; реализация — `Postgres<X>Repository` в `adapters/out/persistence/`? — `R-SQLC-REPO-1`.
   - Public-методы принимают/возвращают доменные объекты (Aggregate/VO/read-DTO), не сгенерированные sqlc-строки и не `pgx.Row`? — `R-SQLC-REPO-2`.
   - `*db.Queries` / `pgxpool.Pool` инжектируется конструктором, не создаётся внутри? — `R-SQLC-REPO-3`.
   - Покрыт интеграционным тестом против `testcontainers-go`? — `R-SQLC-REPO-4`.
   - Возврат `db.<X>` (sqlc-тип) наружу → `R-SQLC-REPO-X1`.
   - Бизнес-логика в репозитории (`if order.Status == ...`) → `R-SQLC-REPO-X2`.
   - `pgxpool.Pool`/`db.Queries` напрямую в `core/` (Handler/Service/Aggregate) → `R-SQLC-REPO-X3` (cross-ref `R-HEX-X1`).

   ### sqlc codegen и query-файлы (`R-SQLC-QF-*`)
   - SQL — в `*.sql`-файлах под `db/queries/`; не строки в Go-коде? — `R-SQLC-QF-1`.
   - Каждый запрос аннотирован `-- name: <Name> :one|:many|:exec|:execrows|:batchexec`? — `R-SQLC-QF-2`.
   - `sqlc.yaml`: `engine: postgresql`, `emit_json_tags`, `emit_pointers_for_null_fields`, `overrides` для UUID/numeric/timestamptz? — `R-SQLC-QF-3`.
   - Nullable-поля через `pgtype.*` (pgx/v5) или кастомный тип из `overrides`; не `sql.NullString`/`sql.NullInt64`? — `R-SQLC-QF-4`.
   - Статус сгенерированного `db/` (`.gitignore` или коммитится с `*.sql`) зафиксирован в `sqlc.yaml` и CI? — `R-SQLC-QF-5`.
   - SQL с конкатенацией строк в Go (`"SELECT ... WHERE id = " + id`) → `R-SQLC-QF-X1`.
   - Ручная правка файлов `db/*.go` → `R-SQLC-QF-X2`.
   - `sqlc.yaml` без `overrides` для UUID/numeric/timestamptz → `R-SQLC-QF-X3`.

   ### Маппинг sqlc ↔ domain (`R-SQLC-MAP-*`)
   - Явные функции-маппера `toDomain(row db.X) *domain.X` и `toInsertParams(o *domain.X) db.XParams`, расположенные рядом с репозиторием (не внутри него)? — `R-SQLC-MAP-1`.
   - Сборка агрегата из нескольких sqlc-строк (nested-fetch) — в маппере, не размазана по репозиторию? — `R-SQLC-MAP-2`.
   - Маппер без бизнес-логики — только структурная конвертация? — `R-SQLC-MAP-3`.
   - `reflect`/`json.Marshal`+`json.Unmarshal` для маппинга sqlc→domain → `R-SQLC-MAP-X1`.
   - Прямой возврат sqlc-строки из репозитория «для экономии» → `R-SQLC-MAP-X2`.

   ### Транзакции (`R-SQLC-TX-*`)
   - Граница транзакции на Handler; репозиторий получает `pgx.Tx` через `WithTx(pgx.Tx)`, не открывает `Begin` самостоятельно? — `R-SQLC-TX-1/2`.
   - `defer tx.Rollback(ctx)` + явный `tx.Commit(ctx)` с проверкой ошибки? — `R-SQLC-TX-3`.
   - Read-only запросы без транзакции или с `pgx.TxOptions{AccessMode: pgx.ReadOnly}`? — `R-SQLC-TX-4`.
   - `Begin`/`Commit`/`Rollback` внутри репозитория → `R-SQLC-TX-X1`.
   - `pgx.Tx` через `context.Value` («скрытая TX») → `R-SQLC-TX-X2` (передавать явно через `WithTx`).
   - `tx.Commit(ctx)` без проверки ошибки → `R-SQLC-TX-X3`.

   ### pgxpool и соединение (`R-SQLC-POOL-*`)
   - `pgxpool.Pool` — singleton, инжектируется конструктором; не создаётся per-request? — `R-SQLC-POOL-1`.
   - `pgxpool.ParseConfig` + `pgxpool.NewWithConfig` с настройкой MinConns/MaxConns/MaxConnLifetime/HealthCheckPeriod? — `R-SQLC-POOL-2`.
   - DSN из env (`envconfig`/`os.Getenv`); не хардкодится? — `R-SQLC-POOL-3`.
   - `pool.Ping(ctx)` при старте — fail-fast если БД недоступна? — `R-SQLC-POOL-4`.
   - `pool.Close()` в `defer` или graceful-shutdown? — `R-SQLC-POOL-5`.
   - `pgx.Connect` (одиночное соединение) в production-коде → `R-SQLC-POOL-X1`.
   - `var pool *pgxpool.Pool` глобально → `R-SQLC-POOL-X2`.
   - Пропущен `pool.Ping` при старте → `R-SQLC-POOL-X3`.

   ### Ошибки и pgx (`R-SQLC-ERR-*`)
   - `pgx.ErrNoRows` → доменная `NotFoundError` с контекстом (`EntityType`, `ID`); не `nil, nil`? — `R-SQLC-ERR-1` (cross-ref `R-ERR-WHERE-X3`).
   - `pgconn.PgError` с `Code`: `23505` (unique) → ошибка конфликта; `23503` (fk) → доменная; остальные — техническая обёртка? — `R-SQLC-ERR-2` (cross-ref `R-ERR-HIER-1`).
   - pgx-ошибки оборачиваются `fmt.Errorf("find order %s: %w", id, err)` и всплывают вверх; не логируются в репозитории? — `R-SQLC-ERR-3` (cross-ref `R-ERR-LOG-4`).
   - Таймаут через `context.WithTimeout` на хендлере или middleware; не внутри репозитория? — `R-SQLC-ERR-4`.
   - `return nil, nil` при `pgx.ErrNoRows` → `R-SQLC-ERR-X1`.
   - Логирование pgx-ошибки в репозитории + проброс вверх (двойное логирование) → `R-SQLC-ERR-X2`.
   - `panic(err)` на pgx-ошибке → `R-SQLC-ERR-X3` (cross-ref `R-ERR-RESULT-1`).

   ### Nested-fetch и связанные агрегаты (`R-SQLC-NEST-*`)
   - Загрузка агрегата с вложенными сущностями — `:many` JOIN + сборка в маппере через `map[uuid.UUID]*X`? — `R-SQLC-NEST-1/2`.
   - `JOIN` с `array_agg`/`json_agg` допустим для простых вложений; сложные — два запроса в рамках одной TX? — `R-SQLC-NEST-3`.
   - Read-проекции (CQRS) — отдельный `<X>ViewRepository`, возвращает read-DTO, не полный агрегат? — `R-SQLC-NEST-4` (cross-ref `R-CQRS-4`).
   - N+1: `for _, id := range ids { repo.FindByID(ctx, id) }` → `R-SQLC-NEST-X1` (заменить на `WHERE id = ANY($1)`).
   - Загрузка полного агрегата для read-only проекции → `R-SQLC-NEST-X2`.

   ### Bulk-операции (`R-SQLC-BULK-*`)
   - Bulk-вставка >1000 строк — `pgx.CopyFrom`; умеренный объём — `sqlc batchexec`? — `R-SQLC-BULK-1/2`.
   - Ошибки `batchexec` читаются через `br.Close()`? — `R-SQLC-BULK-3`.
   - `for _, x := range items { q.Insert(ctx, ...) }` N раз → `R-SQLC-BULK-X1`.
   - Одна большая VALUES-строка конкатенацией в Go → `R-SQLC-BULK-X2`.

   ### Миграции (`R-SQLC-MIG-*`)
   - Схема через `golang-migrate` или `goose`; не `pgxpool.Exec("CREATE TABLE ...")` в application-коде? — `R-SQLC-MIG-1`.
   - `sqlc.yaml` указывает `schema: "db/migrations"`; `sqlc generate` читает из файлов, не live-БД? — `R-SQLC-MIG-2`.
   - Безопасность миграций (`expand-contract`, `CREATE INDEX CONCURRENTLY`, `lock_timeout`) по `pg-migrations-rules.md`? — `R-SQLC-MIG-3`.
   - `migrate.Up()` при старте или отдельным CI-шагом; не вручную? — `R-SQLC-MIG-4`.
   - Изменение уже применённой миграции → `R-SQLC-MIG-X1`.
   - `AutoMigrate`-паттерн (создание таблиц из Go-структур) → `R-SQLC-MIG-X2`.

   ### Тестирование (`R-SQLC-TEST-*`)
   - Интеграционные тесты репозитория против реального Postgres через `testcontainers-go`; не mock `pgx.Tx`/`pgxpool.Pool`? — `R-SQLC-TEST-1`.
   - Тест запускает миграции на чистой БД (`migrate.Up()` в `TestMain` или per-test); данные изолированы `tx.Rollback` в `t.Cleanup`? — `R-SQLC-TEST-2`.
   - Тест покрывает: happy-path, `pgx.ErrNoRows`→`NotFoundError`, constraint-нарушение→доменная ошибка, откат при ошибке? — `R-SQLC-TEST-3`.
   - `TestMain` инициализирует контейнер один раз (suite-уровень); не per-test поднятие? — `R-SQLC-TEST-4`.
   - Mock-реализации `pgxpool.Pool`/`pgx.Tx` вместо Testcontainers → `R-SQLC-TEST-X1`.
   - Тесты без изоляции (shared state, нет rollback) → `R-SQLC-TEST-X2`.
   - Тест только happy-path без ошибок persistence → `R-SQLC-TEST-X3`.

4. **Cross-check:** DDL/типы колонок — `ucp-pg-schema-review` (`PG-T-*`); безопасность миграций — `ucp-pg-migration-review` (`PG-M-*`); блокировки/bulk под нагрузкой — `ucp-pg-runtime-review` (`PG-W-*`); CQRS-разделение — `ucp-go-cqrs-review`; ошибки-значения / apperr.Kind / errors.As — `ucp-go-error-handling-review`. Рекомендуй `errcheck`+`errorlint` в `golangci-lint`, если их нет.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — возврат sqlc-типа наружу (`R-SQLC-REPO-X1`), `pgxpool.Pool`/`db.Queries` в `core/` (`R-SQLC-REPO-X3`), `nil, nil` при `ErrNoRows` (`R-SQLC-ERR-X1`), `panic(err)` на pgx-ошибке (`R-SQLC-ERR-X3`), SQL с конкатенацией строк (`R-SQLC-QF-X1`), `Begin`/`Commit` в репозитории (`R-SQLC-TX-X1`), `COMMIT` без проверки ошибки (`R-SQLC-TX-X3`), `AutoMigrate`-паттерн (`R-SQLC-MIG-X2`).
   - **Предупреждение** — бизнес-логика в репозитории (`R-SQLC-REPO-X2`), `reflect`/json-маппинг (`R-SQLC-MAP-X1`), `pgx.Tx` через `context.Value` (`R-SQLC-TX-X2`), двойное логирование pgx-ошибок (`R-SQLC-ERR-X2`), N+1 в цикле (`R-SQLC-NEST-X1`), цикл `Insert` вместо bulk (`R-SQLC-BULK-X1`), `pgx.Connect` вместо pool (`R-SQLC-POOL-X1`), изменение применённой миграции (`R-SQLC-MIG-X1`).
   - **Замечание** — маппинг размазан по репозиторию (`R-SQLC-MAP-2`), нет `overrides` в `sqlc.yaml` (`R-SQLC-QF-X3`), нет интеграционного теста (`R-SQLC-REPO-4`), тест только happy-path (`R-SQLC-TEST-X3`), нет `pool.Ping` при старте (`R-SQLC-POOL-X3`).

## Что не входит

- Бизнес-операции (Handler/UseCase) — `ucp-go-pattern-review`. Доменные инварианты — `ucp-go-ddd-tactical-review`.
- Типы колонок и безопасность миграций — `ucp-pg-schema-review` / `ucp-pg-migration-review`.
- Ошибки-значения, apperr.Kind, chi-middleware — `ucp-go-error-handling-review`.

$ARGUMENTS
