---
name: ucp-node-test-review
lang: node
description: Ревью тестов NestJS-сервиса (Node) по UCP Test Strategy (коды NODETEST-*) — выбор слоя, детерминизм (время/UUID через overrideProvider, без setTimeout), Postgres testcontainers-node + supertest, мок внешних границ, покрытие UC/BR.
when_to_use: Свеженаписанные тесты (*.spec.ts, test-setup, globalSetup) или онбординг модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тестов (Node / Jest + testcontainers-node)

Ты ревьюишь тесты NestJS-сервиса на соответствие `backend/node/node-test-strategy/node-test-strategy-rules.md` (`NODETEST-*`).
Главные точки: правильный слой, детерминизм, базовый setup без Kafka/Redis, мок только внешних границ, покрытие UC/BR.

## Зависимости

- **`.claude/docs/backend/node/node-test-strategy/node-test-strategy-rules.md`** — правила `NODETEST-*` (код-примеры включены).
- Спека (если есть) — UC-/BR-коды, цитируются в `describe`/`it`.
- Парные: `backend/usecase-pattern/node/...` (что на каком слое тестируется), `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-REPO-4`), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-*` профиль/`Clock`/`UuidProvider`).

## Инструкции

1. **Прочти** `node-test-strategy-rules.md`. Цитируй конкретные коды (`NODETEST-19`, `NODETEST-X1`), не префикс.

2. **Скоп.** `test/**`, `**/*.spec.ts`/`*.e2e-spec.ts`, jest-конфиг и `globalSetup`, файлы с импортами `@testcontainers/postgresql`, `supertest`, `nock`/`msw`, preparer/builder; `git diff` на `.ts`.

3. **Прогон.**
   - **Слой:** интеграционный — `Test.createTestingModule` + `app.init()` + supertest + Postgres testcontainers-node (`NODETEST-1`)? Чистая логика агрегата как unit без Nest (`NODETEST-26`)? Контроллер-без-БД через override порта на in-memory фейк (`NODETEST-27`)? E2E — отдельный jest-проект/тег (`NODETEST-28`)? Pure-unit, написанный как интеграционный → раздувает CI.
   - **Детерминизм:** нет `setTimeout`-ожиданий/while-poll (`NODETEST-X1`; таймерная логика — `jest.useFakeTimers()` + `advanceTimersByTime`)? Время/UUID через `.overrideProvider(CLOCK)`/`.overrideProvider(UUID_PROVIDER)`, не реальные `new Date()`/`randomUUID()` (`NODETEST-7`/`X2`)?
   - **Setup:** `PostgreSqlContainer` в `globalSetup`, один на прогон, образ публичный (`postgres:16`), DSN через env/`ConfigService`-override (`NODETEST-5`)? Дорогой setup в `beforeAll`, `app.close()` в `afterAll` (`NODETEST-6`)? Тестовый JWT — фейк-стратегия/guard + `successToken()`, не сборка руками/живой Keycloak (`NODETEST-8`/`X6`)?
   - **DatabasePreparer:** per-BC, `clear*`/`create*`/`prepare`, только `DELETE`/`TRUNCATE` (не `synchronize: true`/drop-and-create между тестами → `NODETEST-X3`), порядок FK (`NODETEST-9..11`).
   - **Builders:** fluent `with*()`+`build()`, дефолты, сравнение времени с `timestamptz` через ISO-строку/`getTime()` с усечением до миллисекунд (`NODETEST-12..14`).
   - **Структура:** AAA, имя `it('<action> when <condition> — <expected>')`, BR-код в `describe`/`it`, вызов через `supertest(app.getHttpServer())`, общий setup-хелпер, JWT через хелпер (`NODETEST-15..18`). Коды правил в комментариях кода — нет (цитата BR/UC — ок).
   - **Kafka/Redis/async:** нет Testcontainers Kafka/Redis в базовом setup (`NODETEST-X4`); события проверяются в Outbox через preparer (`NODETEST-19`); Redis off конфигом (`NODETEST-20`); consumer тестируется прямым `await handler.handle(testEvent)` (`NODETEST-21`); outbox-relay — синхронно, без ожидания `@Interval`-джобы (`NODETEST-22`).
   - **Внешний HTTP:** `nock`/`msw` (или WireMock-контейнер для сериализации/retry/timeout), стабы в самом тесте, `nock.cleanAll()` в `afterEach`, base-url через override (`NODETEST-23..25`).
   - **Моки:** `jest.mock()`/`overrideProvider` на Handler/Aggregate/порт-репозиторий в интеграционном → `NODETEST-X5` (мокать только внешние границы).

4. **Покрытие:** на каждый UC из спеки — happy + альтернативы + ошибки; на каждый BR — отдельный тест с кодом в `it`; на каждое событие — проверка строки в Outbox; на каждый код ошибки — problem+json. Пропущенные UC-/BR — findings.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `setTimeout`/polling в тесте (`NODETEST-X1`), мок своей бизнес-логики (`NODETEST-X5`), реальные `new Date()`/`randomUUID()` в домене (`NODETEST-X2`/`NODETEST-7`), Testcontainers Kafka/Redis в базовом setup (`NODETEST-X4`), внутренний Docker-registry в коммитимых тестах.
   - **Предупреждение** — `synchronize: true`/drop-and-create между тестами (`NODETEST-X3`), pure-unit как интеграционный (`NODETEST-26`), JWT руками/живой Keycloak (`NODETEST-X6`), сравнение `Date` с `timestamptz` «как есть» (`NODETEST-14`), TestingModule руками в каждом файле (`NODETEST-15`).
   - **Замечание** — `it` без BR-/UC-кода при наличии в спеке (`NODETEST-16`), стабы в общих файлах вместо теста (`NODETEST-24`), нет говорящего имени теста.

## Что не входит

- Дизайн новых тестов — `ucp-node-test-design`. Бизнес-логика UseCase/Handler — `ucp-node-pattern-review`.
- TypeORM-запросы в preparer — `ucp-node-typeorm-review`. Типы колонок — `ucp-pg-schema-review`.
- Bootstrap профиля `integration-test` — `ucp-node-bootstrap-review`.

$ARGUMENTS
