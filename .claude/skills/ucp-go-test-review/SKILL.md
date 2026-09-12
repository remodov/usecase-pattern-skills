---
name: ucp-go-test-review
lang: go
description: Ревью тестов Go-сервиса (net/http + chi) по UCP Test Strategy — слой теста, детерминизм (Clock/IDGenerator), Testcontainers Postgres + httptest, DatabasePreparer, мок внешних HTTP, Outbox вместо Kafka/Redis, покрытие UC/BR.
when_to_use: Свеженаписанные или изменённые тесты (*_test.go, TestMain, *Preparer) или онбординг модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью тестов (Go / net/http + chi)

Ты ревьюишь тесты Go-сервиса на соответствие `backend/go/go-test-strategy/spec.md` (`GOTEST-*`).
Главные точки: правильный слой, детерминизм (Clock/IDGenerator через конструктор), Testcontainers только для Postgres,
внешний HTTP — через `httptest.NewServer`, Kafka/Redis — выключены профилем, покрытие UC/BR.

## Зависимости

- **`.claude/docs/backend/go/go-test-strategy/spec.md`** — правила `GOTEST-*` (код-примеры включены, отдельного справочника нет).
- Спека (если есть) — UC-/BR-коды, цитируются в комментарии перед тестом.
- Парные: `backend/usecase-pattern/go/...` (`R-UC-*`/`R-HND-*` — UseCase покрывается интеграционным), `backend/go/sqlc/spec.md` (`R-SQLC-*` — репозиторий против Testcontainers), `backend/resilience/spec.md` (`R-RES-*` — мок внешнего HTTP), `backend/auth-patterns/spec.md` (`auth-patterns/no-secrets-in-repository`/`auth-patterns/money-commands-need-idempotency-key` — фейковый JWT, Idempotency-Key), `backend/error-handling/references/go/implementation.md` (`apperr.Kind + errors.As`).

## Инструкции

1. **Прочти** `go-test-strategy/spec.md`. Цитируй конкретные коды (`go-test-strategy/no-broker-or-cache`, `go-test-strategy/tests-are-deterministic`), не только префикс.

2. **Скоп.** `**/*_test.go`, `**/testmain_test.go`, `**/*preparer*.go`, `**/testhelper/**`, `**/testutil/**`, `newTestServer`-функции; `git diff` на `.go`-файлы.

3. **Прогон.**

   ### Слой и структура (`GOTEST-1..3`, `GOTEST-26..28`)
   - Интеграционный — `httptest.NewServer(router)` + реальный Postgres (Testcontainers), вызов через `http.DefaultClient`? (`go-test-strategy/integration-test-shape`)
   - Pure-unit агрегата — без инфраструктуры, `assert.ErrorAs` на доменную ошибку? (`go-test-strategy/test-layers-separated`)
   - Unit контроллера — `httptest.NewRecorder` + chi-роутер + in-memory реализация интерфейса (не Testcontainers)? (`go-test-strategy/test-layers-separated`) `testify/mock` на `Repository` **здесь** допустим (`go-test-strategy/test-layers-separated` — только в интеграционном).
   - E2E помечен build-tag `e2e`, отдельный CI-этап, ≤ 10 тестов? (`go-test-strategy/test-layers-separated`)
   - Чистая бизнес-логика, написанная как интеграционный → раздувает CI (`go-test-strategy/test-layers-separated`).
   - `t.Parallel()` в каждом интеграционном тесте? (`go-test-strategy/isolation-matches-parallelism`)

   ### Детерминизм (`go-test-strategy/tests-are-deterministic`, `GOTEST-8..10`)
   - Нет `time.Sleep`/polling-цикла/`testify/assert.Eventually` как способа «дождаться»? (`go-test-strategy/tests-are-deterministic`)
   - Время в домене через интерфейс `Clock`; в тесте — `fixedClock` с предзаданным значением; нет `time.Now()` в `Handler`/`Service`/`Aggregate`? (`go-test-strategy/tests-are-deterministic`/`go-test-strategy/tests-are-deterministic`)
   - UUID/ID через `IDGenerator`; в тесте — `seqIDGenerator`/`staticIDGenerator`? (`go-test-strategy/tests-are-deterministic`/`go-test-strategy/tests-are-deterministic`)
   - Временны́е поля в assert сравниваются с `fixedClock.at`, не с `time.Now()`? (`go-test-strategy/tests-are-deterministic`)

   ### Инфраструктура (`GOTEST-4..7`, `go-test-strategy/schema-once-data-cleaned`)
   - Один `TestMain(m *testing.M)` на пакет — поднимает `postgres.Run` (testcontainers-go), применяет миграции, `defer pg.Terminate`? (`go-test-strategy/container-once-per-package`)
   - DSN в пакетной переменной или `sync.Once`-синглтоне; не хардкодится строкой подключения в тесте? (`go-test-strategy/container-once-per-package`)
   - Схема разворачивается один раз в `TestMain`, не пересоздаётся между тестами — только `TRUNCATE`? (`go-test-strategy/schema-once-data-cleaned`)
   - `newTestServer(t)` — собирает `sqlc.New(pool)` + зависимости + chi-роутер + `httptest.NewServer`, регистрирует `t.Cleanup(srv.Close)`? (`go-test-strategy/test-server-helper`)
   - Нет `DROP TABLE`/пересоздания схемы между тестами? (`go-test-strategy/schema-once-data-cleaned`)

   ### DatabasePreparer (`GOTEST-11..14`, `go-test-strategy/database-preparer-per-context`)
   - На каждый Bounded Context — `<Domain>DatabasePreparer` с `pgxpool.Pool`; методы `Clear(t)`/`Create*(t,...)`/`Find*(t,...)`? (`go-test-strategy/database-preparer-per-context`)
   - `Clear(t)` вызывает `TRUNCATE ... CASCADE` в правильном порядке (FK: зависимые сначала)? Вызывается в начале каждого теста? (`go-test-strategy/database-preparer-per-context`)
   - Порядок `Create*`-методов отражает FK-зависимости (родительскую запись раньше дочерней)? (`go-test-strategy/database-preparer-per-context`)
   - SQL в препарере — через `pgx` (raw-строки), не через sqlc-генерацию (независимость от доменного слоя)? (`go-test-strategy/database-preparer-per-context`)
   - Нет общего `TRUNCATE` всех таблиц в произвольном порядке? (`go-test-strategy/database-preparer-per-context`)

   ### Структура теста (`GOTEST-15..18`)
   - Имя теста `Test<Action>_<Condition>_<Expected>` (PascalCase)? Комментарий с кодом BR из спеки перед функцией? (`go-test-strategy/test-name-states-case`)
   - `testify/require` (fatal) — для setup-шагов; `testify/assert` (continue) — для assertion-блока; прямой `t.Fatal` — только в `TestMain`? (`go-test-strategy/assertions-split-by-severity`)
   - HTTP-запрос через `http.DefaultClient`; статус через `require.Equal`; тело через `json.Unmarshal + assert`? (`go-test-strategy/requests-are-fully-controlled`)
   - `t.Parallel()` в каждом интеграционном тесте; `Clear` в начале теста изолирует данные? (`go-test-strategy/isolation-matches-parallelism`)
   - Нет `ioutil.ReadAll + fmt.Println` вместо `t.Logf`/`t.Errorf`? (`go-test-strategy/requests-are-fully-controlled`)

   ### Kafka, Redis, async (`GOTEST-19..22`, `go-test-strategy/no-broker-or-cache`)
   - Нет Testcontainers Kafka/Redis в базовых интеграционных тестах? (`go-test-strategy/no-broker-or-cache`)
   - События проверяются через `DatabasePreparer.FindOutboxEvents(t, ...)` (Outbox-таблица), не Kafka? (`go-test-strategy/no-broker-or-cache`)
   - Redis не поднимается — `integration-test`-профиль/build-tag подменяет `cache.Client` на `NoopCache`? (`go-test-strategy/no-broker-or-cache`)
   - Idempotent consumer тестируется прямым вызовом `handler.Handle(ctx, testMsg)`, без брокера? (`go-test-strategy/no-broker-or-cache`)
   - Outbox-relay/async-воркер вызывается синхронно: `relay.ProcessPending(ctx)`, без фонового ожидания? (`go-test-strategy/no-broker-or-cache`)

   ### Внешний HTTP (`GOTEST-23..25`, `go-test-strategy/external-calls-via-stub-server`)
   - Внешний REST — `httptest.NewServer(http.HandlerFunc(...))` в тесте, `t.Cleanup(stub.Close)`? (`go-test-strategy/external-calls-via-stub-server`)
   - Заглушка в самом тесте, не в глобальных фикстурах? (`go-test-strategy/external-calls-via-stub-server`)
   - Заглушка проверяет входящий запрос (заголовки, метод, тело через `io.ReadAll + assert`)? (`go-test-strategy/external-calls-via-stub-server`)
   - Нет `testify/mock` на интерфейс HTTP-клиента (теряется проверка сериализации/заголовков/retry)? (`go-test-strategy/external-calls-via-stub-server`)

   ### Авторизация (`GOTEST-29..30`, `go-test-strategy/auth-is-faked-not-disabled`, `go-test-strategy/auth-is-faked-not-disabled`)
   - JWT-валидатор в тестовом роутере подменён на `fakeAuthMiddleware(principal)`, который прокидывает `Principal` в контекст? (`go-test-strategy/auth-is-faked-not-disabled`)
   - Хелперы авторизации (`AdminPrincipal()`/`CustomerPrincipal(id)`) вынесены в `testhelper`-пакет, не дублируются? (`go-test-strategy/auth-is-faked-not-disabled`)
   - Нет реального Keycloak/JWKS в интеграционном тесте? (`go-test-strategy/auth-is-faked-not-disabled`)
   - Auth-middleware не отключается полностью; тест проверяет, что `403`/`401` возвращается при неверной роли? (`go-test-strategy/auth-is-faked-not-disabled`)

4. **Покрытие** (`go-test-strategy/test-name-states-case`): на каждый UC из спеки — happy + альтернативы + ошибки; на каждый BR — отдельный тест с кодом в комментарии; на каждое событие — проверка строки в Outbox (`FindOutboxEvents`); на каждый код ошибки (`apperr.Kind`) — `problem+json`-ответ + корректный статус. Пропущенные UC-/BR-сценарии — findings с `go-test-strategy/test-name-states-case`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `time.Sleep`/polling в тесте (`go-test-strategy/tests-are-deterministic`), `time.Now()`/`uuid.New()` в домене без инжекции (`go-test-strategy/tests-are-deterministic`), Testcontainers Kafka/Redis в базовых тестах (`go-test-strategy/no-broker-or-cache`), `testify/mock` на `Repository` в интеграционном (`go-test-strategy/test-layers-separated`), отключённый auth-middleware в интеграционном (`go-test-strategy/auth-is-faked-not-disabled`), реальный JWKS/Keycloak (`go-test-strategy/auth-is-faked-not-disabled`).
   - **Предупреждение** — `DROP TABLE`/пересоздание схемы между тестами (`go-test-strategy/schema-once-data-cleaned`), `testify/mock` на HTTP-клиент вместо `httptest` (`go-test-strategy/external-calls-via-stub-server`), `TRUNCATE` в произвольном порядке (`go-test-strategy/database-preparer-per-context`), pure-unit написан как интеграционный (`go-test-strategy/test-layers-separated`), нет `t.Parallel()` в интеграционном.
   - **Замечание** — нет BR-кода в комментарии при наличии спеки (`go-test-strategy/test-name-states-case`), заглушка в глобальных фикстурах вместо теста (`go-test-strategy/external-calls-via-stub-server`), `fmt.Println` вместо `t.Logf` (`go-test-strategy/requests-are-fully-controlled`), хелперы авторизации дублируются в каждом файле (`go-test-strategy/auth-is-faked-not-disabled`).

## Что не входит

- Дизайн новых тестов — `ucp-go-test-design`. Бизнес-логика UseCase/Handler — `ucp-go-pattern-review`.
- sqlc-запросы в препарере — `ucp-go-sqlc-review`. Типы колонок — `ucp-pg-schema-review`.
- Retry/CB-конфигурация — `ucp-go-resilience-review`. Observability в тестах — `ucp-go-observability-review`.

$ARGUMENTS
