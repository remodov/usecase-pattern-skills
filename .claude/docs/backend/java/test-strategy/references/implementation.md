# Test Strategy — реализация

Свод правил интеграционных и unit-тестов в Java/Spring-сервисах команды UCP. Каждое правило идентифицируется кодом `TS-N` — скилл `ucp-test-design` цитирует эти коды в выдаче и при review-обзорах.

Базовый принцип (`test-strategy/integration-test-shape`): **тест должен быть быстрым и детерминированным**. Если тест требует Kafka, Redis, нескольких контейнеров и `Awaitility` — это не интеграционный тест на бизнес-логику, а инфраструктурный smoke; их пишут отдельно и редко.

Основан на реальном паттерне из CSMS (`PlatformBaseIntegrationTest`).

Связанные стандарты:
- `R-PATT-*` (Use Case Pattern) — каждый UseCase / Handler покрывается интеграционным тестом, AAA-структурой.
- `R-AGG-*` (DDD tactical) — unit-тесты на инварианты агрегатов отдельно от integration.
- `jooq/repository-integration-tested` (`jooq/repository-integration-tested`) — каждый репозиторий покрыт интеграционным тестом против Testcontainers PostgreSQL, без mock'ов `DSLContext`.
- `R-RES-OAS-*` (Resilience) — WireMock для outbound HTTP-стабов.
- `R-KFK-CONS-*` (Kafka) — listener тесты с in-memory dispatcher или Testcontainers Kafka.
- `auth-patterns/money-commands-need-idempotency-key` (`auth-patterns/money-commands-need-idempotency-key`) — Idempotency-Key тесты для money-операций.

---

## 1. Базовые правила

`test-strategy/integration-test-shape` Интеграционный тест запускает **полный Spring-контекст + реальный PostgreSQL + ваш контроллер через HTTP**. Внешние HTTP-сервисы — WireMock или `@MockitoBean`. Kafka/Redis — заменяются на in-memory или вообще выключаются профилем.

`test-strategy/tests-are-synchronous-and-deterministic` **Все тесты синхронные.** Никаких `CompletableFuture.get()`, `Awaitility.await()`, `Thread.sleep`. Время — детерминированное: фиксация `Clock` источника времени либо `@MockitoBean` на его бине, по варианту проекта (см. `spring-bootstrap/time-source-is-single-and-swappable`).

`test-strategy/one-test-one-scenario` **Один тест — один сценарий.** AAA-структура: Arrange → Act → Assert. Не «проверить всё в одном».

---

## 2. Структура `BaseIntegrationTest`

`test-strategy/base-classes-layered` На сервис заводится **один платформенный `BaseIntegrationTest`** + по одному **доменному base** на каждый Bounded Context. Доменный наследуется от платформенного либо повторяет его настройку и добавляет свои `DatabasePreparer`-ы.

```java
@Import(TestJwtConfiguration.class)
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles(INTEGRATION_TEST_SPRING_PROFILE)
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
public abstract class PlatformBaseIntegrationTest {

    @ServiceConnection
    protected static final PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>("postgres:16-alpine");

    static {
        postgres.start();
    }

    @AfterEach
    void resetClock() {
        DateTimeUtil.resetClock();
    }

    protected void fixClock(OffsetDateTime moment) {
        DateTimeUtil.setClock(Clock.fixed(moment.toInstant(), ZoneOffset.UTC));
    }
}
```

Так выглядит база при статическом источнике времени (вариант A из `spring-bootstrap`). При варианте B вместо `fixClock`/`resetClock` — поля `@MockitoBean DateTimeService dateTimeService` и `@MockitoBean UuidGenerator uuidGenerator`.

`test-strategy/container-connection-is-automatic` **`@ServiceConnection`** (Spring Boot 3.1+) сам прокидывает свойства в `spring.datasource.*`. Не пишем руками `@DynamicPropertySource` для PostgreSQL.

`test-strategy/expensive-setup-runs-once` **`@TestInstance(Lifecycle.PER_CLASS)`** — экземпляр класса теста живёт всё время. Дорогой setup в `@BeforeAll` без `static`.

`test-strategy/tests-are-synchronous-and-deterministic` **Время — предзаданное, по варианту источника в проекте.** В коде сервиса всё, что зовёт «сейчас», идёт через единственный источник времени (`spring-bootstrap/time-source-is-single-and-swappable`); никаких `Instant.now()` напрямую — иначе тест становится недетерминированным.

- Вариант A, статический `Clock`: `fixClock(now)` в начале теста, сброс — `@AfterEach` базового класса. Идентификаторы чеканят фабрики через `UUID.randomUUID()`; тест их не фиксирует, а читает обратно из ответа или БД.
- Вариант B, бины: `@MockitoBean` возвращают предзаданные значения:

```java
given(dateTimeService.now()).willReturn(now);
given(uuidGenerator.generate()).willReturn(orderId);
```

`test-strategy/test-auth-single-source` **`@Import(TestJwtConfiguration.class)`** даёт тесту фейковый JWT-validator + хелпер `TestHttpHeaders.withSuccessToken()` для подкладывания токена в запрос. Единый source-of-truth по тестовой авторизации.

---

## 3. `DatabasePreparer` — fluent setup БД

`test-strategy/database-preparer-per-context` На каждый Bounded Context заводится свой `<Domain>DatabasePreparer` — `@Component`, обёртка над `DSLContext`, с методами в трёх группах:

- **`clear*()`** — очистка таблиц.
- **`create*(...)`** — вставка тестовых данных.
- **`prepare()`** — запуск всей очереди в правильном порядке.

```java
@Component
public class OrderDatabasePreparer {
    private final DSLContext dsl;
    private final List<Runnable> preparers = new ArrayList<>();

    public OrderDatabasePreparer clearOrders() {
        preparers.add(() -> dsl.deleteFrom(Orders.ORDERS).execute());
        return this;
    }

    public OrderDatabasePreparer createOrder(OrdersPojo order) {
        preparers.add(() -> dsl.insertInto(Orders.ORDERS).set(dsl.newRecord(Orders.ORDERS, order)).execute());
        return this;
    }

    public void prepare() {
        preparers.forEach(Runnable::run);
        preparers.clear();
    }
}
```

В тесте:

```java
@BeforeEach
void setUp() {
    databasePreparer
        .clearOrderItems()
        .clearOrders()
        .clearOutbox()
        .createOrder(order)
        .prepare();
}
```

`test-strategy/schema-once-data-cleaned` **Не пересоздаём схему между тестами.** Только `DELETE` нужных таблиц — миллисекунды вместо секунд. Схема создаётся один раз при старте контекста — Liquibase накатывает changelog (`spring.liquibase.change-log: classpath:db/changelog-master.yaml`) автоматически в `@SpringBootTest`.

`test-strategy/database-preparer-per-context` **Порядок методов внутри `prepare()` — порядок их вызова.** Если в БД есть FK — порядок очистки/создания должен это учитывать (FK последним создаём, первым чистим).

---

## 4. `TestObjectGenerator` — fluent builders сущностей

`test-strategy/builders-with-defaults` На каждую POJO-таблицу заводим builder с `with*` и `generate()`:

```java
public class OrderTestObjectGenerator {
    private UUID id = UUID.randomUUID();
    private OrderStatus status = OrderStatus.DRAFT;
    private UUID customerId = UUID.randomUUID();
    private OffsetDateTime createdAt = OffsetDateTime.now().withNano(0);

    public OrderTestObjectGenerator withId(UUID id) { this.id = id; return this; }
    public OrderTestObjectGenerator withStatus(OrderStatus s) { this.status = s; return this; }
    public OrderTestObjectGenerator withCreatedAt(OffsetDateTime t) { this.createdAt = t; return this; }

    public OrdersPojo generate() {
        var pojo = new OrdersPojo();
        pojo.setId(id);
        pojo.setStatus(status);
        pojo.setCustomerId(customerId);
        pojo.setCreatedAt(createdAt);
        return pojo;
    }
}
```

`test-strategy/builders-with-defaults` У генератора **разумные дефолты** (`UUID.randomUUID()`, текущее время с обнулёнными наносекундами). В тесте перезаписываем только то, что важно для сценария.

`test-strategy/builders-with-defaults` `withNano(0)` — обязательно при сравнении `OffsetDateTime` в БД: `timestamptz` хранит микросекунды, а JDK на Linux даёт наносекунды; генераторы обнуляют дробную часть, источник времени сервиса усекает до микросекунд — иначе прочитанное из БД не равно записанному.

---

## 5. Структура одного теста

`test-strategy/test-uses-http-client` Тест extends `<Domain>BaseIntegrationTest`, инжектит `TestRestTemplate` и `DatabasePreparer`:

```java
public class CreateOrderEndpointIntegrationTest extends OrderBaseIntegrationTest {
    private static final String BASE_URL = "/v1/orders";

    @Autowired private TestRestTemplate restTemplate;
    @Autowired private OrderDatabasePreparer databasePreparer;

    @BeforeEach
    void setUp() {
        databasePreparer.clearOrderItems().clearOrders().clearOutbox().prepare();
    }

    @Test
    @DisplayName("BR-002: confirm fails when reservation failed")
    void confirmOrder_whenReservationFailed_returns409() {
        // Arrange
        var orderId = UUID.randomUUID();
        var now = OffsetDateTime.now().withNano(0);
        given(uuidGenerator.generate()).willReturn(orderId);
        given(dateTimeService.getCurrentDateTimeInUTC()).willReturn(now);

        var draft = new OrderTestObjectGenerator()
            .withId(orderId).withStatus(OrderStatus.DRAFT).withCreatedAt(now).generate();
        databasePreparer.createOrder(draft).prepare();

        // Act
        var response = restTemplate.exchange(
            BASE_URL + "/" + orderId + "/confirm",
            HttpMethod.POST,
            new HttpEntity<>(TestHttpHeaders.withSuccessToken()),
            ProblemDetailJsonBean.class);

        // Assert
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(response.getBody().getCode()).isEqualTo("OUT_OF_STOCK");
    }
}
```

`test-strategy/test-name-states-scenario` **Имена методов**: `<action>_when<Condition>_<expectedResult>` (csms-стиль) **или** длинное говорящее имя. В обоих случаях добавляем `@DisplayName` с цитированием BR-кода — это полезно при чтении отчёта.

`test-strategy/test-uses-http-client` HTTP-вызов через **`TestRestTemplate.exchange(...)`** — даёт точный контроль над методом, заголовками, телом. `MockMvc` оставляем для unit-тестов контроллера без БД.

`test-strategy/test-auth-single-source` **JWT — через `TestHttpHeaders.withSuccessToken()`** или специализированный (`withCustomerToken(customerId)`, `withSellerToken(sellerId)`). Не собираем токены руками в каждом тесте.

---

## 6. Kafka, Redis, async — по умолчанию НЕТ

`test-strategy/no-broker-or-cache-in-integration-tests` **Не поднимаем Kafka в интеграционных тестах.** События остаются в Outbox-таблице — в тесте проверяем содержимое `outbox` через тот же `DatabasePreparer` или прямой `JdbcTemplate`/`DSLContext`:

```java
var outboxRows = dsl.selectFrom(OUTBOX_ENTITY_CHANGES)
    .where(OUTBOX_ENTITY_CHANGES.AGGREGATE_ID.eq(orderId))
    .fetch();
assertThat(outboxRows).extracting(r -> r.getEventType())
    .containsExactly("OrderConfirmed");
```

`test-strategy/no-broker-or-cache-in-integration-tests` **Redis тоже не поднимаем.** Профиль `integration-test` ставит `spring.cache.type=none`.

`test-strategy/no-broker-or-cache-in-integration-tests` Если в обработчике есть **подписка на Kafka** (idempotent consumer) — тестируем handler напрямую как Spring-бин: `eventHandler.handle(testEvent)`. Без `EmbeddedKafka`.

`test-strategy/async-effects-made-synchronous` Async/Saga (`@TransactionalEventListener(AFTER_COMMIT)`) — переводится в синхрон через профиль теста или ручной commit + вызов handler-а.

---

## 7. Внешние HTTP — WireMock

`test-strategy/external-calls-via-stub-server` Если сервис вызывает внешний REST (платёжный шлюз, каталог, логистика) — поднимаем **WireMock** в `BaseIntegrationTest`:

```java
@RegisterExtension
static WireMockExtension catalog = WireMockExtension.newInstance()
    .options(wireMockConfig().dynamicPort())
    .build();

@DynamicPropertySource
static void wireMockProps(DynamicPropertyRegistry r) {
    r.add("clients.catalog.base-url", catalog::baseUrl);
}
```

`test-strategy/external-calls-via-stub-server` **Стабы пишем в самом тесте**, не в общих `mappings/*.json`. В тесте видно, на что он опирается.

```java
catalog.stubFor(get("/api/v1/products/" + productId)
    .willReturn(okJson("""
        { "id": "%s", "price": "100.00", "currency": "RUB" }
        """.formatted(productId))));
```

`test-strategy/external-calls-via-stub-server` Если внешний клиент по факту — `@FeignClient` с `@MockitoBean`, можно обойтись без WireMock и мокнуть его напрямую. Но **по умолчанию WireMock предпочтительнее** — он проверяет ещё и сериализацию HTTP, заголовки, retry и timeout.

---

## 8. Что НЕ покрывается интеграционными тестами

`test-strategy/test-layers-separated` Чистая бизнес-логика агрегата — **unit-тест без Spring**. Просто `new Order(...)`, `order.confirm()`. Самые быстрые и многочисленные.

`test-strategy/test-layers-separated` Контроллер + сериализация JSON, без БД — `@WebMvcTest` + `MockMvc`.

`test-strategy/test-layers-separated` E2E через настоящие Kafka/внешние сервисы — отдельная группа `@Tag("e2e")`, отдельный CI-этап, ≤ 5–10 тестов на сервис.

---

## 9. Чек-лист обзора

| Группа | Правила |
|---|---|
| Платформенный/доменный base | `test-strategy/base-classes-layered`–`test-strategy/test-auth-single-source` |
| `DatabasePreparer` | `test-strategy/database-preparer-per-context`–`test-strategy/database-preparer-per-context` |
| `TestObjectGenerator` | `test-strategy/builders-with-defaults`–`test-strategy/builders-with-defaults` |
| Структура теста | `test-strategy/integration-test-shape`–`test-strategy/one-test-one-scenario`, `test-strategy/test-uses-http-client`–`test-strategy/test-auth-single-source` |
| Kafka/Redis/async | `test-strategy/no-broker-or-cache-in-integration-tests`–`test-strategy/async-effects-made-synchronous` |
| Внешние HTTP | `test-strategy/external-calls-via-stub-server`–`test-strategy/external-calls-via-stub-server` |
| Что НЕ интеграционные | `test-strategy/test-layers-separated`–`test-strategy/test-layers-separated` |
