---
name: ucp-test-review
description: Ревью интеграционных и unit-тестов Java/Spring-сервиса по командной Test Strategy — слой выбран корректно (unit vs @WebMvcTest vs integration vs e2e), синхронные тесты, Postgres + WireMock через Testcontainers, без Kafka/Redis в базовом классе, детерминированное время и UUID через @MockitoBean, fluent DatabasePreparer + TestObjectGenerator, покрытие use case-ов и BR-кодов из спеки, отсутствие Thread.sleep/Awaitility, отсутствие @MockBean на бизнес-логику. Вызывается на свеже-написанных тестах или при онбординге существующего модуля. Опирается на коды TS-1..TS-28.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(./gradlew*)
---

# Ревью тестов

Ты ревьюишь Java/Spring-тесты на соответствие командной Test Strategy. Главные точки контроля: правильный выбор слоя, синхронность, базовый класс без Kafka/Redis, детерминированное время/UUID, покрытие UC и BR, отсутствие flaky-конструкций и моков на собственную бизнес-логику.

## Зависимости

- **`.claude/docs/test-strategy.md`** — индекс правил `TS-1`..`TS-28`. Цитируй конкретные коды (`TS-9`, `TS-19`), не префикс.
- Парные документы:
  - `.claude/docs/usecase-pattern-rules.md` (`R-UC-*`, `R-HND-*`) — для понимания, что тестируется на каком слое.
  - `.claude/docs/usecase-spec-template.md` — UC- и BR-коды берутся из спеки, в тесте цитируются в `@DisplayName`.
  - `.claude/docs/java-style-guide.md` (`JS-6.1`, `JS-7.3`) — Lombok-defaults на тестовых хелперах, запрет цитат кодов правил в комментариях.

## Инструкции

1. **Прочти стратегию** `.claude/docs/test-strategy.md`. Цитируй конкретные коды правил (`TS-19`, `TS-7`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые файлы в `src/test/java/**`.
   - Найди новые/изменённые `*IntegrationTest`, `*Test`, `BaseIntegrationTest`, `*DatabasePreparer`, `*TestObjectGenerator`.
   - Найди файлы с импортами `org.testcontainers.*`, `com.github.tomakehurst.wiremock.*`, `org.springframework.boot.test.*`.

3. **Прогон по правилам.** Проверяй каждое применимое:

   - **`TS-1`** — тесты синхронные, без `Thread.sleep` / `Awaitility.await` / `CountDownLatch.await(timeout)`.
   - **`TS-2`** — нет flaky-конструкций (`Awaitility`, `await().untilAsserted`, `Thread.sleep` в тесте).
   - **`TS-3`** — нет `@DirtiesContext` — `DatabasePreparer.clear*()` чистит БД между тестами без пересоздания контекста.
   - **`TS-4`** — два уровня базовых классов: платформенный `<App>BaseIntegrationTest` (`@SpringBootTest`, `@Testcontainers`, `@ServiceConnection`) и доменный `<Domain>BaseIntegrationTest` (наследует + `@Autowired <Domain>DatabasePreparer`).
   - **`TS-5`–`TS-6`** — `@TestInstance(PER_CLASS)`, `@ActiveProfiles("integration-test")`, `@Import(TestJwtConfiguration.class)`.
   - **`TS-7`** — `@MockitoBean DateTimeService dateTimeService` и `@MockitoBean UuidGenerator uuidGenerator`. Время / UUID детерминированные через `given(...)`, не `Instant.now()` / `UUID.randomUUID()` в продакшен-коде.
   - **`TS-8`** — Testcontainers через `@ServiceConnection` (Spring Boot 3.1+), не ручной `@DynamicPropertySource`. PostgreSQL-образ — **публичный** (`postgres:16-alpine`), не внутренний registry.
   - **`TS-9`–`TS-11`** — `<Domain>DatabasePreparer` есть, `@Component` + `@RequiredArgsConstructor`, методы трёх групп (`clear*`, `create*`, `prepare`), порядок FK соблюдён.
   - **`TS-12`–`TS-14`** — `<Entity>TestObjectGenerator` есть, fluent `with*(value)`, `generate()` возвращает заполненную POJO. **`withNano(0)`** обязателен на timestamp-полях.
   - **`TS-15`–`TS-18`** — структура теста AAA, `@DisplayName` с BR-кодом из спеки, HTTP через `TestRestTemplate` (не MockMvc в интеграции), JWT через `TestHttpHeaders.withSuccessToken()` / `with<Role>Token(id)`.
   - **`TS-19`–`TS-20`** — в `BaseIntegrationTest` **нет** Kafka / Redis. Кафка-листенеры выключены через `spring.kafka.listener.auto-startup: false` в `application-integration-test.yml` (BS-13).
   - **`TS-21`** — `EmbeddedKafka` запрещён в основном пакете тестов. Если нужен — отдельный `@Tag("kafka-it")`.
   - **`TS-22`** — события проверяются через таблицу `outbox` (`dsl.selectFrom(OUTBOX)`), не через консьюмер.
   - **`TS-23`–`TS-25`** — WireMock через `@RegisterExtension static WireMockExtension`, стабы пишутся **прямо в тесте**, не в общих JSON-маппингах.
   - **`TS-26`** — unit-тесты бизнес-логики (агрегаты / VO) — `new Aggregate(...)`, без Spring.
   - **`TS-27`** — `@WebMvcTest` + `MockMvc` только для теста контроллера / JSON-сериализации, не для бизнес-логики.
   - **`TS-28`** — `@Tag("e2e")` для длинных Saga / реального Kafka, отдельная группа в CI, минимум.

4. **При ревью кода ищи паттерны-нарушения:**

   - `Thread.sleep(N)`, `Awaitility.await()`, `CountDownLatch.await(timeout)` в теле теста — `TS-1` / `TS-2`.
   - `Instant.now()` / `UUID.randomUUID()` в продакшен-коде вместо `DateTimeService` / `UuidGenerator` — `TS-7`.
   - `@MockBean` / `@MockitoBean` на собственный `UseCaseHandler`, агрегат, `*Repository` — `TS-7-X1` (мокать только внешние границы).
   - `@DirtiesContext` на классе теста — `TS-3` (используй `DatabasePreparer.clear*()`).
   - `@DynamicPropertySource` для Postgres-URL вместо `@ServiceConnection` — `TS-8`.
   - PostgreSQL-образ `harbor.<company>.ru/...` или другой внутренний registry в публикуемых тестах — `TS-8` (использовать `postgres:16-alpine`).
   - `EmbeddedKafkaBroker` / `@EmbeddedKafka` в `*IntegrationTest` без `@Tag` — `TS-21`.
   - `KafkaTemplate.send(...)` + `consumer.poll(...)` для проверки события вместо чтения из `outbox` — `TS-22`.
   - `MockMvc` в `@SpringBootTest`-тесте (вместо `TestRestTemplate`) — `TS-15` / `TS-27` (определись со слоем).
   - `restTemplate.exchange(URL, METHOD, new HttpEntity<>(body), Class)` без JWT-заголовка для protected-endpoint — `TS-16`.
   - `@DisplayName` отсутствует или не цитирует BR-/UC-код, при том что спека содержит соответствующий пункт — `TS-15`.
   - Тест без assertions (`assertThat(...)`) или с `assertTrue(result != null)` вместо `assertThat(result).isNotNull()` — стиль AssertJ (`TS-17`).
   - `TestObjectGenerator` с timestamp без `withNano(0)` — `TS-14`.
   - `@BeforeEach` с прямым `dsl.deleteFrom(...)` вместо `databasePreparer.clearAll()` — `TS-9`.
   - Цитаты кодов правил в комментариях тестов (`// TS-9`, `// AC-C5`) — `JS-7.3` (`@DisplayName` с BR-кодом — OK, это бизнес-описание; комментарий с кодом правила — нет).
   - Поля состояния в классе теста, меняющиеся между тестами без cleanup — `TS-17` (тест зависит от порядка выполнения).
   - `harbor.<company>.ru/postgres:...` в коммитимых тестах — `TS-8` (используй публичный образ).

5. **Покрытие сценариев** (`TS-15` + структура спеки):
   - На каждый use case из спеки §6 — позитивный + альтернативные потоки + ошибки.
   - На каждое бизнес-правило `BR-N` — отдельный тест, `BR-N` в `@DisplayName`.
   - На каждое доменное событие — тест чтения из `outbox`.
   - На каждый код ошибки из карточки команды — тест ProblemDetails-ответа.

   Если в проекте есть `docs/spec/`, сверь список тестов с `§6 Use Cases` корневого файла и `§4 Бизнес-правила` файлов агрегатов. Пропущенные UC-/BR-коды — findings с кодом `TS-15`.

6. **При ревью базового класса (`*BaseIntegrationTest`):**
   - `@SpringBootTest(webEnvironment = RANDOM_PORT)`, `@ActiveProfiles("integration-test")`, `@Testcontainers`, `@TestInstance(PER_CLASS)` — обязательны.
   - `@ServiceConnection` на `PostgreSQLContainer` (не `@DynamicPropertySource`).
   - `@MockitoBean DateTimeService` + `@MockitoBean UuidGenerator`.
   - `@Import(TestJwtConfiguration.class)`.
   - **Нет** `KafkaContainer`, `RedisContainer`, `@EmbeddedKafka`, `RedisStarter`.
   - PostgreSQL-образ публичный (`postgres:16-alpine`).

7. **При ревью `DatabasePreparer`:**
   - `@Component` + `@RequiredArgsConstructor` (`JS-6.1`).
   - Поля `private final DSLContext dsl;` + `private final List<Runnable> preparers = new ArrayList<>();`.
   - Методы `clear<Table>()`, `create<Entity>(<Pojo>)`, `prepare()`.
   - Не пересоздаёт схему, только `DELETE`.
   - Порядок FK: при чистке зависимые сначала, при создании родительские сначала.

8. **При ревью `TestObjectGenerator`:**
   - Разумные дефолты (`UUID.randomUUID()`, `OffsetDateTime.now().withNano(0)`).
   - Fluent `with*(value)` — возвращают `this`.
   - `generate()` — финальный билд.
   - `withNano(0)` обязательно на timestamp-полях.

9. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`TS-19`, `TS-7`).

10. **Доменные ориентиры серьёзности** (`RFF-12`):
    - **Критично** — нарушения, ведущие к flaky-тестам, ложно-зелёным регрессиям или утечкам в прод:
      - `Thread.sleep` / `Awaitility` в тесте (`TS-1`, `TS-2`) — flaky под нагрузкой CI.
      - `@MockBean` на собственный `UseCaseHandler` / агрегат (`TS-7-X1`) — тест проверяет мок, не код.
      - `Instant.now()` / `UUID.randomUUID()` в продакшен-коде (`TS-7`) — детерминированности нет, тесты ловят случайности.
      - `EmbeddedKafka` в основном пакете тестов (`TS-21`) — десятки секунд на тест, тормозит CI.
      - Pure-unit-логика, написанная как `@SpringBootTest` (`TS-26`) — раздувает время сборки на ровном месте.
      - Внутренний Docker-registry в коммитимых тестах (`TS-8`) — публичный CI / open-source адопшен не пройдёт.
    - **Предупреждение** — отклонения от конвенций:
      - `MockMvc` в `@SpringBootTest` вместо `TestRestTemplate` (`TS-15`) — путаница слоёв.
      - `@DirtiesContext` (`TS-3`) — медленные тесты, починить через `DatabasePreparer`.
      - `@DynamicPropertySource` вместо `@ServiceConnection` (`TS-8`) — устаревший стиль для Spring Boot 3.1+.
      - `withNano(0)` отсутствует (`TS-14`) — flaky сравнение с БД.
    - **Замечание** — стилистика:
      - `@DisplayName` без BR-/UC-кода при наличии в спеке (`TS-15`).
      - `assertTrue(x != null)` вместо `assertThat(x).isNotNull()` (`TS-17`).
      - Цитата кода правила в комментарии теста (`JS-7.3`).

## Что не входит

- Дизайн новых тестов — `ucp-test-design`.
- Бизнес-логика тестируемого UseCase / Handler / агрегата — `ucp-pattern-review` / `ucp-ddd-tactical-review`.
- jOOQ-запросы внутри `DatabasePreparer` — `ucp-jooq-review`.
- Resilience-аспекты тестов (mock внешних сервисов через WireMock) — `ucp-resilience-review` для production-кода, здесь только проверка корректности стабов.
- Java-стиль (нейминг, импорты) — `ucp-java-style-review`.
- Bootstrap-конфиг профиля `integration-test` — `ucp-bootstrap-design` / `ucp-shutdown-review`.

$ARGUMENTS
