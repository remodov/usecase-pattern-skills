---
name: ucp-test-design
description: Спроектировать интеграционные и unit-тесты для Java/Spring-сервиса по Test Strategy — синхронные тесты, PostgreSQL через Testcontainers + WireMock, без Kafka/Redis в базовом классе, детерминированное время (fixClock или @MockitoBean).
when_to_use: При добавлении тестов к новому UseCase/Handler или онбординге модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*) Bash(git diff*)
---

# Проектирование тестов

Ты пишешь тесты для Java/Spring-сервиса по командной Test Strategy.

## Зависимости

- **`.claude/docs/backend/java/test-strategy/spec.md`** в проекте (или из `claude-code-java`) — индекс всех правил (полный текст с примерами — `references/implementation.md`). У каждого правила есть код `TS-N`.
- **`.claude/docs/shared/spec-format/spec.md`** — если есть спека сервиса, тестовые сценарии берутся оттуда (UC-1, UC-2, …, BR-001, BR-002, …).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/java/test-strategy/spec.md` (полный текст с примерами тестов и base-классов — `backend/java/test-strategy/references/implementation.md`, открывай точечно по разделу). Цитируй коды `TS-N` в обоснованиях.

2. **Определи слой теста** перед тем как писать:

   - **Unit (без Spring)** — тест чистой бизнес-логики агрегата / value object. `new Order(...)`, `order.confirm()`. `test-strategy/test-layers-separated`.
   - **`@WebMvcTest` / `MockMvc`** — тест контроллера и сериализации JSON. `test-strategy/test-layers-separated`.
   - **Интеграционный** (`@SpringBootTest` + `BaseIntegrationTest`) — `test-strategy/integration-test-shape` `test-strategy/test-uses-http-client` …
   - **E2E** — отдельная группа, `@Tag("e2e")`, реальные Kafka и внешние сервисы. Минимум, только для длинных Saga. `test-strategy/test-layers-separated`.

   Назови выбранный слой в начале ответа и объясни выбор.

3. **Если базового класса в проекте ещё нет** — создай два уровня (`test-strategy/base-classes-layered`):

   - **Платформенный `<App>BaseIntegrationTest`** — общие настройки: `@SpringBootTest(webEnvironment=RANDOM_PORT)`, `@ActiveProfiles("integration-test")`, `@Testcontainers`, `@TestInstance(PER_CLASS)`, `@Import(TestJwtConfiguration.class)`, `@ServiceConnection PostgreSQLContainer`, фиксация времени по варианту проекта (`fixClock`/`resetClock` или `@MockitoBean DateTimeService`). **Не подключает** Kafka / Redis (`test-strategy/no-broker-or-cache-in-integration-tests`, `test-strategy/no-broker-or-cache-in-integration-tests`).
   - **Доменный `<Domain>BaseIntegrationTest`** — наследуется или повторяет платформенный + добавляет `@Autowired <Domain>DatabasePreparer`. По одному на Bounded Context.

   PostgreSQL-образ — **только публичный** (`postgres:16-alpine` или `postgres:16`). Никаких внутренних регистров типа `harbor.<company>.ru` в публикуемых примерах.

4. **Создай `<Domain>DatabasePreparer`** (`test-strategy/database-preparer-per-context`–`test-strategy/database-preparer-per-context`):

   - `@Component` + `@RequiredArgsConstructor` (`java-style/boilerplate-is-generated`), обёртка над `DSLContext`, поле `private final DSLContext dsl;` + `private final List<Runnable> preparers = new ArrayList<>();`.
   - Методы трёх групп:
     - `clear<Table>()` — `dsl.deleteFrom(<TABLE>).execute()`.
     - `create<Entity>(<Pojo>)` — insert через `dsl.insertInto(...).set(dsl.newRecord(<TABLE>, pojo)).execute()`.
     - `prepare()` — `preparers.forEach(Runnable::run); preparers.clear();`.
   - Не пересоздавай схему, только `DELETE`.
   - Учти порядок FK: при чистке — зависимые сначала; при создании — родительские сначала.
   - Lombok в test-scope тоже: `testCompileOnly` + `testAnnotationProcessor` (`java-style/generation-setup-is-uniform`). Скилл `ucp-bootstrap-design` это уже прописал в build.

5. **Создай `<Entity>TestObjectGenerator`** для каждой POJO, на которую опирается тест (`test-strategy/builders-with-defaults`–`test-strategy/builders-with-defaults`):

   - Поля с разумными дефолтами: `UUID.randomUUID()`, `OffsetDateTime.now().withNano(0)`.
   - `with*(value)`-методы — fluent, возвращают `this`.
   - `generate()` — возвращает заполненную POJO.
   - **`withNano(0)`** обязательно для timestamp-полей, иначе сравнения с БД ломаются.

6. **Каждый тест** пиши по AAA (`test-strategy/test-uses-http-client`–`test-strategy/test-auth-single-source`):

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

8. **WireMock** (`test-strategy/external-calls-via-stub-server`–`test-strategy/external-calls-via-stub-server`) — поднимаем только если сервис делает внешние REST-вызовы. `@RegisterExtension static WireMockExtension`. Стабы пишем **прямо в тесте**, не в общих JSON-маппингах.

9. **Что запрещено:**

   - **Цитирование кодов правил в комментариях тестов** (`java-style/no-rule-codes-or-history-in-code` в `backend/java/java-style/spec.md`). Никаких `// TS-9..TS-11`, `// TS-7`, `// AC-C5` в исходниках. Названия классов / методов / `@DisplayName` уже выражают соответствие сценарию — в `@DisplayName` цитата BR / AC допустима (это бизнес-описание, не code-style-правило), а в коде — нет.
   - `Thread.sleep`, `Awaitility.await` — flaky (`test-strategy/tests-are-synchronous-and-deterministic`).
   - `Instant.now()` / `OffsetDateTime.now()` напрямую в продакшен-коде — время идёт через источник времени сервиса (`DateTimeUtil` или `DateTimeService`); `UUID.randomUUID()` допустим в фабриках и событиях (`test-strategy/tests-are-synchronous-and-deterministic`).
   - `@MockBean` на бизнес-логику внутри своего сервиса (UseCaseHandler, агрегаты, репозитории). Mock-ируются только **внешние границы**: HTTP-клиенты (через WireMock или `@MockitoBean`), `DateTimeService`, `UuidGenerator`.
   - `EmbeddedKafka` в основном пакете тестов (`test-strategy/no-broker-or-cache-in-integration-tests`).
   - Внутренние Docker-регистры (`harbor.<company>.ru` и т.п.) в публикуемых примерах.
   - Поля состояния в классе теста, меняющиеся между тестами без `@BeforeEach` cleanup.

10. **Перед выдачей кода** прогони чек-лист (`TS` § 9):

    - Слой выбран правильно (unit / mvc / integration / e2e).
    - Тесты синхронные.
    - В интеграции только Postgres + WireMock (если нужен), без Kafka / Redis.
    - Время — `fixClock` при статическом `Clock` или `@MockitoBean DateTimeService` при бине; UUID — предзаданы только при `UuidGenerator`-бине.
    - `DatabasePreparer` чистит и наполняет БД; не пересоздаёт схему.
    - `TestObjectGenerator` имеет дефолты + `withNano(0)`.
    - PostgreSQL-образ — публичный.

## Вывод

по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

$ARGUMENTS
