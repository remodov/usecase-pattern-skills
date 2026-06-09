---
name: ucp-py-test-review
lang: python
description: Ревью тестов FastAPI-сервиса (Python) по UCP Test Strategy (коды PYTS-*) — выбор слоя, детерминизм (время/UUID через dependency_overrides, без asyncio.sleep), Postgres Testcontainers + httpx, мок внешних границ, покрытие UC/BR.
when_to_use: Свеженаписанные тесты (tests/**, conftest.py) или онбординг модуля под командный подход к тестированию.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью тестов (Python / pytest + Testcontainers)

Ты ревьюишь тесты FastAPI-сервиса на соответствие `backend/python/python-test-strategy/python-test-strategy-rules.md` (`PYTS-*`).
Главные точки: правильный слой, детерминизм, базовые фикстуры без Kafka/Redis, мок только внешних границ, покрытие UC/BR.

## Зависимости

- **`.claude/docs/backend/python/python-test-strategy/python-test-strategy-rules.md`** — правила `PYTS-*` (код-примеры включены).
- Спека (если есть) — UC-/BR-коды, цитируются в docstring теста.
- Парные: `backend/usecase-pattern/python/...` (что на каком слое тестируется), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-REPO-4`), `backend/python/python-bootstrap/...` (`PYBOOT-*` профиль/`Clock`/`IdGenerator`).

## Инструкции

1. **Прочти** `python-test-strategy-rules.md`. Цитируй конкретные коды (`PYTS-19`, `PYTS-X1`), не префикс.

2. **Скоп.** `tests/**`, `conftest.py`, `*_test.py`/`test_*.py`, файлы с импортами `testcontainers`, `httpx`, `pytest_httpserver`/`respx`, preparer/generator; `git diff` на `.py`.

3. **Прогон.**
   - **Слой:** интеграционный — `AsyncClient(transport=ASGITransport(app))` + Postgres Testcontainers (`PYTS-1`)? Чистая логика агрегата как unit без фреймворка (`PYTS-26`)? Контроллер-без-БД через override порта (`PYTS-27`)? E2E помечен `@pytest.mark.e2e` (`PYTS-28`)? Pure-unit, написанный как интеграционный → раздувает CI.
   - **Детерминизм:** нет `asyncio.sleep`/while-poll/`tenacity`-ожиданий (`PYTS-X1`)? Время/UUID через `dependency_overrides` на `Clock`/`IdGenerator`, не реальные `datetime.now()`/`uuid4()` (`PYTS-7`/`X2`)?
   - **Фикстуры:** `PostgresContainer` session-scoped, образ публичный (`postgres:16`), DSN через override/env (`PYTS-5`)? `pytest-asyncio`, дорогой setup не per-test (`PYTS-6`)? Тестовый JWT — фейк-валидатор + `success_token()`, не сборка руками/живой Keycloak (`PYTS-8`/`X6`)?
   - **DatabasePreparer:** per-BC, `clear*`/`create*`/`prepare`, только `DELETE`/`TRUNCATE` (не `create_all`/`drop_all` между тестами → `PYTS-X3`), порядок FK (`PYTS-9..11`).
   - **ObjectGenerator:** fluent `with_*`+`build()`, дефолты, tz-aware время усечено до микросекунд для `timestamptz` (`PYTS-12..14`).
   - **Структура:** AAA, имя `test_<action>_when_<cond>_<expected>`, docstring с BR-кодом, вызов через `await client.request(...)`, JWT через хелпер (`PYTS-15..18`). Коды правил в комментариях кода — нет (в docstring BR/UC — ок).
   - **Kafka/Redis/async:** нет Testcontainers Kafka/Redis в базовых фикстурах (`PYTS-X4`); события проверяются в Outbox через preparer (`PYTS-19`); consumer/relay тестируется прямым вызовом, без брокера и фонового ожидания (`PYTS-21/22`).
   - **Внешний HTTP:** `pytest-httpserver`/WireMock-контейнер (или `respx`), стабы в самом тесте, base-url через override (`PYTS-23..25`).
   - **Моки:** `MagicMock` на Handler/Aggregate/порт-репозиторий в интеграционном → `PYTS-X5` (мокать только внешние границы).

4. **Покрытие** (`PYTS-15`): на каждый UC из спеки — happy + альтернативы + ошибки; на каждый BR — отдельный тест с кодом в docstring; на каждое событие — проверка строки в Outbox; на каждый код ошибки — problem+json. Пропущенные UC-/BR — findings `PYTS-15`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `asyncio.sleep`/polling в тесте (`PYTS-X1`), `MagicMock` на свою бизнес-логику (`PYTS-X5`), реальные `now()`/`uuid4()` в домене (`PYTS-X2`/`PYTS-7`), Testcontainers Kafka/Redis в базовых фикстурах (`PYTS-X4`), внутренний Docker-registry в коммитимых тестах.
   - **Предупреждение** — `create_all`/`drop_all` между тестами (`PYTS-X3`), pure-unit как интеграционный (`PYTS-26`), JWT руками/живой Keycloak (`PYTS-X6`), нет усечения времени для `timestamptz` (`PYTS-14`).
   - **Замечание** — docstring без BR-/UC-кода при наличии в спеке (`PYTS-16`), стабы в общих файлах вместо теста (`PYTS-24`), нет говорящего имени теста.

## Что не входит

- Дизайн новых тестов — `ucp-py-test-design`. Бизнес-логика UseCase/Handler — `ucp-py-pattern-review`.
- SQLAlchemy-запросы в preparer — `ucp-py-sqlalchemy-review`. Типы колонок — `ucp-pg-schema-review`.
- Bootstrap профиля `integration-test` — `ucp-py-bootstrap-review`.

$ARGUMENTS
