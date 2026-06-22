# Node Test Strategy — индекс правил (NestJS/Jest)

> **Что это.** Стратегия тестов NestJS-сервиса по UCP: интеграционные на реальном Postgres через
> testcontainers-node, внешний HTTP замокан, без Kafka/Redis. Языко-специфичный concern (аналог Java
> `test-strategy` / `TS-*`, Python `python-test-strategy` / `PYTS-*`) — **только Node**, своя пара кодов
> `NODETEST-*`. Скиллы читают этот файл; код-примеры включены (отдельного style-guide нет). Jest — дефолт
> NestJS; Vitest — допустимая альтернатива (правила те же, fake timers и DI-override эквивалентны).
> Коды: `NODETEST-<N>` — обязательно, `NODETEST-X<N>` — антипаттерн (запрещено).
> Связанные: `TS-*` (Java-аналог интента), `R-ERR-*` (Exception Filters на edge), `AUTH-19` (Idempotency-Key), PostgreSQL — `pg-*-rules.md`.

Базовый принцип (`NODETEST-1`): **тест быстрый и детерминированный**. Если тест требует Kafka/Redis/несколько контейнеров и polling-ожидание — это инфраструктурный smoke, не тест на бизнес-логику.

## 1. Базовые правила
**MUST:**
- **NODETEST-1.** Интеграционный тест — приложение через `Test.createTestingModule({...}).compile()` + `app.init()` + вызов по HTTP через supertest + реальный PostgreSQL (testcontainers-node); внешний HTTP — мок (раздел 7); Kafka/Redis — выключены конфигом `integration-test`.
- **NODETEST-2.** Тесты детерминированы: никаких `setTimeout`-ожиданий/polling; время и UUID фиксированы через DI-провайдеры `Clock`/`UuidProvider` с override в TestingModule (`NODETEST-7`).
- **NODETEST-3.** Один тест — один сценарий, AAA-структура (Arrange → Act → Assert).

**MUST NOT:**
- **NODETEST-X1.** `await new Promise(r => setTimeout(r, ...))`/while-poll в тесте — признак недетерминированного дизайна; если логика на таймерах — `jest.useFakeTimers()` + `advanceTimersByTime`, не реальное ожидание.
- **NODETEST-X2.** Реальные `new Date()`/`randomUUID()` в тесте вместо детерминированного DI-override.

## 2. Базовый слой (TestingModule)
**MUST:**
- **NODETEST-4.** Один платформенный test-setup на сервис (фабрика TestingModule + globalSetup для testcontainers) + доменные хелперы на каждый Bounded Context.
- **NODETEST-5.** `PostgreSqlContainer` стартует один раз на прогон (jest `globalSetup`); DSN прокидывается в конфиг через env/`ConfigService`-override, не хардкодом.
- **NODETEST-6.** Дорогой setup (container, schema, `app.init()`) — `beforeAll`, не `beforeEach`; `app.close()` в `afterAll`.
- **NODETEST-7.** Время и UUID — кастомные провайдеры (токены `CLOCK`, `UUID_PROVIDER`), в тесте `.overrideProvider(CLOCK).useValue(fixedClock)`; никаких `new Date()`/`randomUUID()` в домене напрямую.
- **NODETEST-8.** Тестовая авторизация — override JWT-стратегии/guard'а на фейк + хелпер `successToken()`; единый source-of-truth, не сборка токенов в каждом тесте (cross-ref `AUTH-17`).

## 3. DatabasePreparer — fluent setup БД
**MUST:**
- **NODETEST-9.** На каждый Bounded Context — свой `<Domain>DatabasePreparer` над connection/query-runner с группами `clear*()`, `create*(...)`, `prepare()`.
- **NODETEST-10.** Не пересоздаём схему между тестами — только `DELETE`/`TRUNCATE` нужных таблиц (мс vs секунды); схема — один раз при старте через миграции.
- **NODETEST-11.** Порядок методов в `prepare()` — порядок вызова; при FK учитывать (FK последним создаём, первым чистим).

**MUST NOT:**
- **NODETEST-X3.** `synchronize: true`/drop-and-create схемы между тестами — медленно и маскирует миграционные баги.

## 4. Fluent builders
**MUST:**
- **NODETEST-12.** На сущность/таблицу — builder с `with*()` и `build()`.
- **NODETEST-13.** Разумные дефолты в builder'е (валидный UUID, UTC-время); в тесте перезаписываем только важное для сценария.
- **NODETEST-14.** Сравнение времени с БД — в UTC и с учётом точности: PostgreSQL `timestamptz` хранит микросекунды, JS `Date` — миллисекунды; усекаем БД-значение до миллисекунд (ISO-строка/`getTime()`), не сравниваем объекты «как есть».

## 5. Структура одного теста
**MUST:**
- **NODETEST-15.** Тест использует общий setup-хелпер (app + preparer из фабрики), не собирает TestingModule руками в каждом файле.
- **NODETEST-16.** Имена: `it('<action> when <condition> — <expected>')`; цитата BR-кода из спеки — в `describe`/`it`.
- **NODETEST-17.** Вызов через `supertest(app.getHttpServer()).post(...)` (контроль метода/заголовков/тела); юнит контроллера без БД — override порта-репозитория на in-memory фейк.
- **NODETEST-18.** JWT — через хелпер (`successToken()`/`customerToken(...)`), не собираем токены руками.

## 6. Kafka, Redis, async — по умолчанию НЕТ
**MUST:**
- **NODETEST-19.** Не поднимаем Kafka в интеграционных — события в Outbox-таблице, проверяем содержимое через `DatabasePreparer`.
- **NODETEST-20.** Redis не поднимаем — конфиг `integration-test` отключает кеш (in-memory/none).
- **NODETEST-21.** Idempotent consumer — тестируем handler напрямую как провайдер (`await handler.handle(testEvent)`), без брокера и microservices-транспорта.
- **NODETEST-22.** Async/outbox-relay — переводим в синхрон: ручной commit + прямой вызов relay/handler, не ждём фонового воркера/`@Interval`-джобы.

**MUST NOT:**
- **NODETEST-X4.** Testcontainers Kafka/Redis в базовом интеграционном тесте — раздувает время, превращает в smoke.

## 7. Внешние HTTP — мок
**MUST:**
- **NODETEST-23.** Внешний REST (платёж, каталог, логистика) — `nock` или `msw` (node-интерсептор); base-url клиента — через конфиг-override.
- **NODETEST-24.** Стабы пишем в самом тесте, не в общих файлах — видно, на что тест опирается; `nock.cleanAll()` в `afterEach`.
- **NODETEST-25.** Реальный локальный HTTP-сервер (WireMock-контейнер) предпочтительнее интерсептора, когда проверяем сериализацию, заголовки, retry, timeout (cross-ref `R-RES-*`).

## 8. Что НЕ покрывается интеграционными тестами
**MUST:**
- **NODETEST-26.** Чистая доменная логика агрегата — unit без Nest (`new Order(...)`, `order.confirm()`); самые быстрые и многочисленные.
- **NODETEST-27.** Контроллер + сериализация без БД — TestingModule + supertest с override порта-репозитория на in-memory фейк.
- **NODETEST-28.** E2E через настоящие Kafka/внешние сервисы — отдельный jest-проект/тег, отдельный CI-этап, ≤ 5–10 на сервис.

**MUST NOT:**
- **NODETEST-X5.** Мокать бизнес-логику (Handler/Aggregate/порт-репозиторий) через `jest.mock()`/`overrideProvider` в интеграционном тесте — он проверяет реальный путь; мок допустим только для внешней системы.
- **NODETEST-X6.** Сборка JWT руками или живой Keycloak в тесте — только фейковый валидатор/токен-хелпер (`NODETEST-8`).
