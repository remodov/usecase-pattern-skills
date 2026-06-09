---
name: ucp-py-test-design
lang: python
description: Спроектировать тесты FastAPI-сервиса (Python) по UCP Test Strategy (коды PYTS-*) — интеграционные на Postgres через Testcontainers + httpx.AsyncClient(ASGITransport), мок внешнего HTTP, без Kafka/Redis, Clock/IdGenerator через dependency_overrides.
when_to_use: После нового UseCase/Handler. Триггеры — «тесты для X», «integration-тест на команду Y», «pytest для агрегата».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(git diff*)
---

# Проектирование тестов (Python / pytest + Testcontainers)

Ты пишешь тесты для FastAPI-сервиса по `backend/python/python-test-strategy/python-test-strategy-rules.md` (`PYTS-*`).

## Зависимости

- **`.claude/docs/backend/python/python-test-strategy/python-test-strategy-rules.md`** — правила `PYTS-*` (код-примеры включены).
- Спека (если есть) — сценарии из use case-ов (UC-N) и бизнес-правил (BR-N).
- Парные: `backend/usecase-pattern/python/...` (Handler/UoW/Dispatcher/порты), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-REPO-4`), `backend/python/python-bootstrap/...` (`PYBOOT-*` профиль `integration-test`, `Clock`/`IdGenerator`).

## Инструкции

1. **Прочти** `python-test-strategy-rules.md` (`PYTS-*`). Коды в комментариях тестов НЕ цитируй; в docstring — цитата BR/UC допустима (бизнес-описание).

2. **Определи слой** и назови его в начале ответа:
   - **Unit** (без фреймворка) — чистая логика агрегата/VO: `Order(...)`, `order.confirm()` (`PYTS-26`).
   - **Контроллер без БД** — `AsyncClient` + override порта-репозитория на in-memory фейк (`PYTS-27`).
   - **Интеграционный** — `httpx.AsyncClient(transport=ASGITransport(app))` + Postgres Testcontainers (`PYTS-1`).
   - **E2E** — `@pytest.mark.e2e`, реальные Kafka/внешние, минимум, отдельный CI-этап (`PYTS-28`).

3. **Если фикстур ещё нет** — создай в `conftest.py` (`PYTS-4..8`): session-scoped `PostgresContainer` (образ публичный `postgres:16`), engine/Settings на его DSN; `pytest-asyncio`; `AsyncClient`-фикстура; `app.dependency_overrides` на фейковые `Clock`/`IdGenerator` (предзаданные значения) и `get_principal`/JWT-валидатор + `success_token()`. **Без** Kafka/Redis (`PYTS-19/20`).

4. **`<Domain>DatabasePreparer`** (`PYTS-9..11`) — над `AsyncSession`/Core: `clear*()` (`DELETE`/`TRUNCATE`), `create*(...)`, `prepare()`. Схему не пересоздавать — стоит один раз через Alembic. Учесть порядок FK.

5. **`<Entity>ObjectGenerator`** (`PYTS-12..14`) — `with_*` fluent + `build()`; дефолты (валидный UUID, tz-aware `datetime(..., tzinfo=UTC)`); время усекать до микросекунд для сравнения с `timestamptz`.

6. **Каждый тест** — AAA, имя `test_<action>_when_<condition>_<expected>`, docstring с BR-кодом; вызов через `await client.request(...)`; JWT через хелпер-фикстуру (`PYTS-15..18`).

7. **Покрытие:** на каждый UC — happy + альтернативы + ошибки; на каждый BR — отдельный тест; на каждое доменное событие — проверка строки в Outbox через preparer; на каждый код ошибки — проверка problem+json (`status`/`code`).

8. **Внешний HTTP** (`PYTS-23..25`) — только если есть outbound-вызовы: `pytest-httpserver`/WireMock-контейнер, base-url через override, стабы в самом тесте. `respx` — лёгкий вариант.

9. **Самопроверка** + предложи `ucp-py-test-review`.

## Антипаттерны, которые НЕ генерировать

- `asyncio.sleep`/polling в тесте (`PYTS-X1`); реальные `datetime.now()`/`uuid4()` вместо DI-override (`PYTS-X2`).
- `create_all()`/`drop_all()` между тестами (`PYTS-X3`); Testcontainers Kafka/Redis в базовом тесте (`PYTS-X4`).
- `MagicMock` на Handler/Aggregate/порт-репозиторий в интеграционном (`PYTS-X5`) — мокать только внешние границы.
- Сборка JWT руками / живой Keycloak (`PYTS-X6`); внутренние Docker-регистры в публикуемых примерах.

После работы скилла — обязательно `ucp-py-test-review`.

$ARGUMENTS
