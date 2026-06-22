---
name: ucp-node-test-design
lang: node
description: Спроектировать тесты NestJS-сервиса (Node) по UCP Test Strategy (коды NODETEST-*) — интеграционные на Postgres через testcontainers-node + supertest, мок внешнего HTTP через nock/msw, без Kafka/Redis, Clock/UuidProvider через overrideProvider.
when_to_use: После нового UseCase/Handler. Триггеры — «тесты для X», «integration-тест на команду Y», «jest для агрегата».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npx*) Bash(jest*) Bash(git diff*)
---

# Проектирование тестов (Node / Jest + testcontainers-node)

Ты пишешь тесты для NestJS-сервиса по `backend/node/node-test-strategy/node-test-strategy-rules.md` (`NODETEST-*`).
Jest — дефолт; Vitest — допустимая альтернатива (правила те же).

## Зависимости

- **`.claude/docs/backend/node/node-test-strategy/node-test-strategy-rules.md`** — правила `NODETEST-*` (код-примеры включены).
- Спека (если есть) — сценарии из use case-ов (UC-N) и бизнес-правил (BR-N).
- Парные: `backend/usecase-pattern/node/...` (Handler/Dispatcher/порты), `backend/node/typeorm/typeorm-rules.md` (`R-TYPEORM-REPO-4`), `backend/node/nest-bootstrap/nest-bootstrap-rules.md` (`NESTBOOT-*` профиль `integration-test`, `Clock`/`UuidProvider`).

## Инструкции

1. **Прочти** `node-test-strategy-rules.md` (`NODETEST-*`). Коды правил в тестах НЕ цитируй; цитата BR/UC в `describe`/`it` допустима (бизнес-описание).

2. **Определи слой** и назови его в начале ответа:
   - **Unit** (без Nest) — чистая логика агрегата/VO: `new Order(...)`, `order.confirm()` (`NODETEST-26`).
   - **Контроллер без БД** — TestingModule + supertest с override порта-репозитория на in-memory фейк (`NODETEST-27`).
   - **Интеграционный** — `Test.createTestingModule(...)` + `app.init()` + supertest + Postgres testcontainers-node (`NODETEST-1`).
   - **E2E** — отдельный jest-проект/тег, реальные Kafka/внешние, ≤ 5–10 на сервис, отдельный CI-этап (`NODETEST-28`).

3. **Если setup ещё нет** — создай платформенный test-setup (`NODETEST-4..8`): jest `globalSetup` с `PostgreSqlContainer` (образ публичный `postgres:16`), стартует один раз на прогон, DSN — через env/`ConfigService`-override; фабрика TestingModule + `app.init()` в `beforeAll`, `app.close()` в `afterAll`; `.overrideProvider(CLOCK)`/`.overrideProvider(UUID_PROVIDER)` на фейки с предзаданными значениями; override JWT-стратегии/guard'а + хелпер `successToken()`. **Без** Kafka/Redis (`NODETEST-19/20`).

4. **`<Domain>DatabasePreparer`** (`NODETEST-9..11`) — над connection/query-runner: `clear*()` (`DELETE`/`TRUNCATE`), `create*(...)`, `prepare()`. Схему не пересоздавать — стоит один раз через миграции. Учесть порядок FK.

5. **Fluent builders** (`NODETEST-12..14`) — `with*()` + `build()`; дефолты (валидный UUID, UTC-время); БД-`timestamptz` хранит микросекунды, JS `Date` — миллисекунды: сравнивать через ISO-строку/`getTime()` с усечением.

6. **Каждый тест** — AAA, имя `it('<action> when <condition> — <expected>')`, BR-код из спеки в `describe`/`it`; вызов через `supertest(app.getHttpServer()).post(...)`; JWT через хелпер; общий setup-хелпер, не сборка TestingModule в каждом файле (`NODETEST-15..18`).

7. **Покрытие:** на каждый UC — happy + альтернативы + ошибки; на каждый BR — отдельный тест; на каждое доменное событие — проверка строки в Outbox через preparer (`NODETEST-19`); на каждый код ошибки — проверка problem+json (`status`/`code`). Consumer/relay — прямым вызовом handler'а, синхронно (`NODETEST-21/22`).

8. **Внешний HTTP** (`NODETEST-23..25`) — только если есть outbound-вызовы: `nock`/`msw`, base-url через конфиг-override, стабы в самом тесте, `nock.cleanAll()` в `afterEach`; WireMock-контейнер — когда проверяем сериализацию/заголовки/retry/timeout.

9. **Самопроверка** + предложи `ucp-node-test-review`.

## Антипаттерны, которые НЕ генерировать

- `setTimeout`-ожидание/polling в тесте (`NODETEST-X1`) — таймерная логика через `jest.useFakeTimers()` + `advanceTimersByTime`; реальные `new Date()`/`randomUUID()` вместо DI-override (`NODETEST-X2`).
- `synchronize: true`/drop-and-create схемы между тестами (`NODETEST-X3`); Testcontainers Kafka/Redis в базовом тесте (`NODETEST-X4`).
- `jest.mock()`/`overrideProvider` на Handler/Aggregate/порт-репозиторий в интеграционном (`NODETEST-X5`) — мокать только внешние границы.
- Сборка JWT руками / живой Keycloak (`NODETEST-X6`); внутренние Docker-регистры в публикуемых примерах.

После работы скилла — обязательно `ucp-node-test-review`.

$ARGUMENTS
