---
name: ucp-py-bootstrap-review
lang: python
description: Ревью bootstrap FastAPI-сервиса по UCP — профили через pydantic-settings (fail-fast, не os.getenv), app factory + lifespan (ресурсы не в глобале), DI явный, async SQLAlchemy + Liquibase (не create_all в проде), health live/ready, нет блокирующих вызовов в async, core/ без FastAPI/SQLAlchemy. Опирается на коды PYBOOT-*. Вызывается на ревью app/main.py, settings.py, container.py, lifespan, Liquibase-конфига.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью bootstrap (Python / FastAPI)

Ты ревьюишь bootstrap-слой FastAPI-сервиса на соответствие `backend/python/python-bootstrap/python-bootstrap-rules.md` (`PYBOOT-*`).

## Зависимости

- **`.claude/docs/backend/python/python-bootstrap/python-bootstrap-rules.md`** — правила `PYBOOT-*`.
- Парные: `backend/validation/python/...` (`BaseSettings`), `backend/usecase-pattern/python/...` (DI/Dispatcher), `backend/error-handling/python/...` (handlers в фабрике), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-16/17`).

## Инструкции

1. **Прочти** `python-bootstrap-rules.md`. Цитируй конкретные коды (`PYBOOT-X2`), не префикс.

2. **Скоп.** `app/main.py`, `app/settings.py`/`config.py`, `app/container.py`, lifespan, `liquibase/changelog/`, `pyproject.toml`, `git diff`.

3. **Прогон.**
   - **Конфиг:** `pydantic-settings BaseSettings`, `APP_ENV`, required без default, fail-fast? Секреты не в git? (`PYBOOT-2/4`). `os.getenv` россыпью → `PYBOOT-X1`.
   - **Factory/lifespan:** `create_app()`-фабрика (не модуль-глобал app)? Ресурсы в `lifespan`, закрытие там же? (`PYBOOT-5/6`). Engine/клиент на уровне модуля → `PYBOOT-X2`.
   - **DI:** контейнер/фабрики (не глобальные синглтоны)? `Clock`/`IdGenerator` за интерфейсом? (`PYBOOT-8/9`). `datetime.now()`/`uuid4()` в домене → `PYBOOT-X3`.
   - **Persistence:** async engine+sessionmaker в lifespan, сессия per-request; Liquibase, не `create_all` в проде (`PYBOOT-10`). `Base.metadata.create_all()` в проде → `PYBOOT-X4`.
   - **Server/health:** `/health/live` + `/health/ready` раздельно (`PYBOOT-13`). Блокирующий sync-вызов в async без executor → `PYBOOT-X5`.
   - **Observability:** structlog (JSON в проде) + correlation-id middleware; PII не в логах; prometheus/OTel (`PYBOOT-14`, cross-ref `AUTH-16`).
   - **Структура:** `core/` не импортит `app/`/`adapters`/FastAPI/SQLAlchemy (`PYBOOT-15`/`X6`, cross-ref `R-HEX-2`).

4. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

5. **Серьёзность** (`RFF-12`):
   - **Критично** — ресурс/engine в глобале (`PYBOOT-X2`), `create_all` в проде (`PYBOOT-X4`), блокирующий sync в async (`PYBOOT-X5`), `core/` импортит фреймворк (`PYBOOT-X6`), секрет в git.
   - **Предупреждение** — `os.getenv` вместо Settings (`PYBOOT-X1`), `datetime.now()`/`uuid4()` в домене (`PYBOOT-X3`), нет раздельных health, app — модуль-глобал.
   - **Замечание** — нет README quickstart, mypy/ruff не в CI.

## Что не входит

- Бизнес-операции — `ucp-py-pattern-review`. Обработка ошибок — `ucp-py-error-handling-review`. Валидация — `ucp-py-validation-review`.

$ARGUMENTS
