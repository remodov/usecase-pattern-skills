# Python Bootstrap — индекс правил (FastAPI)

> **Что это.** Bootstrap-конфигурация FastAPI-сервиса по UCP: профили, app factory, DI, persistence-wiring,
> server, health. Языко-специфичный concern (аналог Java `spring-bootstrap` / `BS-*`) — **только Python**, своя
> пара кодов `PYBOOT-*`. Скиллы читают этот файл; код-примеры включены (отдельного style-guide нет).
> Коды: `PYBOOT-<N>` — обязательно, `PYBOOT-X<N>` — антипаттерн (запрещено).

Базовый принцип (`PYBOOT-1`): **сервис запускается локально одной командой, без живых внешних зависимостей** (кроме Postgres из docker-compose). Нужен живой Keycloak/Kafka для `uvicorn app.main:app` — баг настройки.

## 1. Профили и конфиг
**MUST:**
- **PYBOOT-2.** Три состояния через env (`APP_ENV=local|integration-test|production`): production (реальные сервисы), local (Postgres docker-compose, auth off, внешние URL на dev), integration-test (Postgres+WireMock-аналог, фоновые задачи off). Конфиг — `pydantic-settings BaseSettings` с `.env`-оверрайдами (cross-ref `R-VLD-CFG-1`).
- **PYBOOT-3.** Профиль не активируется кодом — только через env. Код, специфичный профилю, гейтится по `settings.env`.
- **PYBOOT-4.** `BaseSettings` валидируется на старте (fail-fast); required-поля без default, типобезопасно. Секреты — из env/Vault, не в коде/`.env` в git (cross-ref `AUTH-17`).

**MUST NOT:**
- **PYBOOT-X1.** `os.getenv(...)` россыпью по коду вместо одного `Settings`-объекта — нетипизировано, не валидируется.

## 2. App factory и lifespan
**MUST:**
- **PYBOOT-5.** Приложение собирается **фабрикой** `create_app(settings) -> FastAPI`, не модуль-левел глобал — чтобы тесты поднимали изолированные инстансы.
- **PYBOOT-6.** Ресурсы (engine, пулы, клиенты) — через `lifespan`-контекст (`@asynccontextmanager`), не глобальные синглтоны на импорте. Закрытие — в той же lifespan (graceful).
- **PYBOOT-7.** Роутеры, exception-handlers (`ucp-py-error-handling`), middleware регистрируются в фабрике.

**MUST NOT:**
- **PYBOOT-X2.** Создание engine/клиента/коннекта на уровне модуля (`engine = create_async_engine(...)` в глобале) — ломает тесты и lifespan.

## 3. DI-композиция
**MUST:**
- **PYBOOT-8.** DI — явный контейнер (`dependency-injector` / `punq`) или фабрики + FastAPI `Depends`; не глобальные синглтоны. Handlers + репозитории + dispatcher собираются в `app/container.py` (cross-ref `R-HND-2`, `R-DSP-2`).
- **PYBOOT-9.** Источники недетерминизма (время, UUID) — за интерфейсом-`Protocol` (`Clock`, `IdGenerator`), production-реализация — в контейнере, тест подменяет (cross-ref `R-HND-5`, тест-стратегия).

**MUST NOT:**
- **PYBOOT-X3.** `datetime.now()` / `uuid4()` напрямую в домене/хендлере — через `Clock`/`IdGenerator` (иначе недетерминированные тесты).

## 4. Persistence-wiring
**MUST:**
- **PYBOOT-10.** Async SQLAlchemy: `create_async_engine` + `async_sessionmaker` в lifespan; сессия per-request через DI/`Depends`. Миграции — **Liquibase** (отдельно от рантайма), `liquibase update` в CI/деплое, не в коде приложения на старте.
- **PYBOOT-11.** Локальный quickstart документирован в README: `docker compose up -d postgres && liquibase update && uvicorn app.main:app --reload`.

**MUST NOT:**
- **PYBOOT-X4.** `Base.metadata.create_all()` в проде для схемы — только Liquibase (create_all допустим в unit-тестах без миграций).

## 5. Server и shutdown
**MUST:**
- **PYBOOT-12.** ASGI-сервер — `uvicorn` (dev) / `gunicorn -k uvicorn.workers.UvicornWorker` или `uvicorn --workers` (prod). Graceful shutdown — через lifespan-закрытие ресурсов + обработку SIGTERM (cross-ref graceful-shutdown-интент).
- **PYBOOT-13.** Health-эндпоинты: `/health/live` (процесс жив) и `/health/ready` (зависимости готовы) — раздельно.

**MUST NOT:**
- **PYBOOT-X5.** Блокирующие (sync) вызовы в async-эндпоинтах/хендлерах без `run_in_executor` — блокируют event loop.

## 6. Логирование/observability bootstrap
**MUST:**
- **PYBOOT-14.** Структурное логирование (`structlog`/`nestjs`-аналог) настраивается в фабрике: JSON в проде, correlation-id через middleware + `contextvars`. PII в логах запрещён (cross-ref `AUTH-16`). Метрики — `prometheus_client`, трейсинг — OpenTelemetry (cross-ref observability-интент).

## 7. Структура и зависимости
**MUST:**
- **PYBOOT-15.** Раскладка: `core/` (домен+usecases+порты, без FastAPI/SQLAlchemy), `adapters/in/http`, `adapters/out/{persistence,...}`, `app/` (main, container, lifespan). Менеджер пакетов — `uv` или Poetry; `ruff` + `mypy --strict` в CI (cross-ref `backend/python/python-style/python-style-rules.md` `PY-RUFF-*`).
- **PYBOOT-X6.** ❌ Импорт `app/`/`adapters` из `core/` — зависимости направлены внутрь (cross-ref `R-HEX-2`).

## Quickstart-чеклист (сервис не стартует)
1. `APP_ENV` выставлен? (`local` для разработки)
2. `Settings` валидируется — нет ли missing required env (ошибка на старте)?
3. Postgres поднят (`docker compose up -d postgres`)? Liquibase накатан (`liquibase update`)?
4. Ресурсы в lifespan, не в глобале (`PYBOOT-X2`)?
5. На production-старте auth/JWKS — ленивый, сервис стартует без живого IdP.
