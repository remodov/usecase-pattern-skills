---
name: ucp-go-test-review
lang: go
description: Ревью тестов Go-сервиса (net/http + chi) по UCP Test Strategy (коды GOTEST-*) — слой теста, детерминизм (Clock/IDGenerator), Testcontainers Postgres + httptest, DatabasePreparer, мок внешних HTTP, Outbox вместо Kafka/Redis, покрытие UC/BR.
when_to_use: Свеженаписанные или изменённые тесты (*_test.go, TestMain, *Preparer) или онбординг модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью тестов (Go / net/http + chi)

Ты ревьюишь тесты Go-сервиса на соответствие `backend/go/go-test-strategy/go-test-strategy-rules.md` (`GOTEST-*`).
Главные точки: правильный слой, детерминизм (Clock/IDGenerator через конструктор), Testcontainers только для Postgres,
внешний HTTP — через `httptest.NewServer`, Kafka/Redis — выключены профилем, покрытие UC/BR.

## Зависимости

- **`.claude/docs/backend/go/go-test-strategy/go-test-strategy-rules.md`** — правила `GOTEST-*` (код-примеры включены, отдельного style-guide нет).
- Спека (если есть) — UC-/BR-коды, цитируются в комментарии перед тестом.
- Парные: `backend/usecase-pattern/go/...` (`R-UC-*`/`R-HND-*` — UseCase покрывается интеграционным), `backend/go/sqlc/sqlc-rules.md` (`R-SQLC-*` — репозиторий против Testcontainers), `backend/resilience/resilience-rules.md` (`R-RES-*` — мок внешнего HTTP), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-17`/`AUTH-19` — фейковый JWT, Idempotency-Key), `backend/error-handling/go/error-handling-style-guide.md` (`apperr.Kind + errors.As`).

## Инструкции

1. **Прочти** `go-test-strategy-rules.md`. Цитируй конкретные коды (`GOTEST-19`, `GOTEST-X1`), не только префикс.

2. **Скоп.** `**/*_test.go`, `**/testmain_test.go`, `**/*preparer*.go`, `**/testhelper/**`, `**/testutil/**`, `newTestServer`-функции; `git diff` на `.go`-файлы.

3. **Прогон.**

   ### Слой и структура (`GOTEST-1..3`, `GOTEST-26..28`)
   - Интеграционный — `httptest.NewServer(router)` + реальный Postgres (Testcontainers), вызов через `http.DefaultClient`? (`GOTEST-1`)
   - Pure-unit агрегата — без инфраструктуры, `assert.ErrorAs` на доменную ошибку? (`GOTEST-26`)
   - Unit контроллера — `httptest.NewRecorder` + chi-роутер + in-memory реализация интерфейса (не Testcontainers)? (`GOTEST-27`) `testify/mock` на `Repository` **здесь** допустим (`GOTEST-X9` — только в интеграционном).
   - E2E помечен build-tag `e2e`, отдельный CI-этап, ≤ 10 тестов? (`GOTEST-28`)
   - Чистая бизнес-логика, написанная как интеграционный → раздувает CI (`GOTEST-26`).
   - `t.Parallel()` в каждом интеграционном тесте? (`GOTEST-18`)

   ### Детерминизм (`GOTEST-2`, `GOTEST-8..10`)
   - Нет `time.Sleep`/polling-цикла/`testify/assert.Eventually` как способа «дождаться»? (`GOTEST-X1`)
   - Время в домене через интерфейс `Clock`; в тесте — `fixedClock` с предзаданным значением; нет `time.Now()` в `Handler`/`Service`/`Aggregate`? (`GOTEST-8`/`GOTEST-X4`)
   - UUID/ID через `IDGenerator`; в тесте — `seqIDGenerator`/`staticIDGenerator`? (`GOTEST-9`/`GOTEST-X4`)
   - Временны́е поля в assert сравниваются с `fixedClock.at`, не с `time.Now()`? (`GOTEST-10`)

   ### Инфраструктура (`GOTEST-4..7`, `GOTEST-X3`)
   - Один `TestMain(m *testing.M)` на пакет — поднимает `postgres.Run` (testcontainers-go), применяет миграции, `defer pg.Terminate`? (`GOTEST-4`)
   - DSN в пакетной переменной или `sync.Once`-синглтоне; не хардкодится строкой подключения в тесте? (`GOTEST-5`)
   - Схема разворачивается один раз в `TestMain`, не пересоздаётся между тестами — только `TRUNCATE`? (`GOTEST-6`)
   - `newTestServer(t)` — собирает `sqlc.New(pool)` + зависимости + chi-роутер + `httptest.NewServer`, регистрирует `t.Cleanup(srv.Close)`? (`GOTEST-7`)
   - Нет `DROP TABLE`/пересоздания схемы между тестами? (`GOTEST-X3`)

   ### DatabasePreparer (`GOTEST-11..14`, `GOTEST-X5`)
   - На каждый Bounded Context — `<Domain>DatabasePreparer` с `pgxpool.Pool`; методы `Clear(t)`/`Create*(t,...)`/`Find*(t,...)`? (`GOTEST-11`)
   - `Clear(t)` вызывает `TRUNCATE ... CASCADE` в правильном порядке (FK: зависимые сначала)? Вызывается в начале каждого теста? (`GOTEST-12`)
   - Порядок `Create*`-методов отражает FK-зависимости (родительскую запись раньше дочерней)? (`GOTEST-13`)
   - SQL в препарере — через `pgx` (raw-строки), не через sqlc-генерацию (независимость от доменного слоя)? (`GOTEST-14`)
   - Нет общего `TRUNCATE` всех таблиц в произвольном порядке? (`GOTEST-X5`)

   ### Структура теста (`GOTEST-15..18`)
   - Имя теста `Test<Action>_<Condition>_<Expected>` (PascalCase)? Комментарий с кодом BR из спеки перед функцией? (`GOTEST-15`)
   - `testify/require` (fatal) — для setup-шагов; `testify/assert` (continue) — для assertion-блока; прямой `t.Fatal` — только в `TestMain`? (`GOTEST-16`)
   - HTTP-запрос через `http.DefaultClient`; статус через `require.Equal`; тело через `json.Unmarshal + assert`? (`GOTEST-17`)
   - `t.Parallel()` в каждом интеграционном тесте; `Clear` в начале теста изолирует данные? (`GOTEST-18`)
   - Нет `ioutil.ReadAll + fmt.Println` вместо `t.Logf`/`t.Errorf`? (`GOTEST-X6`)

   ### Kafka, Redis, async (`GOTEST-19..22`, `GOTEST-X7`)
   - Нет Testcontainers Kafka/Redis в базовых интеграционных тестах? (`GOTEST-X7`)
   - События проверяются через `DatabasePreparer.FindOutboxEvents(t, ...)` (Outbox-таблица), не Kafka? (`GOTEST-19`)
   - Redis не поднимается — `integration-test`-профиль/build-tag подменяет `cache.Client` на `NoopCache`? (`GOTEST-20`)
   - Idempotent consumer тестируется прямым вызовом `handler.Handle(ctx, testMsg)`, без брокера? (`GOTEST-21`)
   - Outbox-relay/async-воркер вызывается синхронно: `relay.ProcessPending(ctx)`, без фонового ожидания? (`GOTEST-22`)

   ### Внешний HTTP (`GOTEST-23..25`, `GOTEST-X8`)
   - Внешний REST — `httptest.NewServer(http.HandlerFunc(...))` в тесте, `t.Cleanup(stub.Close)`? (`GOTEST-23`)
   - Заглушка в самом тесте, не в глобальных фикстурах? (`GOTEST-24`)
   - Заглушка проверяет входящий запрос (заголовки, метод, тело через `io.ReadAll + assert`)? (`GOTEST-25`)
   - Нет `testify/mock` на интерфейс HTTP-клиента (теряется проверка сериализации/заголовков/retry)? (`GOTEST-X8`)

   ### Авторизация (`GOTEST-29..30`, `GOTEST-X10`, `GOTEST-X11`)
   - JWT-валидатор в тестовом роутере подменён на `fakeAuthMiddleware(principal)`, который прокидывает `Principal` в контекст? (`GOTEST-29`)
   - Хелперы авторизации (`AdminPrincipal()`/`CustomerPrincipal(id)`) вынесены в `testhelper`-пакет, не дублируются? (`GOTEST-30`)
   - Нет реального Keycloak/JWKS в интеграционном тесте? (`GOTEST-X10`)
   - Auth-middleware не отключается полностью; тест проверяет, что `403`/`401` возвращается при неверной роли? (`GOTEST-X11`)

4. **Покрытие** (`GOTEST-15`): на каждый UC из спеки — happy + альтернативы + ошибки; на каждый BR — отдельный тест с кодом в комментарии; на каждое событие — проверка строки в Outbox (`FindOutboxEvents`); на каждый код ошибки (`apperr.Kind`) — `problem+json`-ответ + корректный статус. Пропущенные UC-/BR-сценарии — findings с `GOTEST-15`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `time.Sleep`/polling в тесте (`GOTEST-X1`), `time.Now()`/`uuid.New()` в домене без инжекции (`GOTEST-X4`), Testcontainers Kafka/Redis в базовых тестах (`GOTEST-X7`), `testify/mock` на `Repository` в интеграционном (`GOTEST-X9`), отключённый auth-middleware в интеграционном (`GOTEST-X11`), реальный JWKS/Keycloak (`GOTEST-X10`).
   - **Предупреждение** — `DROP TABLE`/пересоздание схемы между тестами (`GOTEST-X3`), `testify/mock` на HTTP-клиент вместо `httptest` (`GOTEST-X8`), `TRUNCATE` в произвольном порядке (`GOTEST-X5`), pure-unit написан как интеграционный (`GOTEST-26`), нет `t.Parallel()` в интеграционном.
   - **Замечание** — нет BR-кода в комментарии при наличии спеки (`GOTEST-15`), заглушка в глобальных фикстурах вместо теста (`GOTEST-24`), `fmt.Println` вместо `t.Logf` (`GOTEST-X6`), хелперы авторизации дублируются в каждом файле (`GOTEST-30`).

## Что не входит

- Дизайн новых тестов — `ucp-go-test-design`. Бизнес-логика UseCase/Handler — `ucp-go-pattern-review`.
- sqlc-запросы в препарере — `ucp-go-sqlc-review`. Типы колонок — `ucp-pg-schema-review`.
- Retry/CB-конфигурация — `ucp-go-resilience-review`. Observability в тестах — `ucp-go-observability-review`.

$ARGUMENTS
