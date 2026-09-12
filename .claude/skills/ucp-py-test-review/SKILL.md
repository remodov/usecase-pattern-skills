---
name: ucp-py-test-review
lang: python
description: Ревью тестов FastAPI-сервиса (Python) по UCP Test Strategy (требования python-test-strategy/*) — выбор слоя, детерминизм (время/UUID через dependency_overrides, без asyncio.sleep), Postgres Testcontainers + httpx, мок внешних границ, покрытие UC/BR.
when_to_use: Свеженаписанные тесты (tests/**, conftest.py) или онбординг модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тестов (Python / pytest + Testcontainers)

Ты ревьюишь тесты FastAPI-сервиса на соответствие `backend/python/python-test-strategy/spec.md` (`PYTS-*`).
Главные точки: правильный слой, детерминизм, базовые фикстуры без Kafka/Redis, мок только внешних границ, покрытие UC/BR.

## Зависимости

- **`.claude/docs/backend/python/python-test-strategy/spec.md`** — правила `PYTS-*` (код-примеры включены).
- Спека (если есть) — UC-/BR-коды, цитируются в docstring теста.
- Парные: `backend/usecase-pattern/python/...` (что на каком слое тестируется), `backend/python/sqlalchemy/spec.md` (`sqlalchemy/repository-integration-tested`), `backend/python/python-bootstrap/...` (`PYBOOT-*` профиль/`Clock`/`IdGenerator`).

## Инструкции

1. **Прочти** `python-test-strategy/spec.md`. Цитируй конкретные коды (`python-test-strategy/no-broker-or-cache-in-integration-tests`, `python-test-strategy/tests-are-deterministic`), не префикс.

2. **Скоп.** `tests/**`, `conftest.py`, `*_test.py`/`test_*.py`, файлы с импортами `testcontainers`, `httpx`, `pytest_httpserver`/`respx`, preparer/generator; `git diff` на `.py`.

3. **Прогон.**
   - **Слой:** интеграционный — `AsyncClient(transport=ASGITransport(app))` + Postgres Testcontainers (`python-test-strategy/integration-test-shape`)? Чистая логика агрегата как unit без фреймворка (`python-test-strategy/test-layers-separated`)? Контроллер-без-БД через override порта (`python-test-strategy/test-layers-separated`)? E2E помечен `@pytest.mark.e2e` (`python-test-strategy/test-layers-separated`)? Pure-unit, написанный как интеграционный → раздувает CI.
   - **Детерминизм:** нет `asyncio.sleep`/while-poll/`tenacity`-ожиданий (`python-test-strategy/tests-are-deterministic`)? Время/UUID через `dependency_overrides` на `Clock`/`IdGenerator`, не реальные `datetime.now()`/`uuid4()` (`python-test-strategy/tests-are-deterministic`/`X2`)?
   - **Фикстуры:** `PostgresContainer` session-scoped, образ публичный (`postgres:16`), DSN через override/env (`python-test-strategy/fixtures-are-layered`)? `pytest-asyncio`, дорогой setup не per-test (`python-test-strategy/fixtures-are-layered`)? Тестовый JWT — фейк-валидатор + `success_token()`, не сборка руками/живой Keycloak (`python-test-strategy/test-auth-single-source`/`X6`)?
   - **DatabasePreparer:** per-BC, `clear*`/`create*`/`prepare`, только `DELETE`/`TRUNCATE` (не `create_all`/`drop_all` между тестами → `python-test-strategy/schema-once-data-cleaned`), порядок FK (`PYTS-9..11`).
   - **ObjectGenerator:** fluent `with_*`+`build()`, дефолты, tz-aware время усечено до микросекунд для `timestamptz` (`PYTS-12..14`).
   - **Структура:** AAA, имя `test_<action>_when_<cond>_<expected>`, docstring с BR-кодом, вызов через `await client.request(...)`, JWT через хелпер (`PYTS-15..18`). Коды правил в комментариях кода — нет (в docstring BR/UC — ок).
   - **Kafka/Redis/async:** нет Testcontainers Kafka/Redis в базовых фикстурах (`python-test-strategy/no-broker-or-cache-in-integration-tests`); события проверяются в Outbox через preparer (`python-test-strategy/no-broker-or-cache-in-integration-tests`); consumer/relay тестируется прямым вызовом, без брокера и фонового ожидания (`PYTS-21/22`).
   - **Внешний HTTP:** `pytest-httpserver`/WireMock-контейнер (или `respx`), стабы в самом тесте, base-url через override (`PYTS-23..25`).
   - **Моки:** `MagicMock` на Handler/Aggregate/порт-репозиторий в интеграционном → `python-test-strategy/no-mocking-business-logic` (мокать только внешние границы).

4. **Покрытие** (`python-test-strategy/test-uses-shared-fixtures`): на каждый UC из спеки — happy + альтернативы + ошибки; на каждый BR — отдельный тест с кодом в docstring; на каждое событие — проверка строки в Outbox; на каждый код ошибки — problem+json. Пропущенные UC-/BR — findings `python-test-strategy/test-uses-shared-fixtures`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `asyncio.sleep`/polling в тесте (`python-test-strategy/tests-are-deterministic`), `MagicMock` на свою бизнес-логику (`python-test-strategy/no-mocking-business-logic`), реальные `now()`/`uuid4()` в домене (`python-test-strategy/tests-are-deterministic`/`python-test-strategy/tests-are-deterministic`), Testcontainers Kafka/Redis в базовых фикстурах (`python-test-strategy/no-broker-or-cache-in-integration-tests`), внутренний Docker-registry в коммитимых тестах.
   - **Предупреждение** — `create_all`/`drop_all` между тестами (`python-test-strategy/schema-once-data-cleaned`), pure-unit как интеграционный (`python-test-strategy/test-layers-separated`), JWT руками/живой Keycloak (`python-test-strategy/test-auth-single-source`), нет усечения времени для `timestamptz` (`python-test-strategy/builders-with-defaults`).
   - **Замечание** — docstring без BR-/UC-кода при наличии в спеке (`python-test-strategy/test-name-states-scenario`), стабы в общих файлах вместо теста (`python-test-strategy/external-calls-via-stub-server`), нет говорящего имени теста.

## Что не входит

- Дизайн новых тестов — `ucp-py-test-design`. Бизнес-логика UseCase/Handler — `ucp-py-pattern-review`.
- SQLAlchemy-запросы в preparer — `ucp-py-sqlalchemy-review`. Типы колонок — `ucp-pg-schema-review`.
- Bootstrap профиля `integration-test` — `ucp-py-bootstrap-review`.

$ARGUMENTS
