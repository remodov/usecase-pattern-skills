# Test Strategy — интеграционные тесты сервиса

Подход к интеграционным тестам в Java/Spring-сервисах. Каждое правило имеет код вида `TS-N` — скилл `ucp-test-design` цитирует эти коды в обзорах.

Базовый принцип (`TS-1`): **тест должен быть быстрым и детерминированным**. Если тест требует Kafka, Redis, нескольких контейнеров и `Awaitility` — это не интеграционный тест на бизнес-логику, а инфраструктурный smoke; их пишут отдельно и редко.

Основан на реальном паттерне из CSMS (`PlatformBaseIntegrationTest`).

---

## 1. Базовые правила

`TS-1` Интеграционный тест запускает **полный Spring-контекст + реальный PostgreSQL + ваш контроллер через HTTP**. Внешние HTTP-сервисы — WireMock или `@MockitoBean`. Kafka/Redis — заменяются на in-memory или вообще выключаются профилем.

`TS-2` **Все тесты синхронные.** Никаких `CompletableFuture.get()`, `Awaitility.await()`, `Thread.sleep`. Время и UUID — детерминированные через `@MockitoBean` (см. `TS-7`).

`TS-3` **Один тест — один сценарий.** AAA-структура: Arrange → Act → Assert. Не «проверить всё в одном».

---

## 2. Структура `BaseIntegrationTest`

`TS-4` На сервис заводится **один платформенный `BaseIntegrationTest`** + по одному **доменному base** на каждый Bounded Context. Доменный наследуется от платформенного либо повторяет его настройку и добавляет свои `DatabasePreparer`-ы.

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

    @MockitoBean
    protected DateTimeService dateTimeService;

    @MockitoBean
    protected UuidGenerator uuidGenerator;

    static {
        postgres.start();
    }
}
```

`TS-5` **`@ServiceConnection`** (Spring Boot 3.1+) сам прокидывает свойства в `spring.datasource.*`. Не пишем руками `@DynamicPropertySource` для PostgreSQL.

`TS-6` **`@TestInstance(Lifecycle.PER_CLASS)`** — экземпляр класса теста живёт всё время. Дорогой setup в `@BeforeAll` без `static`.

`TS-7` **Время и UUID — `@MockitoBean`.** В коде сервиса всё, что зовёт «сейчас» или «новый id», идёт через два бина: `DateTimeService` и `UuidGenerator`. В тесте они мокаются и возвращают предзаданные значения. Никаких `Instant.now()` или `UUID.randomUUID()` напрямую — иначе тест становится недетерминированным.

```java
given(dateTimeService.getCurrentDateTimeInUTC()).willReturn(now);
given(uuidGenerator.generate()).willReturn(orderId);
```

`TS-8` **`@Import(TestJwtConfiguration.class)`** даёт тесту фейковый JWT-validator + хелпер `TestHttpHeaders.withSuccessToken()` для подкладывания токена в запрос. Единый source-of-truth по тестовой авторизации.

---

## 3. `DatabasePreparer` — fluent setup БД

`TS-9` На каждый Bounded Context заводится свой `<Domain>DatabasePreparer` — `@Component`, обёртка над `DSLContext`, с методами в трёх группах:

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

`TS-10` **Не пересоздаём схему между тестами.** Только `DELETE` нужных таблиц — миллисекунды вместо секунд. Схема создаётся один раз при старте контекста — Liquibase накатывает changelog (`spring.liquibase.change-log: classpath:db/changelog-master.yaml`) автоматически в `@SpringBootTest`.

`TS-11` **Порядок методов внутри `prepare()` — порядок их вызова.** Если в БД есть FK — порядок очистки/создания должен это учитывать (FK последним создаём, первым чистим).

---

## 4. `TestObjectGenerator` — fluent builders сущностей

`TS-12` На каждую POJO-таблицу заводим builder с `with*` и `generate()`:

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

`TS-13` У генератора **разумные дефолты** (`UUID.randomUUID()`, текущее время с обнулёнными наносекундами). В тесте перезаписываем только то, что важно для сценария.

`TS-14` `withNano(0)` — обязательно при сравнении `OffsetDateTime` в БД (PostgreSQL `timestamp` хранит миллисекунды).

---

## 5. Структура одного теста

`TS-15` Тест extends `<Domain>BaseIntegrationTest`, инжектит `TestRestTemplate` и `DatabasePreparer`:

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

`TS-16` **Имена методов**: `<action>_when<Condition>_<expectedResult>` (csms-стиль) **или** длинное говорящее имя. В обоих случаях добавляем `@DisplayName` с цитированием BR-кода — это полезно при чтении отчёта.

`TS-17` HTTP-вызов через **`TestRestTemplate.exchange(...)`** — даёт точный контроль над методом, заголовками, телом. `MockMvc` оставляем для unit-тестов контроллера без БД.

`TS-18` **JWT — через `TestHttpHeaders.withSuccessToken()`** или специализированный (`withCustomerToken(customerId)`, `withSellerToken(sellerId)`). Не собираем токены руками в каждом тесте.

---

## 6. Kafka, Redis, async — по умолчанию НЕТ

`TS-19` **Не поднимаем Kafka в интеграционных тестах.** События остаются в Outbox-таблице — в тесте проверяем содержимое `outbox` через тот же `DatabasePreparer` или прямой `JdbcTemplate`/`DSLContext`:

```java
var outboxRows = dsl.selectFrom(OUTBOX_ENTITY_CHANGES)
    .where(OUTBOX_ENTITY_CHANGES.AGGREGATE_ID.eq(orderId))
    .fetch();
assertThat(outboxRows).extracting(r -> r.getEventType())
    .containsExactly("OrderConfirmed");
```

`TS-20` **Redis тоже не поднимаем.** Профиль `integration-test` ставит `spring.cache.type=none`.

`TS-21` Если в обработчике есть **подписка на Kafka** (idempotent consumer) — тестируем handler напрямую как Spring-бин: `eventHandler.handle(testEvent)`. Без `EmbeddedKafka`.

`TS-22` Async/Saga (`@TransactionalEventListener(AFTER_COMMIT)`) — переводится в синхрон через профиль теста или ручной commit + вызов handler-а.

---

## 7. Внешние HTTP — WireMock

`TS-23` Если сервис вызывает внешний REST (платёжный шлюз, каталог, логистика) — поднимаем **WireMock** в `BaseIntegrationTest`:

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

`TS-24` **Стабы пишем в самом тесте**, не в общих `mappings/*.json`. В тесте видно, на что он опирается.

```java
catalog.stubFor(get("/api/v1/products/" + productId)
    .willReturn(okJson("""
        { "id": "%s", "price": "100.00", "currency": "RUB" }
        """.formatted(productId))));
```

`TS-25` Если внешний клиент по факту — `@FeignClient` с `@MockitoBean`, можно обойтись без WireMock и мокнуть его напрямую. Но **по умолчанию WireMock предпочтительнее** — он проверяет ещё и сериализацию HTTP, заголовки, retry и timeout.

---

## 8. Что НЕ покрывается интеграционными тестами

`TS-26` Чистая бизнес-логика агрегата — **unit-тест без Spring**. Просто `new Order(...)`, `order.confirm()`. Самые быстрые и многочисленные.

`TS-27` Контроллер + сериализация JSON, без БД — `@WebMvcTest` + `MockMvc`.

`TS-28` E2E через настоящие Kafka/внешние сервисы — отдельная группа `@Tag("e2e")`, отдельный CI-этап, ≤ 5–10 тестов на сервис.

---

## 9. Чек-лист обзора

| Группа | Правила |
|---|---|
| Платформенный/доменный base | `TS-4`–`TS-8` |
| `DatabasePreparer` | `TS-9`–`TS-11` |
| `TestObjectGenerator` | `TS-12`–`TS-14` |
| Структура теста | `TS-1`–`TS-3`, `TS-15`–`TS-18` |
| Kafka/Redis/async | `TS-19`–`TS-22` |
| Внешние HTTP | `TS-23`–`TS-25` |
| Что НЕ интеграционные | `TS-26`–`TS-28` |
