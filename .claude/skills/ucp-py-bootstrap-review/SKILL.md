---
name: ucp-py-bootstrap-review
lang: python
description: Ревью bootstrap FastAPI-сервиса по UCP (требования python-bootstrap/*) — профили на pydantic-settings, ресурсы в lifespan, явный DI, Liquibase вместо create_all, health live/ready, чистота core.
when_to_use: Ревью app/main.py, settings.py, container.py, lifespan, конфигурации Liquibase.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью bootstrap (Python / FastAPI)

Ты ревьюишь bootstrap-слой FastAPI-сервиса на соответствие `backend/python/python-bootstrap/spec.md` (`PYBOOT-*`).

## Зависимости

- **`.claude/docs/backend/python/python-bootstrap/spec.md`** — правила `PYBOOT-*`.
- Парные: `backend/validation/python/...` (`BaseSettings`), `backend/usecase-pattern/python/...` (DI/Dispatcher), `backend/error-handling/python/...` (handlers в фабрике), `backend/auth-patterns/spec.md` (`AUTH-16/17`).

## Инструкции

1. **Прочти** `python-bootstrap/spec.md`. Цитируй конкретные коды (`python-bootstrap/resources-in-lifespan`), не префикс.

2. **Скоп.** `app/main.py`, `app/settings.py`/`config.py`, `app/container.py`, lifespan, `liquibase/changelog/`, `pyproject.toml`, `git diff`.

3. **Прогон.**
   - **Конфиг:** `pydantic-settings BaseSettings`, `APP_ENV`, required без default, fail-fast? Секреты не в git? (`PYBOOT-2/4`). `os.getenv` россыпью → `python-bootstrap/single-settings-object`.
   - **Factory/lifespan:** `create_app()`-фабрика (не модуль-глобал app)? Ресурсы в `lifespan`, закрытие там же? (`PYBOOT-5/6`). Engine/клиент на уровне модуля → `python-bootstrap/resources-in-lifespan`.
   - **DI:** контейнер/фабрики (не глобальные синглтоны)? `Clock`/`IdGenerator` за интерфейсом? (`PYBOOT-8/9`). `datetime.now()`/`uuid4()` в домене → `python-bootstrap/clock-and-ids-behind-protocols`.
   - **Persistence:** async engine+sessionmaker в lifespan, сессия per-request; Liquibase, не `create_all` в проде (`python-bootstrap/persistence-wiring`). `Base.metadata.create_all()` в проде → `python-bootstrap/persistence-wiring`.
   - **Server/health:** `/health/live` + `/health/ready` раздельно (`python-bootstrap/liveness-and-readiness-split`). Блокирующий sync-вызов в async без executor → `python-bootstrap/no-blocking-in-async-handlers`.
   - **Observability:** structlog (JSON в проде) + correlation-id middleware; PII не в логах; prometheus/OTel (`python-bootstrap/observability-configured-in-factory`, cross-ref `auth-patterns/no-pii-in-logs-and-events`).
   - **Структура:** `core/` не импортит `app/`/`adapters`/FastAPI/SQLAlchemy (`python-bootstrap/layout-directs-dependencies-inward`/`X6`, cross-ref `hexagonal/core-free-of-framework`).

4. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

5. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — ресурс/engine в глобале (`python-bootstrap/resources-in-lifespan`), `create_all` в проде (`python-bootstrap/persistence-wiring`), блокирующий sync в async (`python-bootstrap/no-blocking-in-async-handlers`), `core/` импортит фреймворк (`python-bootstrap/layout-directs-dependencies-inward`), секрет в git.
   - **Предупреждение** — `os.getenv` вместо Settings (`python-bootstrap/single-settings-object`), `datetime.now()`/`uuid4()` в домене (`python-bootstrap/clock-and-ids-behind-protocols`), нет раздельных health, app — модуль-глобал.
   - **Замечание** — нет README quickstart, mypy/ruff не в CI.

## Что не входит

- Бизнес-операции — `ucp-py-pattern-review`. Обработка ошибок — `ucp-py-error-handling-review`. Валидация — `ucp-py-validation-review`.

$ARGUMENTS
