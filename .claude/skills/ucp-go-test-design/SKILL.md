---
name: ucp-go-test-design
lang: go
description: Спроектировать тесты Go-сервиса (net/http + chi) по UCP — интеграционные на Postgres через testcontainers-go + http.DefaultClient, мок внешнего HTTP через httptest, Clock/IDGenerator через конструкторную DI, Outbox вместо Kafka/Redis.
when_to_use: После нового UseCase/Handler. Триггеры — «тесты для X», «integration-тест на команду Y», «написать тест на агрегат».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Проектирование тестов (Go / net/http + chi)

Ты пишешь тесты для Go-сервиса по `.claude/docs/backend/go/go-test-strategy/spec.md` (`GOTEST-*`).

## Зависимости

- **`.claude/docs/backend/go/go-test-strategy/spec.md`** — правила `GOTEST-*` (код-примеры включены).
- Спека (если есть) — сценарии из use case-ов (UC-N) и бизнес-правил (BR-N).
- Парные: `backend/go/go-test-strategy/spec.md` (структура сервиса), `backend/error-handling/references/go/implementation.md` (apperr.Kind + errors.As — как проверять коды ошибок), `backend/go/sqlc/spec.md` (`R-SQLC-*` — репозиторий против Testcontainers), `backend/auth-patterns/references/go/implementation.md` (`auth-patterns/no-secrets-in-repository`/`auth-patterns/money-commands-need-idempotency-key` — фейковый JWT, Idempotency-Key).

## Инструкции

1. **Прочти** `.claude/docs/backend/go/go-test-strategy/spec.md` (`GOTEST-*`). Коды в комментариях тестов НЕ цитируй; в комментарии над функцией — цитата BR/UC допустима (бизнес-описание).

2. **Определи слой** и назови его в начале ответа:
   - **Unit** (без инфраструктуры) — чистая логика агрегата/VO: `NewOrder(...)`, `order.Cancel()`, `assert.ErrorAs(t, err, &domainErr)` (`go-test-strategy/test-layers-separated`).
   - **Контроллер без БД** — `httptest.NewRecorder` + реальный chi-роутер + in-memory реализация интерфейса репозитория; Testcontainers не поднимаем (`go-test-strategy/test-layers-separated`).
   - **Интеграционный** — `httptest.NewServer(router)` + реальный PostgreSQL через testcontainers-go + `http.DefaultClient` (`go-test-strategy/integration-test-shape`).
   - **E2E** — build-tag `e2e`, настоящие Kafka/внешние сервисы, отдельный CI-этап, ≤ 10 тестов (`go-test-strategy/test-layers-separated`).

3. **Если инфраструктура тестов ещё не готова** — создай в пакете (`GOTEST-4..7`): `TestMain(m *testing.M)` с `postgres.Run` (testcontainers-go, образ `postgres:16-alpine`), применением миграций один раз, `m.Run()`, завершением контейнера через `defer`; пакетная переменная `testDSN`; `newTestServer(t *testing.T)` — собирает `sqlc.New(pool)` + все зависимости + chi-роутер + `httptest.NewServer` + `t.Cleanup(srv.Close)`. Kafka/go-redis — **не поднимать** (`go-test-strategy/no-broker-or-cache`).

4. **`<Domain>DatabasePreparer`** (`GOTEST-11..14`) — над `pgxpool.Pool` напрямую (не через sqlc): `Clear(t)` вызывает `TRUNCATE ... CASCADE` в правильном порядке FK-зависимостей; fluent `Create*(t, ...)`/`Find*(t, ...)`. Схему не пересоздавать между тестами — только `TRUNCATE` (`go-test-strategy/schema-once-data-cleaned`).

5. **Детерминизм** (`GOTEST-8..10`) — время и UUID в домене инжектируются через интерфейсы `Clock`/`IDGenerator`; в тесте — `fixedClock{at: time.Date(...)}` и `seqIDGenerator` (счётчик); сравниваем с ожидаемым значением из `fixedClock`, не с `time.Now()`.

6. **Каждый тест** — AAA (`// Arrange`, `// Act`, `// Assert`); имя `Test<Action>_<Condition>_<Expected>`; комментарий над функцией с кодом BR из спеки; `t.Parallel()` в интеграционных; `Clear(t)` в начале каждого теста (`GOTEST-15..18`).

7. **Покрытие:** на каждый UC — happy + альтернативы + ошибки; на каждый BR — отдельный тест; на каждое доменное событие — проверка Outbox-таблицы через `DatabasePreparer.FindOutboxEvents(t, "EVENT_TYPE")` (`go-test-strategy/no-broker-or-cache`); на каждый код ошибки — проверка статуса + декодированного `problem+json` (`status`/`code`).

8. **Авторизация** (`GOTEST-29..30`) — подменяем JWT-валидатор на `fakeAuthMiddleware(principal)`, который прокидывает фейковый `Principal` в контекст; тест обязан проверять `401`/`403` при неверной роли (`go-test-strategy/auth-is-faked-not-disabled`); хелперы `AdminPrincipal()`/`CustomerPrincipal(id)` — в общем `testhelper`-пакете.

9. **Внешний HTTP** (`GOTEST-23..25`) — только если есть исходящие вызовы: `httptest.NewServer(http.HandlerFunc(...))` в самом тесте; stub проверяет входящий запрос (метод, заголовки, тело); base-url клиента переопределяется через конструктор; `t.Cleanup(stub.Close)`.

10. **Самопроверка** по чеклисту из `go-test-strategy/spec.md` §«Чеклист подключения к новому сервису» + предложи `ucp-go-test-review`.

## Антипаттерны, которые НЕ генерировать

- `time.Sleep`/polling-цикл/`testify/assert.Eventually` в тесте как способ «подождать» (`go-test-strategy/tests-are-deterministic`); `time.Now()`/`uuid.New()` напрямую в домене вместо DI-интерфейса (`go-test-strategy/tests-are-deterministic`/`go-test-strategy/tests-are-deterministic`).
- `DROP TABLE`/пересоздание схемы между тестами (`go-test-strategy/schema-once-data-cleaned`); Testcontainers Kafka/go-redis в базовом интеграционном тесте (`go-test-strategy/no-broker-or-cache`).
- Мокать `Repository`-интерфейс через `testify/mock` в интеграционном тесте (`go-test-strategy/test-layers-separated`) — `mock.Repository` допустим только в unit-тесте контроллера/Handler.
- Реальный Keycloak/JWKS в интеграционном тесте (`go-test-strategy/auth-is-faked-not-disabled`); отключение auth-middleware полностью (`go-test-strategy/auth-is-faked-not-disabled`).
- `ioutil.ReadAll` + `fmt.Println` вместо `t.Logf` (`go-test-strategy/requests-are-fully-controlled`); `testify/mock` на HTTP-клиент вместо реального `httptest.NewServer` (`go-test-strategy/external-calls-via-stub-server`).

После работы скилла — обязательно `ucp-go-test-review`.

$ARGUMENTS
