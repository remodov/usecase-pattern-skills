---
name: ucp-py-sqlalchemy-design
lang: python
description: Сгенерировать persistence-слой на async SQLAlchemy 2.0 + Liquibase из доменного порта по UCP — SqlAlchemy<X>Repository реализует Protocol из core/, маппер ORM↔domain, UoW, select() 2.0 + eager-load, ViewRepository, Liquibase changelog.
when_to_use: После ucp-py-pattern-design (есть порт-Protocol). Триггеры — «репозиторий на SQLAlchemy для X», «persistence для агрегата Y», «async-репозиторий».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(liquibase*) Bash(pytest*)
---

# Проектирование persistence (Python / SQLAlchemy 2.0 async)

Ты генерируешь persistence-слой согласно `backend/python/sqlalchemy/spec.md` (`R-SQLA-*`). Репозиторий реализует
порт из `core/`, маппит ORM↔domain, граница транзакции — на Handler через UoW.

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/sqlalchemy/spec.md` (`R-SQLA-*`). Связанные: `backend/usecase-pattern/python/...` (порт/UoW/слои), `backend/pg-types/spec.md` (`PG-T-*` типы), `backend/pg-migrations/spec.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/spec.md` (locks/bulk).

2. **Вход:** доменный порт-`Protocol` из `core/<bc>/port/` (от `ucp-py-pattern-design`) + агрегат.

3. **Произведи код** (SQLAlchemy 2.0 async, тайп-хинты; без комментариев; коды правил НЕ цитируй):
   - `adapters/out/persistence/models.py` — ORM-модели (`DeclarativeBase`+`mapped_column`), типы: `Numeric`→Decimal (деньги), `DateTime(timezone=True)`, `UUID` (`R-SQLA-MODEL-1/2`).
   - `adapters/out/persistence/<x>_mapper.py` — явный `to_domain`/`to_model` (`sqlalchemy/explicit-mapper`).
   - `adapters/out/persistence/<x>_repository.py` — `SqlAlchemy<X>Repository` реализует порт; `AsyncSession` инжектится; методы возвращают домен; `select()` 2.0 + eager-load (`selectinload`); `relationship(..., lazy="raise")` (`R-SQLA-REPO-*`, `R-SQLA-QRY-1/2`).
   - read-проекции — `SqlAlchemy<X>ViewRepository` → read-DTO (`sqlalchemy/view-repository-for-projections`).
   - Liquibase changelog (для codegen-сервисов — из DBML), вычитать diff руками (`R-SQLA-MIG-1/3`); безопасность по `PG-M-*`.

4. **Граница транзакции — НЕ в репозитории** (`commit` на Handler через UoW, `sqlalchemy/transaction-boundary-on-handler`). Маппинг в домен — до `commit` (`sqlalchemy/no-orm-access-after-commit`). Обработка ошибок в TX: контекст шага через `bind_contextvars(step=..., use_case=...)`, исключение не глотать (авто-rollback + edge-лог ошибки и шага) — `sqlalchemy/transaction-errors-propagate-with-context`/`X3`.

5. **Самопроверка** + предложи `ucp-py-sqlalchemy-review`. Для DDL/типов — `ucp-pg-schema-review`.

## Антипаттерны, которые НЕ генерировать

- Возврат ORM-модели наружу (`sqlalchemy/repository-speaks-domain-types`); бизнес-логика/`commit` в репозитории (`sqlalchemy/no-business-logic-in-repository`/`sqlalchemy/transaction-boundary-on-handler`).
- `select(...)` или сессия в `core/` (`sqlalchemy/port-in-core-implementation-in-adapter`); доменная логика на ORM-модели (`sqlalchemy/orm-models-are-anemic-and-in-adapter`).
- `session.query(...)` legacy (`sqlalchemy/modern-query-style`); ленивая загрузка связей в async (`sqlalchemy/eager-load-relationships`); деньги `Float`.
- `text(f"...{x}")` с конкатенацией (`sqlalchemy/raw-sql-is-parameterized`); `create_all()` в проде вместо Liquibase.

После работы скилла — обязательно `ucp-py-sqlalchemy-review`.

$ARGUMENTS
