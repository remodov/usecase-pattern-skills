# Python Test Strategy — индекс правил (pytest + Testcontainers)

> **Что это.** Стратегия тестов FastAPI-сервиса по UCP: интеграционные на реальном Postgres через
> Testcontainers, внешний HTTP замокан, без Kafka/Redis. Языко-специфичный concern (аналог Java
> `test-strategy` / `TS-*`) — **только Python**, своя пара кодов `PYTS-*`. Скиллы читают этот файл;
> код-примеры включены (отдельного style-guide нет). PostgreSQL-правила (типы/индексы) — `pg-*-rules.md`.
> Коды: `PYTS-<N>` — обязательно, `PYTS-X<N>` — антипаттерн (запрещено).
> Связанные: `R-PATT-*`/`R-HND-*` (UseCase покрыт интеграционным), `R-AGG-*` (unit на инварианты), `R-SQLA-REPO-4` (репозиторий против Testcontainers), `R-RES-*`/httpx-клиенты (мок внешнего HTTP), `AUTH-19` (Idempotency-Key).

Базовый принцип (`PYTS-1`): **тест быстрый и детерминированный**. Если тест требует Kafka/Redis/несколько контейнеров и polling-ожидание — это инфраструктурный smoke, не тест на бизнес-логику.

## 1. Базовые правила
**MUST:**
- **PYTS-1.** Интеграционный тест — ASGI-приложение через `httpx.AsyncClient(transport=ASGITransport(app))` + реальный PostgreSQL (Testcontainers) + вызов роутера по HTTP; внешний HTTP — мок (раздел 7); Kafka/Redis — выключены профилем `integration-test`.
- **PYTS-2.** Тесты детерминированы: никаких `asyncio.sleep`/polling-циклов/`tenacity`-ожиданий ради «дождаться»; время и UUID — фиксированы через `dependency_overrides` на `Clock`/`IdGenerator` (`PYTS-7`).
- **PYTS-3.** Один тест — один сценарий, AAA-структура (Arrange → Act → Assert).

**MUST NOT:**
- **PYTS-X1.** `asyncio.sleep`/while-poll/`Awaitility`-аналоги в тесте — признак недетерминированного дизайна.
- **PYTS-X2.** Реальные `datetime.now()`/`uuid4()` в тесте вместо детерминированного DI-override.

## 2. Фикстуры (базовый слой)
**MUST:**
- **PYTS-4.** Один платформенный набор фикстур на сервис (`conftest.py`) + доменные фикстуры на каждый Bounded Context (свои `DatabasePreparer`-ы).
- **PYTS-5.** `PostgresContainer` — session-scoped фикстура; DSN прокидывается в `Settings`/engine через `dependency_overrides` или env, не хардкодом.
- **PYTS-6.** `pytest-asyncio` (`asyncio_mode=auto` или `@pytest.mark.asyncio`); дорогой setup (container, schema) — session/module-scope, не per-test.
- **PYTS-7.** Время и UUID — `app.dependency_overrides[get_clock]`/`[get_id_generator]` на фейки с предзаданными значениями; никаких `datetime.now()`/`uuid4()` в домене (cross-ref `PYBOOT-X3`).
- **PYTS-8.** Тестовая авторизация — override `get_principal`/JWT-валидатора на фейк + хелпер `success_token()`; единый source-of-truth, не сборка токенов в каждом тесте (cross-ref `AUTH-17`).

## 3. DatabasePreparer — fluent setup БД
**MUST:**
- **PYTS-9.** На каждый Bounded Context — свой `<Domain>DatabasePreparer` над `AsyncSession`/Core с группами `clear*()`, `create*(...)`, `prepare()`.
- **PYTS-10.** Не пересоздаём схему между тестами — только `DELETE`/`TRUNCATE` нужных таблиц (мс vs секунды); схема — один раз при старте через Liquibase (cross-ref `R-SQLA-MIG-1`).
- **PYTS-11.** Порядок методов в `prepare()` — порядок вызова; при FK учитывать (FK последним создаём, первым чистим).

**MUST NOT:**
- **PYTS-X3.** `Base.metadata.create_all()`/`drop_all()` между тестами — схема стоит один раз; пересоздание медленно и маскирует миграционные баги.

## 4. ObjectGenerator — fluent builders
**MUST:**
- **PYTS-12.** На сущность/таблицу — builder с `with_*` и `build()`/`generate()`.
- **PYTS-13.** Разумные дефолты в генераторе (валидный UUID, tz-aware время); в тесте перезаписываем только важное для сценария.
- **PYTS-14.** Время — `datetime(..., tzinfo=UTC)` с усечением до микросекунд при сравнении с БД (PostgreSQL `timestamptz` хранит микросекунды; naive-datetime → расхождение).

## 5. Структура одного теста
**MUST:**
- **PYTS-15.** Тест использует общий `AsyncClient`-фикстуру + `DatabasePreparer` (через DI-фикстуры), не поднимает приложение руками.
- **PYTS-16.** Имена: `test_<action>_when_<condition>_<expected>`; docstring с цитатой BR-кода из спеки.
- **PYTS-17.** Вызов через `await client.post(...)`/`.request(...)` (контроль метода/заголовков/тела); юнит контроллера без БД — `AsyncClient` с override порта-репозитория на фейк.
- **PYTS-18.** JWT — через хелпер-фикстуру (`success_token()`/`customer_token(...)`), не собираем токены руками.

## 6. Kafka, Redis, async — по умолчанию НЕТ
**MUST:**
- **PYTS-19.** Не поднимаем Kafka в интеграционных — события в Outbox-таблице, проверяем содержимое через `DatabasePreparer`.
- **PYTS-20.** Redis не поднимаем — профиль `integration-test` отключает кеш (cache backend = none/in-memory).
- **PYTS-21.** Idempotent consumer — тестируем handler напрямую как объект (`await event_handler.handle(test_event)`), без брокера.
- **PYTS-22.** Async/outbox-relay — переводим в синхрон: ручной `commit` + прямой вызов relay/handler, не ждём фонового воркера.

**MUST NOT:**
- **PYTS-X4.** Testcontainers Kafka/Redis в базовом интеграционном тесте — раздувает время, превращает в smoke.

## 7. Внешние HTTP — мок
**MUST:**
- **PYTS-23.** Внешний REST (платёж, каталог, логистика) — реальный локальный HTTP-сервер (`pytest-httpserver` / WireMock-контейнер) в фикстуре; base-url клиента → на него через override.
- **PYTS-24.** Стабы пишем в самом тесте, не в общих файлах — видно, на что тест опирается.
- **PYTS-25.** `respx` (мок httpx на transport-уровне) допустим как лёгкий вариант, но реальный HTTP-сервер предпочтительнее: проверяет сериализацию, заголовки, retry, timeout (cross-ref `R-RES-*`).

## 8. Что НЕ покрывается интеграционными тестами
**MUST:**
- **PYTS-26.** Чистая доменная логика агрегата — unit без фреймворка (`Order(...)`, `order.confirm()`); самые быстрые и многочисленные.
- **PYTS-27.** Контроллер + сериализация без БД — `AsyncClient` + override порта-репозитория на in-memory фейк.
- **PYTS-28.** E2E через настоящие Kafka/внешние сервисы — отдельная группа (`@pytest.mark.e2e`), отдельный CI-этап, ≤ 5–10 на сервис.

**MUST NOT:**
- **PYTS-X5.** Мокать бизнес-логику (Handler/Aggregate/порт-репозиторий) через `MagicMock` в интеграционном тесте — он проверяет реальный путь; мок допустим только для внешней системы.
- **PYTS-X6.** Сборка JWT руками или живой Keycloak в тесте — только фейковый валидатор/токен-хелпер (`PYTS-8`).
