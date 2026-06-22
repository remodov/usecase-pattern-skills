# Go Test Strategy — индекс правил (testing + testify + testcontainers-go)

> **Что это.** Стратегия тестов Go-сервиса по UCP: интеграционные на реальном Postgres через
> Testcontainers, внешний HTTP замокан через `net/http/httptest`, Kafka/Redis — выключены профилем.
> Языко-специфичный concern (аналог Java `TS-*` / Python `PYTS-*`) — **только Go**, своя пара кодов `GOTEST-*`.
> Скиллы читают этот файл; код-примеры включены (отдельного style-guide нет).
> PostgreSQL-правила (типы/индексы) — `pg-*-rules.md`. Ошибки — значения (`apperr.Kind + errors.As + %w`),
> как в `error-handling/go/error-handling-style-guide.md`.
> Коды: `GOTEST-<N>` — обязательно (MUST), `GOTEST-X<N>` — антипаттерн (MUST NOT).
> Связанные: `R-PATT-*`/`R-HND-*` (UseCase покрыт интеграционным), `R-AGG-*` (unit на инварианты),
> `R-SQLC-*` (репозиторий против Testcontainers), `R-RES-*` (мок внешнего HTTP), `AUTH-19` (Idempotency-Key).

Базовый принцип (`GOTEST-1`): **тест быстрый и детерминированный**. Если тест требует Kafka/Redis/несколько
контейнеров и polling-ожидание — это инфраструктурный smoke, не тест на бизнес-логику.

---

## 1. Базовые правила

**MUST:**
- **GOTEST-1.** Интеграционный тест — `net/http/httptest.NewServer(router)` + реальный PostgreSQL (Testcontainers) + HTTP-вызов через `http.DefaultClient`; внешний HTTP — `httptest.NewServer` с заглушкой (раздел 7); Kafka/Redis — выключены build-tag'ом `integration` или env-профилем.
- **GOTEST-2.** Тесты детерминированы: никаких `time.Sleep`/polling-циклов/`Eventually`-ожиданий ради «дождаться»; время и UUID — фиксированы через интерфейсы `Clock`/`IDGenerator` (раздел 3).
- **GOTEST-3.** Один тест — один сценарий, AAA-структура (`// Arrange`, `// Act`, `// Assert`).

**MUST NOT:**
- **GOTEST-X1.** `time.Sleep`/`testify/assert.Eventually` или polling-цикл в тесте как способ «подождать» — признак недетерминированного дизайна.
- **GOTEST-X2.** Вызов `time.Now()`/`uuid.New()` напрямую в доменном коде вместо зависимости-интерфейса — нарушает детерминизм теста.

```go
// GOTEST-1: запуск интеграционного теста
func TestCreateOrder_Success(t *testing.T) {
    t.Parallel()
    srv, prep := newTestServer(t) // раздел 2

    // Arrange
    prep.Clear(t).CreateCustomer(t, customerID)

    // Act
    resp, err := http.Post(srv.URL+"/orders", "application/json",
        strings.NewReader(`{"customerId":"c1","amount":100}`))
    require.NoError(t, err)

    // Assert
    assert.Equal(t, http.StatusCreated, resp.StatusCode)
}
```

---

## 2. Инфраструктура теста (TestMain + контейнер)

**MUST:**
- **GOTEST-4.** Один `TestMain(m *testing.M)` на пакет — поднимает `PostgresContainer` (testcontainers-go), применяет миграции (sqlc-generated schema или goose/migrate), запускает `m.Run()`, завершает контейнер явным вызовом после `m.Run()` (не через `defer` — `defer` не выполняется до `os.Exit`).
- **GOTEST-5.** DSN из контейнера прокидывается через пакетную переменную или `sync.Once`-синглтон; не хардкодится строка подключения в тесте.
- **GOTEST-6.** Схема разворачивается один раз при старте (`TestMain`), не пересоздаётся между тестами — только `TRUNCATE` нужных таблиц (мс vs секунды).
- **GOTEST-7.** `newTestServer(t *testing.T)` — вспомогательная функция: собирает `sqlc.New(pool)` + все зависимости + chi-роутер + `httptest.NewServer`; регистрирует `t.Cleanup(srv.Close)`.

**MUST NOT:**
- **GOTEST-X3.** `DROP TABLE`/пересоздание схемы между тестами — медленно и маскирует миграционные ошибки.

```go
// GOTEST-4 / GOTEST-5: TestMain
var testDSN string

func TestMain(m *testing.M) {
    ctx := context.Background()
    pg, err := postgres.Run(ctx, "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(wait.ForListeningPort("5432/tcp")),
    )
    if err != nil {
        log.Fatalf("start postgres: %v", err)
    }
    testDSN, _ = pg.ConnectionString(ctx, "sslmode=disable")
    applyMigrations(testDSN) // goose / migrate; один раз

    code := m.Run()
    _ = pg.Terminate(ctx)
    os.Exit(code)
}

// GOTEST-7: newTestServer
func newTestServer(t *testing.T) (*httptest.Server, *OrderDatabasePreparer) {
    t.Helper()
    pool, _ := pgxpool.New(context.Background(), testDSN)
    t.Cleanup(pool.Close)

    q := db.New(pool)
    repo := order.NewRepository(q)
    clock := &fixedClock{at: time.Date(2024, 1, 15, 10, 0, 0, 0, time.UTC)}
    ids := &seqIDGenerator{}
    svc := order.NewService(repo, clock, ids)

    r := chi.NewRouter()
    orderhttp.Mount(r, svc)
    srv := httptest.NewServer(r)
    t.Cleanup(srv.Close)

    return srv, &OrderDatabasePreparer{pool: pool}
}
```

---

## 3. Детерминизм — Clock и IDGenerator

**MUST:**
- **GOTEST-8.** Время в домене инжектируется через интерфейс `Clock`; в тесте — `fixedClock` с предзаданным значением; `time.Now()` в домене запрещён.
- **GOTEST-9.** UUID/ID инжектируется через `IDGenerator`; в тесте — `seqIDGenerator` (счётчик) или `staticIDGenerator` (фиксированная строка).
- **GOTEST-10.** Тест сравнивает временны́е поля с ожидаемым значением из `fixedClock`, не с `time.Now()`.

**MUST NOT:**
- **GOTEST-X4.** `uuid.New()`/`time.Now()` вызываются прямо в `Handler`/`Service`/`Aggregate` без инжекции — делает тест недетерминированным.

```go
// GOTEST-8: Clock-интерфейс
type Clock interface{ Now() time.Time }

type fixedClock struct{ at time.Time }
func (c *fixedClock) Now() time.Time { return c.at }

// GOTEST-9: IDGenerator-интерфейс
type IDGenerator interface{ Next() string }

type seqIDGenerator struct{ n atomic.Int64 }
func (g *seqIDGenerator) Next() string {
    return fmt.Sprintf("id-%d", g.n.Add(1))
}

// GOTEST-10: сравнение времени в тесте
assert.Equal(t, clock.at.UTC(), gotOrder.CreatedAt.UTC())
```

---

## 4. DatabasePreparer — fluent setup БД

**MUST:**
- **GOTEST-11.** На каждый Bounded Context — свой `<Domain>DatabasePreparer` с `pgxpool.Pool`; методы `Clear(t)`/`Create*(t, ...)`/`Find*(t, ...)`.
- **GOTEST-12.** `Clear(t)` вызывает `TRUNCATE ... CASCADE` нужных таблиц в правильном порядке (FK: зависимые сначала); вызывается в начале каждого теста.
- **GOTEST-13.** Порядок `Create*`-методов отражает FK-зависимости (родительскую запись создаём раньше дочерней).
- **GOTEST-14.** Прямые SQL-запросы в препарере — через `pgx` (не через sqlc-генерацию, чтобы тест не зависел от доменного слоя); допустимы raw-строки, читаемые и минимальные.

**MUST NOT:**
- **GOTEST-X5.** Общий `TRUNCATE` всех таблиц в произвольном порядке — нарушает FK-ограничения; порядок важен.

```go
// GOTEST-11 / GOTEST-12: OrderDatabasePreparer
type OrderDatabasePreparer struct{ pool *pgxpool.Pool }

func (p *OrderDatabasePreparer) Clear(t *testing.T) *OrderDatabasePreparer {
    t.Helper()
    _, err := p.pool.Exec(context.Background(),
        "TRUNCATE order_items, orders, customers CASCADE")
    require.NoError(t, err)
    return p
}

func (p *OrderDatabasePreparer) CreateCustomer(t *testing.T, id string) *OrderDatabasePreparer {
    t.Helper()
    _, err := p.pool.Exec(context.Background(),
        "INSERT INTO customers(id, name) VALUES($1, $2)", id, "Test Customer")
    require.NoError(t, err)
    return p
}
```

---

## 5. Структура одного теста

**MUST:**
- **GOTEST-15.** Имена тестов: `Test<Action>_<Condition>_<Expected>` (Go-конвенция PascalCase), docstring-комментарий с кодом BR из спеки.
- **GOTEST-16.** Утверждения — через `testify/require` (fatal on fail) для setup-шагов и `testify/assert` (continue) для прочих; `t.Fatal` напрямую — только в `TestMain`.
- **GOTEST-17.** HTTP-запрос из теста — через `http.DefaultClient`; тело запроса и ответа — строгий контроль (`require.Equal` на статус; `json.Unmarshal` + assert на поля).
- **GOTEST-18.** Интеграционные тесты, работающие с общей БД, **не используют** `t.Parallel()` вместе с `TRUNCATE CASCADE` — параллельный `TRUNCATE` из двух тестов образует гонку данных. Изоляция — через транзакцию на тест: `tx, _ := pool.Begin(ctx)` в начале, `t.Cleanup(func(){ tx.Rollback(ctx) })` в конце; каждый тест видит только свои строки и не затрагивает соседей. Если транзакционная изоляция неприменима (DDL, `TRUNCATE` внутри теста) — `t.Parallel()` убирается, тесты идут последовательно.

**MUST NOT:**
- **GOTEST-X6.** `ioutil.ReadAll` (депрецирован с Go 1.16) вместо `io.ReadAll`; `fmt.Println` для отладки в тесте без `t.Logf` — не виден при `go test -v`-прогоне; всегда `io.ReadAll` и `t.Logf`/`t.Errorf`.

```go
// GOTEST-15: имя + BR-ссылка
// TestCancelOrder_WhenAlreadyCancelled_Returns422 проверяет BR-ORDER-7:
// нельзя отменить заказ в статусе CANCELLED.
func TestCancelOrder_WhenAlreadyCancelled_Returns422(t *testing.T) {
    t.Parallel()
    srv, prep := newTestServer(t)
    prep.Clear(t).CreateCustomer(t, "c1").CreateOrder(t, "o1", "c1", "CANCELLED")

    req, _ := http.NewRequest(http.MethodDelete, srv.URL+"/orders/o1", nil)
    resp, err := http.DefaultClient.Do(req)
    require.NoError(t, err)
    defer resp.Body.Close()

    // GOTEST-16: require для критичных, assert для остальных
    require.Equal(t, http.StatusUnprocessableEntity, resp.StatusCode)

    var body map[string]any
    require.NoError(t, json.NewDecoder(resp.Body).Decode(&body))
    assert.Equal(t, 422, int(body["status"].(float64)))
}
```

---

## 6. Kafka, Redis, async — по умолчанию НЕТ

**MUST:**
- **GOTEST-19.** Не поднимаем `kafka-go` в интеграционных — события в Outbox-таблице; проверяем содержимое через `DatabasePreparer.FindOutboxEvents(t, ...)`.
- **GOTEST-20.** Redis не поднимаем — профиль `integration-test` или build-tag подменяет `cache.Client` на `NoopCache`.
- **GOTEST-21.** Idempotent consumer тестируем как объект: `handler.Handle(ctx, testMsg)` напрямую, без брокера.
- **GOTEST-22.** Outbox-relay/async-воркер — вызываем синхронно в тесте: `relay.ProcessPending(ctx)`, не ждём фонового тика.

**MUST NOT:**
- **GOTEST-X7.** Testcontainers Kafka/Redis в базовом интеграционном тесте — раздувает время, превращает в smoke.

```go
// GOTEST-19: проверка Outbox вместо Kafka
func TestCreateOrder_PublishesToOutbox(t *testing.T) {
    t.Parallel()
    srv, prep := newTestServer(t)
    prep.Clear(t).CreateCustomer(t, "c1")

    resp, _ := http.Post(srv.URL+"/orders", "application/json",
        strings.NewReader(`{"customerId":"c1","amount":100}`))
    require.Equal(t, http.StatusCreated, resp.StatusCode)

    events := prep.FindOutboxEvents(t, "ORDER_CREATED")
    require.Len(t, events, 1)
    assert.Equal(t, "c1", events[0].Payload["customerId"])
}
```

---

## 7. Внешние HTTP — мок через httptest

**MUST:**
- **GOTEST-23.** Внешний REST (платёж, каталог, логистика) — `httptest.NewServer(handler)` в тесте; base-url клиента переопределяется через конструктор/опцию; регистрируем `t.Cleanup(stub.Close)`.
- **GOTEST-24.** Заглушку (stub) пишем в самом тесте — видно, на что тест полагается; не выносим в глобальные фикстуры.
- **GOTEST-25.** Заглушка проверяет входящий запрос (заголовки, метод, тело) через `r.Header.Get`/`io.ReadAll + assert` внутри своего `http.HandlerFunc` — тест спецификации клиента, не только ответа.

**MUST NOT:**
- **GOTEST-X8.** Мокать интерфейс HTTP-клиента через `testify/mock` вместо реального HTTP — теряем проверку сериализации, заголовков, retry и timeout.

```go
// GOTEST-23 / GOTEST-24 / GOTEST-25: httptest-заглушка
func TestCreateOrder_CallsPaymentGateway(t *testing.T) {
    t.Parallel()

    // GOTEST-24: заглушка прямо в тесте
    paymentStub := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        // GOTEST-25: проверяем входящий запрос
        assert.Equal(t, http.MethodPost, r.Method)
        assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

        body, _ := io.ReadAll(r.Body)
        var req map[string]any
        _ = json.Unmarshal(body, &req)
        assert.Equal(t, float64(100), req["amount"])

        w.WriteHeader(http.StatusOK)
        w.Write([]byte(`{"transactionId":"txn-1"}`))
    }))
    t.Cleanup(paymentStub.Close)

    // GOTEST-23: подменяем base-url клиента
    srv, prep := newTestServerWithPayment(t, paymentStub.URL)
    prep.Clear(t).CreateCustomer(t, "c1")

    resp, _ := http.Post(srv.URL+"/orders", "application/json",
        strings.NewReader(`{"customerId":"c1","amount":100}`))
    require.Equal(t, http.StatusCreated, resp.StatusCode)
}
```

---

## 8. Пирамида тестов — что чем покрывать

**MUST:**
- **GOTEST-26.** Чистая доменная логика агрегата — unit без инфраструктуры: `order := NewOrder(...)`, `err := order.Cancel()`, `assert.ErrorAs(t, err, &domainErr)`.
- **GOTEST-27.** Контроллер + сериализация без БД — `httptest.NewRecorder` + реальный chi-роутер + мок репозитория на in-memory реализацию интерфейса; не поднимаем Testcontainers.
- **GOTEST-28.** E2E через настоящие Kafka/внешние сервисы — build-tag `e2e`, отдельный CI-этап, ≤ 5–10 тестов на сервис.

**MUST NOT:**
- **GOTEST-X9.** Мокать `Repository`-интерфейс через `testify/mock` в интеграционном тесте — он проверяет реальный путь через БД; `mock.Repository` допустим **только** в unit-тесте контроллера/Handler.
- **GOTEST-X10.** Реальный Keycloak/JWKS-сервер в интеграционном тесте — только `testify`-авторизованный stub или фейковый JWT без подписи (`AUTH-17`).

```go
// GOTEST-26: unit на агрегат
func TestOrder_Cancel_WhenAlreadyCancelled_ReturnsError(t *testing.T) {
    order := &Order{ID: "o1", Status: StatusCancelled}
    err := order.Cancel()
    var domainErr *AlreadyCancelledError
    assert.ErrorAs(t, err, &domainErr)
}

// GOTEST-27: unit на контроллер (без БД, GOTEST-X9 — mock допустим здесь)
func TestOrderHandler_GetOrder_WhenNotFound_Returns404(t *testing.T) {
    repo := &inMemoryOrderRepo{} // простая in-memory реализация интерфейса
    svc := order.NewService(repo, &fixedClock{}, &seqIDGenerator{})

    r := chi.NewRouter()
    orderhttp.Mount(r, svc)

    w := httptest.NewRecorder()
    req := httptest.NewRequest(http.MethodGet, "/orders/nonexistent", nil)
    r.ServeHTTP(w, req)

    assert.Equal(t, http.StatusNotFound, w.Code)
}
```

---

## 9. Авторизация в тестах

**MUST:**
- **GOTEST-29.** JWT-валидатор в тестовом роутере — подменяется на `fakeAuthMiddleware(role)`, который прокидывает фейковый `Principal` в контекст; реальный JWKS не поднимаем.
- **GOTEST-30.** Хелперы авторизации (`withRole(t, "admin")`/`withCustomer(t, id)`) — единый source-of-truth в `testhelper` пакете; не дублируем сборку заголовков в каждом тесте.

**MUST NOT:**
- **GOTEST-X11.** Отключать auth-middleware полностью в интеграционном тесте — тест должен проверять, что `403`/`401` возвращается при неверной роли; отключение маскирует баги авторизации.

```go
// GOTEST-29 / GOTEST-30: fakeAuthMiddleware + хелперы
func fakeAuthMiddleware(principal Principal) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            ctx := auth.WithPrincipal(r.Context(), principal)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

// testhelper/auth.go
func AdminPrincipal() Principal { return Principal{ID: "admin-1", Role: "admin"} }
func CustomerPrincipal(id string) Principal { return Principal{ID: id, Role: "customer"} }
```

---

## Чеклист подключения к новому сервису (Go / net/http + chi)

- [ ] `TestMain` с `postgres.Run` (testcontainers-go) + миграции один раз при старте
- [ ] `testDSN` или пакетная переменная — без хардкода строки подключения в тестах
- [ ] `newTestServer(t)` — собирает роутер + sqlc + все зависимости + `httptest.NewServer`
- [ ] `Clock`/`IDGenerator` — интерфейсы в домене, `fixedClock`/`seqIDGenerator` в тестах
- [ ] `<Domain>DatabasePreparer` с `Clear(t)` и fluent `Create*(t, ...)` на каждый BC
- [ ] `TRUNCATE ... CASCADE` в правильном порядке (FK-зависимые — первыми)
- [ ] Внешние HTTP — `httptest.NewServer` с явным `t.Cleanup`; stub проверяет входящий запрос
- [ ] Kafka/Redis — отключены build-tag'ом или env; события — в Outbox-таблице
- [ ] Unit-тесты агрегата — без инфраструктуры; unit-тесты контроллера — `httptest.NewRecorder`
- [ ] E2E — build-tag `e2e`, отдельный CI-этап, ≤ 10 тестов
- [ ] Auth-middleware — `fakeAuthMiddleware` с реальной проверкой роли; тест 403/401 обязателен
- [ ] Интеграционные тесты — изоляция через транзакцию (`tx.Rollback` в `t.Cleanup`); `t.Parallel()` только при транзакционной изоляции, иначе последовательно
- [ ] `require.NoError`/`require.Equal` для критичных шагов; `assert.*` для assertion-блока
- [ ] Имена тестов `Test<Action>_<Condition>_<Expected>`; комментарий с кодом BR из спеки
