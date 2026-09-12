---
name: ucp-py-sqlalchemy-review
lang: python
description: Ревью persistence-слоя на async SQLAlchemy 2.0 + Liquibase по UCP (требования sqlalchemy/*) — порт/маппер ORM↔domain, граница TX на Handler через UoW, select() 2.0, ViewRepository, типы Decimal/tz/UUID.
when_to_use: Изменения в adapters/out/persistence (models.py, *_repository.py, *_mapper.py, *_view_repository.py) или в Liquibase changelog.
paths: "**/adapters/out/persistence/**, **/liquibase/changelog/**"
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью persistence (Python / SQLAlchemy 2.0 async)

Ты ревьюишь persistence-слой на соответствие `backend/python/sqlalchemy/spec.md` (`R-SQLA-*`). Репозиторий
реализует порт из `core/`, маппит ORM↔domain, граница транзакции — на Handler через UoW. Механический слой
(импорт-границы, типы, SQLi) ловит CI-стек (`import-linter`, `bandit`, `mypy`); здесь — семантика.

## Зависимости

- **`.claude/docs/backend/python/sqlalchemy/spec.md`** — правила `R-SQLA-*` (код-примеры включены).
- Парные: `backend/usecase-pattern/python/...` (порт/UoW/слои, `R-LAY-*`/`R-TX-*`/`R-HEX-*`), `backend/pg-types/spec.md` (`PG-T-*` типы), `backend/pg-migrations/spec.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/spec.md` (locks/bulk, `PG-W-*`), `backend/cqrs/spec.md` (`usecase-pattern/reads-via-read-model` read-проекции).

## Инструкции

1. **Прочти** `sqlalchemy/spec.md`. Цитируй конкретные коды (`sqlalchemy/repository-speaks-domain-types`), не префикс.

2. **Скоп.** `adapters/out/persistence/**` (`models.py`, `*_repository.py`, `*_mapper.py`, `*_view_repository.py`), `liquibase/changelog/**`, порт-`Protocol` в `core/<bc>/port/`, `git diff` на `.py`.

3. **Прогон.**
   - **Repository:** реализует `Protocol` из `core/`, в `adapters/out/persistence/`? Public-методы принимают/возвращают доменные объекты, не ORM/`Row`? `AsyncSession` инжектится, не создаётся внутри? Покрыт интеграционным тестом против Testcontainers (`R-SQLA-REPO-1..4`). Возврат ORM-модели наружу → `sqlalchemy/repository-speaks-domain-types`. Бизнес-логика в репозитории (`if order.status == ...`) → `sqlalchemy/no-business-logic-in-repository`. `select(...)`/`AsyncSession` в `core/` → `sqlalchemy/port-in-core-implementation-in-adapter` (cross-ref `hexagonal/outbound-port-interface-in-core`).
   - **ORM-модели:** `DeclarativeBase`+`mapped_column` в `adapters/out/persistence/`, не в `core/`? Типы: деньги `Numeric(p,s)`→`Decimal`, время `DateTime(timezone=True)`, UUID `UUID(as_uuid=True)` (`R-SQLA-MODEL-1/2`, cross-ref `PG-T-013/030/040`). ORM≠domain≠Pydantic-DTO (`sqlalchemy/orm-models-are-anemic-and-in-adapter`). Доменная логика/инварианты на ORM-модели → `sqlalchemy/orm-models-are-anemic-and-in-adapter`. Деньги `Float` → нарушение `sqlalchemy/precise-column-types`.
   - **Маппинг:** явные `to_domain`/`to_model` рядом с репозиторием, сборка агрегата в маппере (`R-SQLA-MAP-1/2`). «Универсальный» `__dict__`/`vars()` или ORM напрямую как domain → `sqlalchemy/explicit-mapper`.
   - **Сессия/TX:** граница транзакции на Handler через UoW (`async with uow: ... await uow.commit()`), сессия per-request, read-методы без `commit` (`R-SQLA-SESS-1/2/3`, cross-ref `usecase-pattern/transaction-boundary-on-handler`/`python-bootstrap/resources-in-lifespan`). `commit()`/`rollback()` внутри репозитория → `sqlalchemy/transaction-boundary-on-handler`. Использование ORM-объекта после commit (`expire_on_commit=True`) → `sqlalchemy/no-orm-access-after-commit` (`MissingGreenlet`/detached; маппи в домен до commit). **Обработка ошибок в транзакции:** при сбое в `session.begin()` в лог попадают и ошибка, и шаг/операция (контекст шага через `bind_contextvars`, лог — централизованным edge-handler), исключение не глотается (`sqlalchemy/transaction-errors-propagate-with-context`). Проглатывание исключения в TX (`except: pass`/`log` без re-raise) или partial commit между шагами → `sqlalchemy/transaction-errors-propagate-with-context`.
   - **Запросы:** 2.0-style `select(...)`+`await session.execute(...)` (`sqlalchemy/modern-query-style`); eager-load `selectinload`/`joinedload`, `relationship(lazy="raise")` (`sqlalchemy/eager-load-relationships`); bulk через `execute(insert(), rows)`/`add_all` (`sqlalchemy/bulk-operations`, cross-ref `pg-runtime/bulk-load-via-copy`); пагинация `limit/offset`/keyset, `count(*)` отдельным запросом (`sqlalchemy/pagination-and-counting`); read-проекции — `<X>ViewRepository`→read-DTO, не агрегат (`sqlalchemy/view-repository-for-projections`, cross-ref `usecase-pattern/reads-via-read-model`). `session.query(...)` legacy → `sqlalchemy/modern-query-style`. Ленивая загрузка в async → `sqlalchemy/eager-load-relationships`. `fetchall()` без `LIMIT` → `sqlalchemy/pagination-and-counting`. `text(f"...{x}")` конкатенацией → `sqlalchemy/raw-sql-is-parameterized`.
   - **Миграции:** схема через Liquibase, не `create_all()` в проде (`sqlalchemy/schema-via-migrations`, cross-ref `python-bootstrap/persistence-wiring`); безопасность по `PG-M-*` (`sqlalchemy/schema-via-migrations`); сгенерированный changelog вычитан руками (`sqlalchemy/generated-changelog-is-reviewed`). Правка применённого changeset → `sqlalchemy/generated-changelog-is-reviewed`.

4. **Cross-check:** DDL/типы колонок — `ucp-pg-schema-review` (`PG-T-*`); безопасность миграций — `ucp-pg-migration-review` (`PG-M-*`); транзакции/блокировки под нагрузкой — `ucp-pg-runtime-review`; CQRS-разделение — `ucp-cqrs-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — возврат ORM наружу (`sqlalchemy/repository-speaks-domain-types`), `select`/сессия в `core/` (`sqlalchemy/port-in-core-implementation-in-adapter`), `commit`/`rollback` в репозитории (`sqlalchemy/transaction-boundary-on-handler`), ленивая загрузка в async (`sqlalchemy/eager-load-relationships`), сырой SQL конкатенацией (`sqlalchemy/raw-sql-is-parameterized`), деньги `Float`, `create_all()` в проде.
   - **Предупреждение** — бизнес-логика в репозитории (`sqlalchemy/no-business-logic-in-repository`), доменная логика на ORM (`sqlalchemy/orm-models-are-anemic-and-in-adapter`), `session.query(...)` legacy (`sqlalchemy/modern-query-style`), `__dict__`-маппинг (`sqlalchemy/explicit-mapper`), ORM-объект после commit (`sqlalchemy/no-orm-access-after-commit`), `fetchall()` без `LIMIT` (`sqlalchemy/pagination-and-counting`), проглатывание исключения/partial commit в транзакции (`sqlalchemy/transaction-errors-propagate-with-context`), правка применённой ревизии (`sqlalchemy/generated-changelog-is-reviewed`).
   - **Замечание** — маппинг размазан по репозиторию (`sqlalchemy/explicit-mapper`), `len(all())` вместо `count(*)`, нет интеграционного теста на репозиторий (`sqlalchemy/repository-integration-tested`), autogenerate-ревизия не вычитана (`sqlalchemy/generated-changelog-is-reviewed`).

## Что не входит

- Бизнес-операции — `ucp-py-pattern-review`. Доменные инварианты — `ucp-py-ddd-tactical-review`.
- Типы колонок и безопасность миграций — `ucp-pg-schema-review` / `ucp-pg-migration-review`.

$ARGUMENTS
