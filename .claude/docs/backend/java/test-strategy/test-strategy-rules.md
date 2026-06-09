# Test Strategy — индекс правил

> **Что это.** Сжатый индекс правил `test-strategy.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами тестов, base-классов и preparer'ов — `test-strategy.md`**; открывай её точечно по разделу.
> Коды: `TS-<N>`. X-кодов нет; запреты вшиты в формулировки.
> Связанные: `R-PATT-*` (UseCase покрыт интеграционным), `R-AGG-*` (unit на инварианты), `R-JOOQ-REPO-6` (репозиторий против Testcontainers), `R-RES-OAS-*` (WireMock), `AUTH-19` (Idempotency-Key тесты).

Базовый принцип (`TS-1`): **тест быстрый и детерминированный**. Если тест требует Kafka/Redis/несколько контейнеров и `Awaitility` — это инфраструктурный smoke, не тест на бизнес-логику.

## 1. Базовые правила
**MUST:**
- **TS-1.** Интеграционный тест — полный Spring-контекст + реальный PostgreSQL + контроллер через HTTP; внешний HTTP — WireMock / `@MockitoBean`; Kafka/Redis — in-memory или выключены профилем.
- **TS-2.** Все тесты синхронные: никаких `CompletableFuture.get()`, `Awaitility.await()`, `Thread.sleep`; время и UUID — детерминированы через `@MockitoBean` (`TS-7`).
- **TS-3.** Один тест — один сценарий, AAA-структура (Arrange → Act → Assert).

## 2. Структура BaseIntegrationTest
**MUST:**
- **TS-4.** Один платформенный `BaseIntegrationTest` на сервис + по доменному base на каждый Bounded Context (наследует платформенный + свои `DatabasePreparer`-ы).
- **TS-5.** `@ServiceConnection` (Spring Boot 3.1+) сам прокидывает `spring.datasource.*` — не писать `@DynamicPropertySource` для PostgreSQL руками.
- **TS-6.** `@TestInstance(Lifecycle.PER_CLASS)` — экземпляр живёт всё время; дорогой setup в `@BeforeAll` без `static`.
- **TS-7.** Время и UUID — `@MockitoBean` на `DateTimeService` и `UuidGenerator`, возвращают предзаданные значения; никаких `Instant.now()`/`UUID.randomUUID()` напрямую.
- **TS-8.** `@Import(TestJwtConfiguration.class)` — фейковый JWT-validator + `TestHttpHeaders.withSuccessToken()`; единый source-of-truth по тестовой авторизации.

## 3. DatabasePreparer — fluent setup БД
**MUST:**
- **TS-9.** На каждый Bounded Context — свой `<Domain>DatabasePreparer` (`@Component` над `DSLContext`) с группами `clear*()`, `create*(...)`, `prepare()`.
- **TS-10.** Не пересоздаём схему между тестами — только `DELETE` нужных таблиц (мс vs секунды); схема — один раз при старте через Liquibase.
- **TS-11.** Порядок методов внутри `prepare()` — порядок вызова; при FK учитывать (FK последним создаём, первым чистим).

## 4. TestObjectGenerator — fluent builders
**MUST:**
- **TS-12.** На каждую POJO-таблицу — builder с `with*` и `generate()`.
- **TS-13.** Разумные дефолты в генераторе (`UUID.randomUUID()`, время с обнулёнными наносекундами); в тесте перезаписываем только важное для сценария.
- **TS-14.** `withNano(0)` обязательно при сравнении `OffsetDateTime` в БД (PostgreSQL хранит миллисекунды).

## 5. Структура одного теста
**MUST:**
- **TS-15.** Тест extends `<Domain>BaseIntegrationTest`, инжектит `TestRestTemplate` и `DatabasePreparer`.
- **TS-16.** Имена методов: `<action>_when<Condition>_<expectedResult>` или длинное говорящее; в обоих — `@DisplayName` с цитатой BR-кода.
- **TS-17.** HTTP-вызов через `TestRestTemplate.exchange(...)` (контроль метода/заголовков/тела); `MockMvc` — для unit-тестов контроллера без БД.
- **TS-18.** JWT — через `TestHttpHeaders.withSuccessToken()` / специализированный (`withCustomerToken(...)`), не собираем токены руками.

## 6. Kafka, Redis, async — по умолчанию НЕТ
**MUST:**
- **TS-19.** Не поднимаем Kafka в интеграционных — события в Outbox-таблице, проверяем содержимое через `DatabasePreparer`/`DSLContext`.
- **TS-20.** Redis не поднимаем — профиль `integration-test` ставит `spring.cache.type=none`.
- **TS-21.** Подписка на Kafka (idempotent consumer) — тестируем handler напрямую как бин (`eventHandler.handle(testEvent)`), без `EmbeddedKafka`.
- **TS-22.** Async/Saga (`@TransactionalEventListener(AFTER_COMMIT)`) — переводим в синхрон через профиль теста или ручной commit + вызов handler.

## 7. Внешние HTTP — WireMock
**MUST:**
- **TS-23.** Внешний REST (платёж, каталог, логистика) — WireMock в `BaseIntegrationTest` (`@RegisterExtension` + `@DynamicPropertySource` для base-url).
- **TS-24.** Стабы пишем в самом тесте, не в общих `mappings/*.json` — видно, на что тест опирается.
- **TS-25.** Если внешний клиент — `@FeignClient` с `@MockitoBean`, можно без WireMock; но по умолчанию WireMock предпочтительнее (проверяет сериализацию HTTP, заголовки, retry, timeout).

## 8. Что НЕ покрывается интеграционными тестами
**MUST:**
- **TS-26.** Чистая бизнес-логика агрегата — unit-тест без Spring (`new Order(...)`, `order.confirm()`); самые быстрые и многочисленные.
- **TS-27.** Контроллер + сериализация JSON без БД — `@WebMvcTest` + `MockMvc`.
- **TS-28.** E2E через настоящие Kafka/внешние сервисы — отдельная группа `@Tag("e2e")`, отдельный CI-этап, ≤ 5–10 тестов на сервис.
