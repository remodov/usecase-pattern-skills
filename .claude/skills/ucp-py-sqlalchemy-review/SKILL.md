---
name: ucp-py-sqlalchemy-review
lang: python
description: Ревью persistence-слоя на async SQLAlchemy 2.0 + Alembic по UCP (коды R-SQLA-*) — порт/маппер ORM↔domain, граница TX на Handler через UoW, select() 2.0, ViewRepository, типы Decimal/tz/UUID.
when_to_use: Изменения в adapters/out/persistence (models.py, *_repository.py, *_mapper.py, *_view_repository.py) или в alembic-ревизиях.
paths: "**/adapters/out/persistence/**, **/alembic/versions/**"
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью persistence (Python / SQLAlchemy 2.0 async)

Ты ревьюишь persistence-слой на соответствие `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-*`). Репозиторий
реализует порт из `core/`, маппит ORM↔domain, граница транзакции — на Handler через UoW. Механический слой
(импорт-границы, типы, SQLi) ловит CI-стек (`import-linter`, `bandit`, `mypy`); здесь — семантика.

## Зависимости

- **`.claude/docs/backend/python/sqlalchemy/sqlalchemy-rules.md`** — правила `R-SQLA-*` (код-примеры включены).
- Парные: `backend/usecase-pattern/python/...` (порт/UoW/слои, `R-LAY-*`/`R-TX-*`/`R-HEX-*`), `backend/pg-types/pg-types-rules.md` (`PG-T-*` типы), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/pg-runtime-rules.md` (locks/bulk, `PG-W-*`), `backend/cqrs/cqrs-rules.md` (`R-CQRS-4` read-проекции).

## Инструкции

1. **Прочти** `sqlalchemy-rules.md`. Цитируй конкретные коды (`R-SQLA-REPO-X1`), не префикс.

2. **Скоп.** `adapters/out/persistence/**` (`models.py`, `*_repository.py`, `*_mapper.py`, `*_view_repository.py`), `alembic/versions/**`, порт-`Protocol` в `core/<bc>/port/`, `git diff` на `.py`.

3. **Прогон.**
   - **Repository:** реализует `Protocol` из `core/`, в `adapters/out/persistence/`? Public-методы принимают/возвращают доменные объекты, не ORM/`Row`? `AsyncSession` инжектится, не создаётся внутри? Покрыт интеграционным тестом против Testcontainers (`R-SQLA-REPO-1..4`). Возврат ORM-модели наружу → `R-SQLA-REPO-X1`. Бизнес-логика в репозитории (`if order.status == ...`) → `R-SQLA-REPO-X2`. `select(...)`/`AsyncSession` в `core/` → `R-SQLA-REPO-X3` (cross-ref `R-HEX-X1`).
   - **ORM-модели:** `DeclarativeBase`+`mapped_column` в `adapters/out/persistence/`, не в `core/`? Типы: деньги `Numeric(p,s)`→`Decimal`, время `DateTime(timezone=True)`, UUID `UUID(as_uuid=True)` (`R-SQLA-MODEL-1/2`, cross-ref `PG-T-013/030/040`). ORM≠domain≠Pydantic-DTO (`R-SQLA-MODEL-3`). Доменная логика/инварианты на ORM-модели → `R-SQLA-MODEL-X1`. Деньги `Float` → нарушение `R-SQLA-MODEL-2`.
   - **Маппинг:** явные `to_domain`/`to_model` рядом с репозиторием, сборка агрегата в маппере (`R-SQLA-MAP-1/2`). «Универсальный» `__dict__`/`vars()` или ORM напрямую как domain → `R-SQLA-MAP-X1`.
   - **Сессия/TX:** граница транзакции на Handler через UoW (`async with uow: ... await uow.commit()`), сессия per-request, read-методы без `commit` (`R-SQLA-SESS-1/2/3`, cross-ref `R-TX-1`/`PYBOOT-X2`). `commit()`/`rollback()` внутри репозитория → `R-SQLA-SESS-X1`. Использование ORM-объекта после commit (`expire_on_commit=True`) → `R-SQLA-SESS-X2` (`MissingGreenlet`/detached; маппи в домен до commit).
   - **Запросы:** 2.0-style `select(...)`+`await session.execute(...)` (`R-SQLA-QRY-1`); eager-load `selectinload`/`joinedload`, `relationship(lazy="raise")` (`R-SQLA-QRY-2`); bulk через `execute(insert(), rows)`/`add_all` (`R-SQLA-QRY-3`, cross-ref `PG-W-010`); пагинация `limit/offset`/keyset, `count(*)` отдельным запросом (`R-SQLA-QRY-4`); read-проекции — `<X>ViewRepository`→read-DTO, не агрегат (`R-SQLA-QRY-5`, cross-ref `R-CQRS-4`). `session.query(...)` legacy → `R-SQLA-QRY-X1`. Ленивая загрузка в async → `R-SQLA-QRY-X2`. `fetchall()` без `LIMIT` → `R-SQLA-QRY-X3`. `text(f"...{x}")` конкатенацией → `R-SQLA-QRY-X4`.
   - **Миграции:** схема через Alembic, не `create_all()` в проде (`R-SQLA-MIG-1`, cross-ref `PYBOOT-X4`); безопасность по `PG-M-*` (`R-SQLA-MIG-2`); autogenerate вычитан руками (`R-SQLA-MIG-3`). Правка применённой ревизии → `R-SQLA-MIG-X1`.

4. **Cross-check:** DDL/типы колонок — `ucp-pg-schema-review` (`PG-T-*`); безопасность миграций — `ucp-pg-migration-review` (`PG-M-*`); транзакции/блокировки под нагрузкой — `ucp-pg-runtime-review`; CQRS-разделение — `ucp-cqrs-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — возврат ORM наружу (`R-SQLA-REPO-X1`), `select`/сессия в `core/` (`R-SQLA-REPO-X3`), `commit`/`rollback` в репозитории (`R-SQLA-SESS-X1`), ленивая загрузка в async (`R-SQLA-QRY-X2`), сырой SQL конкатенацией (`R-SQLA-QRY-X4`), деньги `Float`, `create_all()` в проде.
   - **Предупреждение** — бизнес-логика в репозитории (`R-SQLA-REPO-X2`), доменная логика на ORM (`R-SQLA-MODEL-X1`), `session.query(...)` legacy (`R-SQLA-QRY-X1`), `__dict__`-маппинг (`R-SQLA-MAP-X1`), ORM-объект после commit (`R-SQLA-SESS-X2`), `fetchall()` без `LIMIT` (`R-SQLA-QRY-X3`), правка применённой ревизии (`R-SQLA-MIG-X1`).
   - **Замечание** — маппинг размазан по репозиторию (`R-SQLA-MAP-2`), `len(all())` вместо `count(*)`, нет интеграционного теста на репозиторий (`R-SQLA-REPO-4`), autogenerate-ревизия не вычитана (`R-SQLA-MIG-3`).

## Что не входит

- Бизнес-операции — `ucp-py-pattern-review`. Доменные инварианты — `ucp-py-ddd-tactical-review`.
- Типы колонок и безопасность миграций — `ucp-pg-schema-review` / `ucp-pg-migration-review`.

$ARGUMENTS
