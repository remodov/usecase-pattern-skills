---
name: ucp-test-review
description: Ревью интеграционных и unit-тестов Java/Spring по командной Test Strategy (требования test-strategy/*) — выбор слоя, синхронность, Postgres + WireMock через Testcontainers, детерминированные время/UUID, покрытие UC и BR, без Thread.sleep/@MockBean.
when_to_use: Свеже-написанные тесты в src/test/java или онбординг существующего модуля.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(./gradlew*)
---

# Ревью тестов

Ты ревьюишь Java/Spring-тесты на соответствие командной Test Strategy. Главные точки контроля: правильный выбор слоя, синхронность, базовый класс без Kafka/Redis, детерминированное время/UUID, покрытие UC и BR, отсутствие flaky-конструкций и моков на собственную бизнес-логику.

## Зависимости

- **`.claude/docs/backend/java/test-strategy/spec.md`** — индекс правил `test-strategy/integration-test-shape`..`test-strategy/test-layers-separated`. Цитируй конкретные коды (`test-strategy/database-preparer-per-context`, `test-strategy/no-broker-or-cache-in-integration-tests`), не префикс.
- Парные документы:
  - `.claude/docs/backend/usecase-pattern/spec.md` (`R-UC-*`, `R-HND-*`) — для понимания, что тестируется на каком слое.
  - `.claude/docs/shared/spec-format/spec.md` — UC- и BR-коды берутся из спеки, в тесте цитируются в `@DisplayName`.
  - `.claude/docs/backend/java/java-style/spec.md` (`java-style/boilerplate-is-generated`, `java-style/no-rule-codes-or-history-in-code`) — Lombok-defaults на тестовых хелперах, запрет цитат кодов правил в комментариях.

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/java/test-strategy/spec.md` (полный текст с примерами тестов и base-классов — `backend/java/test-strategy/references/implementation.md`, открывай точечно по разделу). Цитируй конкретные коды правил (`test-strategy/no-broker-or-cache-in-integration-tests`, `test-strategy/tests-are-synchronous-and-deterministic`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые файлы в `src/test/java/**`.
   - Найди новые/изменённые `*IntegrationTest`, `*Test`, `BaseIntegrationTest`, `*DatabasePreparer`, `*TestObjectGenerator`.
   - Найди файлы с импортами `org.testcontainers.*`, `com.github.tomakehurst.wiremock.*`, `org.springframework.boot.test.*`.

3. **Прогон по правилам.** Проверяй каждое применимое:

   - **`test-strategy/integration-test-shape`** — тесты синхронные, без `Thread.sleep` / `Awaitility.await` / `CountDownLatch.await(timeout)`.
   - **`test-strategy/tests-are-synchronous-and-deterministic`** — нет flaky-конструкций (`Awaitility`, `await().untilAsserted`, `Thread.sleep` в тесте).
   - **`test-strategy/one-test-one-scenario`** — нет `@DirtiesContext` — `DatabasePreparer.clear*()` чистит БД между тестами без пересоздания контекста.
   - **`test-strategy/base-classes-layered`** — два уровня базовых классов: платформенный `<App>BaseIntegrationTest` (`@SpringBootTest`, `@Testcontainers`, `@ServiceConnection`) и доменный `<Domain>BaseIntegrationTest` (наследует + `@Autowired <Domain>DatabasePreparer`).
   - **`test-strategy/container-connection-is-automatic`–`test-strategy/expensive-setup-runs-once`** — `@TestInstance(PER_CLASS)`, `@ActiveProfiles("integration-test")`, `@Import(TestJwtConfiguration.class)`.
   - **`test-strategy/tests-are-synchronous-and-deterministic`** — время предзадано по варианту источника в проекте: `fixClock(now)` + `@AfterEach resetClock()` при статическом `DateTimeUtil`, либо `@MockitoBean DateTimeService` (и `UuidGenerator`) с `given(...)` при бинах; в продакшен-коде нет `Instant.now()` / `OffsetDateTime.now()`; два источника времени в одном сервисе — находка.
   - **`test-strategy/test-auth-single-source`** — Testcontainers через `@ServiceConnection` (Spring Boot 3.1+), не ручной `@DynamicPropertySource`. PostgreSQL-образ — **публичный** (`postgres:16-alpine`), не внутренний registry.
   - **`test-strategy/database-preparer-per-context`–`test-strategy/database-preparer-per-context`** — `<Domain>DatabasePreparer` есть, `@Component` + `@RequiredArgsConstructor`, методы трёх групп (`clear*`, `create*`, `prepare`), порядок FK соблюдён.
   - **`test-strategy/builders-with-defaults`–`test-strategy/builders-with-defaults`** — `<Entity>TestObjectGenerator` есть, fluent `with*(value)`, `generate()` возвращает заполненную POJO. **`withNano(0)`** обязателен на timestamp-полях.
   - **`test-strategy/test-uses-http-client`–`test-strategy/test-auth-single-source`** — структура теста AAA, `@DisplayName` с BR-кодом из спеки, HTTP через `TestRestTemplate` (не MockMvc в интеграции), JWT через `TestHttpHeaders.withSuccessToken()` / `with<Role>Token(id)`.
   - **`test-strategy/no-broker-or-cache-in-integration-tests`–`test-strategy/no-broker-or-cache-in-integration-tests`** — в `BaseIntegrationTest` **нет** Kafka / Redis. Кафка-листенеры выключены через `spring.kafka.listener.auto-startup: false` в `application-integration-test.yml` (BS-13).
   - **`test-strategy/no-broker-or-cache-in-integration-tests`** — `EmbeddedKafka` запрещён в основном пакете тестов. Если нужен — отдельный `@Tag("kafka-it")`.
   - **`test-strategy/async-effects-made-synchronous`** — события проверяются через таблицу `outbox` (`dsl.selectFrom(OUTBOX)`), не через консьюмер.
   - **`test-strategy/external-calls-via-stub-server`–`test-strategy/external-calls-via-stub-server`** — WireMock через `@RegisterExtension static WireMockExtension`, стабы пишутся **прямо в тесте**, не в общих JSON-маппингах.
   - **`test-strategy/test-layers-separated`** — unit-тесты бизнес-логики (агрегаты / VO) — `new Aggregate(...)`, без Spring.
   - **`test-strategy/test-layers-separated`** — `@WebMvcTest` + `MockMvc` только для теста контроллера / JSON-сериализации, не для бизнес-логики.
   - **`test-strategy/test-layers-separated`** — `@Tag("e2e")` для длинных Saga / реального Kafka, отдельная группа в CI, минимум.

4. **При ревью кода ищи паттерны-нарушения:**

   - `Thread.sleep(N)`, `Awaitility.await()`, `CountDownLatch.await(timeout)` в теле теста — `test-strategy/integration-test-shape` / `test-strategy/tests-are-synchronous-and-deterministic`.
   - `Instant.now()` / `OffsetDateTime.now()` в продакшен-коде мимо источника времени сервиса — `test-strategy/tests-are-synchronous-and-deterministic`.
   - `@MockBean` / `@MockitoBean` на собственный `UseCaseHandler`, агрегат, `*Repository` — `TS-7-X1` (мокать только внешние границы).
   - `@DirtiesContext` на классе теста — `test-strategy/one-test-one-scenario` (используй `DatabasePreparer.clear*()`).
   - `@DynamicPropertySource` для Postgres-URL вместо `@ServiceConnection` — `test-strategy/test-auth-single-source`.
   - PostgreSQL-образ `harbor.<company>.ru/...` или другой внутренний registry в публикуемых тестах — `test-strategy/test-auth-single-source` (использовать `postgres:16-alpine`).
   - `EmbeddedKafkaBroker` / `@EmbeddedKafka` в `*IntegrationTest` без `@Tag` — `test-strategy/no-broker-or-cache-in-integration-tests`.
   - `KafkaTemplate.send(...)` + `consumer.poll(...)` для проверки события вместо чтения из `outbox` — `test-strategy/async-effects-made-synchronous`.
   - `MockMvc` в `@SpringBootTest`-тесте (вместо `TestRestTemplate`) — `test-strategy/test-uses-http-client` / `test-strategy/test-layers-separated` (определись со слоем).
   - `restTemplate.exchange(URL, METHOD, new HttpEntity<>(body), Class)` без JWT-заголовка для protected-endpoint — `test-strategy/test-name-states-scenario`.
   - `@DisplayName` отсутствует или не цитирует BR-/UC-код, при том что спека содержит соответствующий пункт — `test-strategy/test-uses-http-client`.
   - Тест без assertions (`assertThat(...)`) или с `assertTrue(result != null)` вместо `assertThat(result).isNotNull()` — стиль AssertJ (`test-strategy/test-uses-http-client`).
   - `TestObjectGenerator` с timestamp без `withNano(0)` — `test-strategy/builders-with-defaults`.
   - `@BeforeEach` с прямым `dsl.deleteFrom(...)` вместо `databasePreparer.clearAll()` — `test-strategy/database-preparer-per-context`.
   - Цитаты кодов правил в комментариях тестов (`// TS-9`, `// AC-C5`) — `java-style/no-rule-codes-or-history-in-code` (`@DisplayName` с BR-кодом — OK, это бизнес-описание; комментарий с кодом правила — нет).
   - Поля состояния в классе теста, меняющиеся между тестами без cleanup — `test-strategy/test-uses-http-client` (тест зависит от порядка выполнения).
   - `harbor.<company>.ru/postgres:...` в коммитимых тестах — `test-strategy/test-auth-single-source` (используй публичный образ).

5. **Покрытие сценариев** (`test-strategy/test-uses-http-client` + структура спеки):
   - На каждый use case из спеки §6 — позитивный + альтернативные потоки + ошибки.
   - На каждое бизнес-правило `BR-N` — отдельный тест, `BR-N` в `@DisplayName`.
   - На каждое доменное событие — тест чтения из `outbox`.
   - На каждый код ошибки из карточки команды — тест ProblemDetails-ответа.

   Если в проекте есть `docs/spec/`, сверь список тестов с `§6 Use Cases` корневого файла и `§4 Бизнес-правила` файлов агрегатов. Пропущенные UC-/BR-коды — findings с кодом `test-strategy/test-uses-http-client`.

6. **При ревью базового класса (`*BaseIntegrationTest`):**
   - `@SpringBootTest(webEnvironment = RANDOM_PORT)`, `@ActiveProfiles("integration-test")`, `@Testcontainers`, `@TestInstance(PER_CLASS)` — обязательны.
   - `@ServiceConnection` на `PostgreSQLContainer` (не `@DynamicPropertySource`).
   - Фиксация времени по варианту проекта: `fixClock`/`resetClock` при статическом `Clock` либо `@MockitoBean DateTimeService` при бине.
   - `@Import(TestJwtConfiguration.class)`.
   - **Нет** `KafkaContainer`, `RedisContainer`, `@EmbeddedKafka`, `RedisStarter`.
   - PostgreSQL-образ публичный (`postgres:16-alpine`).

7. **При ревью `DatabasePreparer`:**
   - `@Component` + `@RequiredArgsConstructor` (`java-style/boilerplate-is-generated`).
   - Поля `private final DSLContext dsl;` + `private final List<Runnable> preparers = new ArrayList<>();`.
   - Методы `clear<Table>()`, `create<Entity>(<Pojo>)`, `prepare()`.
   - Не пересоздаёт схему, только `DELETE`.
   - Порядок FK: при чистке зависимые сначала, при создании родительские сначала.

8. **При ревью `TestObjectGenerator`:**
   - Разумные дефолты (`UUID.randomUUID()`, `OffsetDateTime.now().withNano(0)`).
   - Fluent `with*(value)` — возвращают `this`.
   - `generate()` — финальный билд.
   - `withNano(0)` обязательно на timestamp-полях.

9. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`test-strategy/no-broker-or-cache-in-integration-tests`, `test-strategy/tests-are-synchronous-and-deterministic`).

10. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
    - **Критично** — нарушения, ведущие к flaky-тестам, ложно-зелёным регрессиям или утечкам в прод:
      - `Thread.sleep` / `Awaitility` в тесте (`test-strategy/integration-test-shape`, `test-strategy/tests-are-synchronous-and-deterministic`) — flaky под нагрузкой CI.
      - `@MockBean` на собственный `UseCaseHandler` / агрегат (`TS-7-X1`) — тест проверяет мок, не код.
      - `Instant.now()` / `UUID.randomUUID()` в продакшен-коде (`test-strategy/tests-are-synchronous-and-deterministic`) — детерминированности нет, тесты ловят случайности.
      - `EmbeddedKafka` в основном пакете тестов (`test-strategy/no-broker-or-cache-in-integration-tests`) — десятки секунд на тест, тормозит CI.
      - Pure-unit-логика, написанная как `@SpringBootTest` (`test-strategy/test-layers-separated`) — раздувает время сборки на ровном месте.
      - Внутренний Docker-registry в коммитимых тестах (`test-strategy/test-auth-single-source`) — публичный CI / open-source адопшен не пройдёт.
    - **Предупреждение** — отклонения от конвенций:
      - `MockMvc` в `@SpringBootTest` вместо `TestRestTemplate` (`test-strategy/test-uses-http-client`) — путаница слоёв.
      - `@DirtiesContext` (`test-strategy/one-test-one-scenario`) — медленные тесты, починить через `DatabasePreparer`.
      - `@DynamicPropertySource` вместо `@ServiceConnection` (`test-strategy/test-auth-single-source`) — устаревший стиль для Spring Boot 3.1+.
      - `withNano(0)` отсутствует (`test-strategy/builders-with-defaults`) — flaky сравнение с БД.
    - **Замечание** — стилистика:
      - `@DisplayName` без BR-/UC-кода при наличии в спеке (`test-strategy/test-uses-http-client`).
      - `assertTrue(x != null)` вместо `assertThat(x).isNotNull()` (`test-strategy/test-uses-http-client`).
      - Цитата кода правила в комментарии теста (`java-style/no-rule-codes-or-history-in-code`).

## Что не входит

- Дизайн новых тестов — `ucp-test-design`.
- Бизнес-логика тестируемого UseCase / Handler / агрегата — `ucp-pattern-review` / `ucp-ddd-tactical-review`.
- jOOQ-запросы внутри `DatabasePreparer` — `ucp-jooq-review`.
- Resilience-аспекты тестов (mock внешних сервисов через WireMock) — `ucp-resilience-review` для production-кода, здесь только проверка корректности стабов.
- Java-стиль (нейминг, импорты) — `ucp-java-style-review`.
- Bootstrap-конфиг профиля `integration-test` — `ucp-bootstrap-design` / `ucp-shutdown-review`.

$ARGUMENTS
