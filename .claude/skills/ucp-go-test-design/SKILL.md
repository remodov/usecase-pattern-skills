---
name: ucp-go-test-design
lang: go
description: Спроектировать тесты Go-сервиса (net/http + chi) по UCP (коды GOTEST-*) — интеграционные на Postgres через testcontainers-go + http.DefaultClient, мок внешнего HTTP через httptest, Clock/IDGenerator через конструкторную DI, Outbox вместо Kafka/Redis.
when_to_use: После нового UseCase/Handler. Триггеры — «тесты для X», «integration-тест на команду Y», «написать тест на агрегат».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Проектирование тестов (Go / net/http + chi)

Ты пишешь тесты для Go-сервиса по `.claude/docs/backend/go/go-test-strategy/go-test-strategy-rules.md` (`GOTEST-*`).

## Зависимости

- **`.claude/docs/backend/go/go-test-strategy/go-test-strategy-rules.md`** — правила `GOTEST-*` (код-примеры включены).
- Спека (если есть) — сценарии из use case-ов (UC-N) и бизнес-правил (BR-N).
- Парные: `backend/go/go-test-strategy/go-test-strategy-rules.md` (структура сервиса), `backend/error-handling/go/error-handling-style-guide.md` (apperr.Kind + errors.As — как проверять коды ошибок), `backend/go/sqlc/sqlc-rules.md` (`R-SQLC-*` — репозиторий против Testcontainers), `backend/auth-patterns/go/auth-patterns-style-guide.md` (`AUTH-17`/`AUTH-19` — фейковый JWT, Idempotency-Key).

## Инструкции

1. **Прочти** `.claude/docs/backend/go/go-test-strategy/go-test-strategy-rules.md` (`GOTEST-*`). Коды в комментариях тестов НЕ цитируй; в комментарии над функцией — цитата BR/UC допустима (бизнес-описание).

2. **Определи слой** и назови его в начале ответа:
   - **Unit** (без инфраструктуры) — чистая логика агрегата/VO: `NewOrder(...)`, `order.Cancel()`, `assert.ErrorAs(t, err, &domainErr)` (`GOTEST-26`).
   - **Контроллер без БД** — `httptest.NewRecorder` + реальный chi-роутер + in-memory реализация интерфейса репозитория; Testcontainers не поднимаем (`GOTEST-27`).
   - **Интеграционный** — `httptest.NewServer(router)` + реальный PostgreSQL через testcontainers-go + `http.DefaultClient` (`GOTEST-1`).
   - **E2E** — build-tag `e2e`, настоящие Kafka/внешние сервисы, отдельный CI-этап, ≤ 10 тестов (`GOTEST-28`).

3. **Если инфраструктура тестов ещё не готова** — создай в пакете (`GOTEST-4..7`): `TestMain(m *testing.M)` с `postgres.Run` (testcontainers-go, образ `postgres:16-alpine`), применением миграций один раз, `m.Run()`, завершением контейнера через `defer`; пакетная переменная `testDSN`; `newTestServer(t *testing.T)` — собирает `sqlc.New(pool)` + все зависимости + chi-роутер + `httptest.NewServer` + `t.Cleanup(srv.Close)`. Kafka/go-redis — **не поднимать** (`GOTEST-X7`).

4. **`<Domain>DatabasePreparer`** (`GOTEST-11..14`) — над `pgxpool.Pool` напрямую (не через sqlc): `Clear(t)` вызывает `TRUNCATE ... CASCADE` в правильном порядке FK-зависимостей; fluent `Create*(t, ...)`/`Find*(t, ...)`. Схему не пересоздавать между тестами — только `TRUNCATE` (`GOTEST-X3`).

5. **Детерминизм** (`GOTEST-8..10`) — время и UUID в домене инжектируются через интерфейсы `Clock`/`IDGenerator`; в тесте — `fixedClock{at: time.Date(...)}` и `seqIDGenerator` (счётчик); сравниваем с ожидаемым значением из `fixedClock`, не с `time.Now()`.

6. **Каждый тест** — AAA (`// Arrange`, `// Act`, `// Assert`); имя `Test<Action>_<Condition>_<Expected>`; комментарий над функцией с кодом BR из спеки; `t.Parallel()` в интеграционных; `Clear(t)` в начале каждого теста (`GOTEST-15..18`).

7. **Покрытие:** на каждый UC — happy + альтернативы + ошибки; на каждый BR — отдельный тест; на каждое доменное событие — проверка Outbox-таблицы через `DatabasePreparer.FindOutboxEvents(t, "EVENT_TYPE")` (`GOTEST-19`); на каждый код ошибки — проверка статуса + декодированного `problem+json` (`status`/`code`).

8. **Авторизация** (`GOTEST-29..30`) — подменяем JWT-валидатор на `fakeAuthMiddleware(principal)`, который прокидывает фейковый `Principal` в контекст; тест обязан проверять `401`/`403` при неверной роли (`GOTEST-X11`); хелперы `AdminPrincipal()`/`CustomerPrincipal(id)` — в общем `testhelper`-пакете.

9. **Внешний HTTP** (`GOTEST-23..25`) — только если есть исходящие вызовы: `httptest.NewServer(http.HandlerFunc(...))` в самом тесте; stub проверяет входящий запрос (метод, заголовки, тело); base-url клиента переопределяется через конструктор; `t.Cleanup(stub.Close)`.

10. **Самопроверка** по чеклисту из `go-test-strategy-rules.md` §«Чеклист подключения к новому сервису» + предложи `ucp-go-test-review`.

## Антипаттерны, которые НЕ генерировать

- `time.Sleep`/polling-цикл/`testify/assert.Eventually` в тесте как способ «подождать» (`GOTEST-X1`); `time.Now()`/`uuid.New()` напрямую в домене вместо DI-интерфейса (`GOTEST-X2`/`GOTEST-X4`).
- `DROP TABLE`/пересоздание схемы между тестами (`GOTEST-X3`); Testcontainers Kafka/go-redis в базовом интеграционном тесте (`GOTEST-X7`).
- Мокать `Repository`-интерфейс через `testify/mock` в интеграционном тесте (`GOTEST-X9`) — `mock.Repository` допустим только в unit-тесте контроллера/Handler.
- Реальный Keycloak/JWKS в интеграционном тесте (`GOTEST-X10`); отключение auth-middleware полностью (`GOTEST-X11`).
- `ioutil.ReadAll` + `fmt.Println` вместо `t.Logf` (`GOTEST-X6`); `testify/mock` на HTTP-клиент вместо реального `httptest.NewServer` (`GOTEST-X8`).

После работы скилла — обязательно `ucp-go-test-review`.

$ARGUMENTS
