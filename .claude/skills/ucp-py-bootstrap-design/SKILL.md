---
name: ucp-py-bootstrap-design
lang: python
description: Спроектировать или починить bootstrap FastAPI-сервиса на Python (коды PYBOOT-*) — профили pydantic-settings, app factory create_app + lifespan, DI-контейнер, async SQLAlchemy + Alembic, health live/ready, structlog+prometheus+OTel.
when_to_use: Триггеры — «настрой bootstrap FastAPI», «app factory + lifespan», «почему сервис не стартует». При старте сервиса или падении на конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(uvicorn*) Bash(alembic*) Bash(docker compose*) Bash(uv*)
---

# Проектирование bootstrap (Python / FastAPI)

Ты настраиваешь bootstrap-слой FastAPI-сервиса по UCP согласно `backend/python/python-bootstrap/python-bootstrap-rules.md`
(`PYBOOT-*`). Цель — сервис стартует локально одной командой, конфиг валидируется fail-fast, ресурсы в lifespan,
DI явный, раскладка core/adapters/app соблюдена.

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/python-bootstrap/python-bootstrap-rules.md` (`PYBOOT-*`). Связанные: `backend/validation/python/validation-style-guide.md` (`BaseSettings`), `backend/usecase-pattern/python/usecase-pattern-style-guide.md` (Dispatcher/DI), `backend/error-handling/python/error-handling-style-guide.md` (exception-handlers в фабрике).

2. **Диагноз: починка или с нуля.** Для починки сначала воспроизведи ошибку (`uvicorn app.main:app`); пройди Quickstart-чеклист (§ конец rules) — missing env / ресурс в глобале / нет Alembic.

3. **Произведи код** (без комментариев; коды правил НЕ цитируй в коде):
   - `app/settings.py` — `Settings(BaseSettings)` с `APP_ENV`, required без default, nested, `.env`-оверрайды (`PYBOOT-2/4`).
   - `app/main.py` — `create_app(settings) -> FastAPI` фабрика + `lifespan` (engine/sessionmaker/клиенты открываются и закрываются здесь); регистрация роутеров/exception-handlers/middleware (`PYBOOT-5/6/7`).
   - `app/container.py` — DI: репозитории, handlers, dispatcher, `Clock`/`IdGenerator`-реализации (`PYBOOT-8/9`).
   - persistence: `create_async_engine` + `async_sessionmaker` в lifespan, сессия per-request через `Depends`; Alembic-конфиг (`PYBOOT-10`), миграции вне старта приложения.
   - health: `/health/live`, `/health/ready` (`PYBOOT-13`).
   - bootstrap логирования/метрик/трейсинга в фабрике (`PYBOOT-14`).
   - README quickstart (`PYBOOT-11`).

4. **Самопроверка** — Quickstart-чеклист из rules.

5. **Финальный шаг:** предложи `ucp-py-bootstrap-review`; для бизнес-операций — `ucp-py-pattern-design`.

## Антипаттерны, которые НЕ генерировать

- `os.getenv(...)` россыпью вместо `Settings` (`PYBOOT-X1`); engine/клиент на уровне модуля (`PYBOOT-X2`).
- `datetime.now()`/`uuid4()` напрямую в домене вместо `Clock`/`IdGenerator` (`PYBOOT-X3`).
- `Base.metadata.create_all()` для прод-схемы вместо Alembic (`PYBOOT-X4`).
- блокирующие sync-вызовы в async без executor (`PYBOOT-X5`); импорт `app/`/`adapters` из `core/` (`PYBOOT-X6`).

После работы скилла — обязательно `ucp-py-bootstrap-review`.

$ARGUMENTS
