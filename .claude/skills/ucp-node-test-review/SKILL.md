---
name: ucp-node-test-review
lang: node
description: Ревью тестов NestJS-сервиса (Node) по UCP Test Strategy (требования node-test-strategy/*) — выбор слоя, детерминизм (время/UUID через overrideProvider, без setTimeout), Postgres testcontainers-node + supertest, мок внешних границ, покрытие UC/BR.
when_to_use: Свеженаписанные тесты (*.spec.ts, test-setup, globalSetup) или онбординг модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тестов (Node / Jest + testcontainers-node)

Ты ревьюишь тесты NestJS-сервиса на соответствие `backend/node/node-test-strategy/spec.md` (`NODETEST-*`).
Главные точки: правильный слой, детерминизм, базовый setup без Kafka/Redis, мок только внешних границ, покрытие UC/BR.

## Зависимости

- **`.claude/docs/backend/node/node-test-strategy/spec.md`** — правила `NODETEST-*` (код-примеры включены).
- Спека (если есть) — UC-/BR-коды, цитируются в `describe`/`it`.
- Парные: `backend/usecase-pattern/node/...` (что на каком слое тестируется), `backend/node/typeorm/spec.md` (`typeorm/repository-integration-tested`), `backend/node/nest-bootstrap/spec.md` (`NESTBOOT-*` профиль/`Clock`/`UuidProvider`).

## Инструкции

1. **Прочти** `node-test-strategy/spec.md`. Цитируй конкретные коды (`node-test-strategy/no-broker-or-cache`, `node-test-strategy/tests-are-deterministic`), не префикс.

2. **Скоп.** `test/**`, `**/*.spec.ts`/`*.e2e-spec.ts`, jest-конфиг и `globalSetup`, файлы с импортами `@testcontainers/postgresql`, `supertest`, `nock`/`msw`, preparer/builder; `git diff` на `.ts`.

3. **Прогон.**
   - **Слой:** интеграционный — `Test.createTestingModule` + `app.init()` + supertest + Postgres testcontainers-node (`node-test-strategy/integration-test-shape`)? Чистая логика агрегата как unit без Nest (`node-test-strategy/test-layers-separated`)? Контроллер-без-БД через override порта на in-memory фейк (`node-test-strategy/test-layers-separated`)? E2E — отдельный jest-проект/тег (`node-test-strategy/test-layers-separated`)? Pure-unit, написанный как интеграционный → раздувает CI.
   - **Детерминизм:** нет `setTimeout`-ожиданий/while-poll (`node-test-strategy/tests-are-deterministic`; таймерная логика — `jest.useFakeTimers()` + `advanceTimersByTime`)? Время/UUID через `.overrideProvider(CLOCK)`/`.overrideProvider(UUID_PROVIDER)`, не реальные `new Date()`/`randomUUID()` (`node-test-strategy/tests-are-deterministic`/`X2`)?
   - **Setup:** `PostgreSqlContainer` в `globalSetup`, один на прогон, образ публичный (`postgres:16`), DSN через env/`ConfigService`-override (`node-test-strategy/setup-runs-once`)? Дорогой setup в `beforeAll`, `app.close()` в `afterAll` (`node-test-strategy/setup-runs-once`)? Тестовый JWT — фейк-стратегия/guard + `successToken()`, не сборка руками/живой Keycloak (`node-test-strategy/test-auth-single-source`/`X6`)?
   - **DatabasePreparer:** per-BC, `clear*`/`create*`/`prepare`, только `DELETE`/`TRUNCATE` (не `synchronize: true`/drop-and-create между тестами → `node-test-strategy/schema-once-data-cleaned`), порядок FK (`NODETEST-9..11`).
   - **Builders:** fluent `with*()`+`build()`, дефолты, сравнение времени с `timestamptz` через ISO-строку/`getTime()` с усечением до миллисекунд (`NODETEST-12..14`).
   - **Структура:** AAA, имя `it('<action> when <condition> — <expected>')`, BR-код в `describe`/`it`, вызов через `supertest(app.getHttpServer())`, общий setup-хелпер, JWT через хелпер (`NODETEST-15..18`). Коды правил в комментариях кода — нет (цитата BR/UC — ок).
   - **Kafka/Redis/async:** нет Testcontainers Kafka/Redis в базовом setup (`node-test-strategy/no-broker-or-cache`); события проверяются в Outbox через preparer (`node-test-strategy/no-broker-or-cache`); Redis off конфигом (`node-test-strategy/no-broker-or-cache`); consumer тестируется прямым `await handler.handle(testEvent)` (`node-test-strategy/no-broker-or-cache`); outbox-relay — синхронно, без ожидания `@Interval`-джобы (`node-test-strategy/no-broker-or-cache`).
   - **Внешний HTTP:** `nock`/`msw` (или WireMock-контейнер для сериализации/retry/timeout), стабы в самом тесте, `nock.cleanAll()` в `afterEach`, base-url через override (`NODETEST-23..25`).
   - **Моки:** `jest.mock()`/`overrideProvider` на Handler/Aggregate/порт-репозиторий в интеграционном → `node-test-strategy/no-mocking-business-logic` (мокать только внешние границы).

4. **Покрытие:** на каждый UC из спеки — happy + альтернативы + ошибки; на каждый BR — отдельный тест с кодом в `it`; на каждое событие — проверка строки в Outbox; на каждый код ошибки — problem+json. Пропущенные UC-/BR — findings.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `setTimeout`/polling в тесте (`node-test-strategy/tests-are-deterministic`), мок своей бизнес-логики (`node-test-strategy/no-mocking-business-logic`), реальные `new Date()`/`randomUUID()` в домене (`node-test-strategy/tests-are-deterministic`/`node-test-strategy/tests-are-deterministic`), Testcontainers Kafka/Redis в базовом setup (`node-test-strategy/no-broker-or-cache`), внутренний Docker-registry в коммитимых тестах.
   - **Предупреждение** — `synchronize: true`/drop-and-create между тестами (`node-test-strategy/schema-once-data-cleaned`), pure-unit как интеграционный (`node-test-strategy/test-layers-separated`), JWT руками/живой Keycloak (`node-test-strategy/test-auth-single-source`), сравнение `Date` с `timestamptz` «как есть» (`node-test-strategy/builders-and-time-precision`), TestingModule руками в каждом файле (`node-test-strategy/test-uses-shared-helper`).
   - **Замечание** — `it` без BR-/UC-кода при наличии в спеке (`node-test-strategy/test-name-states-scenario`), стабы в общих файлах вместо теста (`node-test-strategy/external-calls-are-stubbed`), нет говорящего имени теста.

## Что не входит

- Дизайн новых тестов — `ucp-node-test-design`. Бизнес-логика UseCase/Handler — `ucp-node-pattern-review`.
- TypeORM-запросы в preparer — `ucp-node-typeorm-review`. Типы колонок — `ucp-pg-schema-review`.
- Bootstrap профиля `integration-test` — `ucp-node-bootstrap-review`.

$ARGUMENTS
