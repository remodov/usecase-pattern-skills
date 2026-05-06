---
name: ucp-test-design
description: Спроектировать интеграционные и unit-тесты для Java/Spring-сервиса по командной Test Strategy — синхронные тесты, только PostgreSQL через Testcontainers + WireMock для внешнего HTTP, без Kafka / Redis в базовом классе, детерминированное время и UUID через @MockitoBean, fluent DatabasePreparer + TestObjectGenerator. Применяется при добавлении тестов к новому UseCase / Handler или онбординге модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*) Bash(git diff*)
---

# Проектирование тестов

Ты пишешь тесты для Java/Spring-сервиса по командной Test Strategy.

## Зависимости

- **`.claude/docs/test-strategy.md`** в проекте (или из `claude-code-java`) — единственный источник правил. У каждого правила есть код `TS-N`.
- **`.claude/docs/usecase-spec-template.md`** — если есть спека сервиса, тестовые сценарии берутся оттуда (UC-1, UC-2, …, BR-001, BR-002, …).

## Инструкции

1. **Прочти стратегию** из `.claude/docs/test-strategy.md`. Цитируй коды `TS-N` в обоснованиях.

2. **Определи слой теста** перед тем как писать:

   - **Unit (без Spring)** — тест чистой бизнес-логики агрегата / value object. `new Order(...)`, `order.confirm()`. `TS-26`.
   - **`@WebMvcTest` / `MockMvc`** — тест контроллера и сериализации JSON. `TS-27`.
   - **Интеграционный** (`@SpringBootTest` + `BaseIntegrationTest`) — `TS-1` `TS-15` …
   - **E2E** — отдельная группа, `@Tag("e2e")`, реальные Kafka и внешние сервисы. Минимум, только для длинных Saga. `TS-28`.

   Назови выбранный слой в начале ответа и объясни выбор.

3. **Если базового класса в проекте ещё нет** — создай два уровня (`TS-4`):

   - **Платформенный `<App>BaseIntegrationTest`** — общие настройки: `@SpringBootTest(webEnvironment=RANDOM_PORT)`, `@ActiveProfiles("integration-test")`, `@Testcontainers`, `@TestInstance(PER_CLASS)`, `@Import(TestJwtConfiguration.class)`, `@ServiceConnection PostgreSQLContainer`, `@MockitoBean DateTimeService`, `@MockitoBean UuidGenerator`. **Не подключает** Kafka / Redis (`TS-19`, `TS-20`).
   - **Доменный `<Domain>BaseIntegrationTest`** — наследуется или повторяет платформенный + добавляет `@Autowired <Domain>DatabasePreparer`. По одному на Bounded Context.

   PostgreSQL-образ — **только публичный** (`postgres:16-alpine` или `postgres:16`). Никаких внутренних регистров типа `harbor.<company>.ru` в публикуемых примерах.

4. **Создай `<Domain>DatabasePreparer`** (`TS-9`–`TS-11`):

   - `@Component` + `@RequiredArgsConstructor` (`JS-6.1`), обёртка над `DSLContext`, поле `private final DSLContext dsl;` + `private final List<Runnable> preparers = new ArrayList<>();`.
   - Методы трёх групп:
     - `clear<Table>()` — `dsl.deleteFrom(<TABLE>).execute()`.
     - `create<Entity>(<Pojo>)` — insert через `dsl.insertInto(...).set(dsl.newRecord(<TABLE>, pojo)).execute()`.
     - `prepare()` — `preparers.forEach(Runnable::run); preparers.clear();`.
   - Не пересоздавай схему, только `DELETE`.
   - Учти порядок FK: при чистке — зависимые сначала; при создании — родительские сначала.
   - Lombok в test-scope тоже: `testCompileOnly` + `testAnnotationProcessor` (`JS-6.6`). Скилл `ucp-bootstrap-design` это уже прописал в build.

5. **Создай `<Entity>TestObjectGenerator`** для каждой POJO, на которую опирается тест (`TS-12`–`TS-14`):

   - Поля с разумными дефолтами: `UUID.randomUUID()`, `OffsetDateTime.now().withNano(0)`.
   - `with*(value)`-методы — fluent, возвращают `this`.
   - `generate()` — возвращает заполненную POJO.
   - **`withNano(0)`** обязательно для timestamp-полей, иначе сравнения с БД ломаются.

6. **Каждый тест** пиши по AAA (`TS-15`–`TS-18`):

   ```
   @Test
   @DisplayName("BR-XXX: <человеческое описание>")
   void <action>_when<Condition>_<expectedResult>() {
       // Arrange — given(uuidGenerator)/given(dateTimeService); generate POJO; databasePreparer.create*().prepare()
       // Act — restTemplate.exchange(URL, METHOD, new HttpEntity<>(body, TestHttpHeaders.withSuccessToken()), ResponseClass.class)
       // Assert — assertThat(response.getStatusCode()).isEqualTo(...); assertThat(dsl.selectFrom(...).fetch()) ...
   }
   ```

   - HTTP-вызовы — через **`TestRestTemplate`** (не MockMvc для интеграции).
   - JWT — через **`TestHttpHeaders.withSuccessToken()`** или специализированные `with<Role>Token(id)`.
   - Имя теста — длинное говорящее **или** короткое + `@DisplayName` с **цитированием BR-кода**, если применимо.

7. **Покрытие сценариев** делай по правилам:

   - **На каждый use case** из спеки — позитивный путь (UC-N happy) + альтернативные потоки + ошибки.
   - **На каждое бизнес-правило** (`BR-N`) — отдельный тест с кодом BR в `@DisplayName`.
   - **На каждое доменное событие** — тест, что оно появилось в Outbox (через `dsl.selectFrom(OUTBOX...)`).
   - **На каждый код ошибки** — тест, что ProblemDetails возвращается с правильным `code` / `status`.

8. **WireMock** (`TS-23`–`TS-25`) — поднимаем только если сервис делает внешние REST-вызовы. `@RegisterExtension static WireMockExtension`. Стабы пишем **прямо в тесте**, не в общих JSON-маппингах.

9. **Что запрещено:**

   - **Цитирование кодов правил в комментариях тестов** (`JS-7.3` в `java-style-guide.md`). Никаких `// TS-9..TS-11`, `// TS-7`, `// AC-C5` в исходниках. Названия классов / методов / `@DisplayName` уже выражают соответствие сценарию — в `@DisplayName` цитата BR / AC допустима (это бизнес-описание, не code-style-правило), а в коде — нет.
   - `Thread.sleep`, `Awaitility.await` — flaky (`TS-2`).
   - `Instant.now()`, `UUID.randomUUID()` напрямую в продакшен-коде — должны быть `DateTimeService` / `UuidGenerator` (`TS-7`).
   - `@MockBean` на бизнес-логику внутри своего сервиса (UseCaseHandler, агрегаты, репозитории). Mock-ируются только **внешние границы**: HTTP-клиенты (через WireMock или `@MockitoBean`), `DateTimeService`, `UuidGenerator`.
   - `EmbeddedKafka` в основном пакете тестов (`TS-21`).
   - Внутренние Docker-регистры (`harbor.<company>.ru` и т.п.) в публикуемых примерах.
   - Поля состояния в классе теста, меняющиеся между тестами без `@BeforeEach` cleanup.

10. **Перед выдачей кода** прогони чек-лист (`TS` § 9):

    - Слой выбран правильно (unit / mvc / integration / e2e).
    - Тесты синхронные.
    - В интеграции только Postgres + WireMock (если нужен), без Kafka / Redis.
    - Время и UUID — `@MockitoBean`.
    - `DatabasePreparer` чистит и наполняет БД; не пересоздаёт схему.
    - `TestObjectGenerator` имеет дефолты + `withNano(0)`.
    - PostgreSQL-образ — публичный.

## Структура вывода

1. **Резюме**: что тестируем, какой слой, какие use case-ы и BR покрыты.
2. **Файловое дерево** новых тестов и хелперов.
3. **Каждый файл** в отдельном code block с путём.
4. **Заметки по реализации**: что нужно в `build.gradle` (Testcontainers, WireMock, JUnit Jupiter, AssertJ, BDDMockito), как пустить локально (`./gradlew test --tests *.OrderConfirmIntegrationTest`).

$ARGUMENTS
