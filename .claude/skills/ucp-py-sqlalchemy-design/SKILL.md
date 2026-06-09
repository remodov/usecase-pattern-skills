---
name: ucp-py-sqlalchemy-design
lang: python
description: Сгенерировать persistence-слой на async SQLAlchemy 2.0 + Alembic из доменного порта по UCP (коды R-SQLA-*) — SqlAlchemy<X>Repository реализует Protocol из core/, маппер ORM↔domain, UoW, select() 2.0 + eager-load, ViewRepository, Alembic.
when_to_use: После ucp-py-pattern-design (есть порт-Protocol). Триггеры — «репозиторий на SQLAlchemy для X», «persistence для агрегата Y», «async-репозиторий».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(alembic*) Bash(pytest*)
---

# Проектирование persistence (Python / SQLAlchemy 2.0 async)

Ты генерируешь persistence-слой согласно `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-*`). Репозиторий реализует
порт из `core/`, маппит ORM↔domain, граница транзакции — на Handler через UoW.

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-*`). Связанные: `backend/usecase-pattern/python/...` (порт/UoW/слои), `backend/pg-types/pg-types-rules.md` (`PG-T-*` типы), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*` безопасные миграции), `backend/pg-runtime/pg-runtime-rules.md` (locks/bulk).

2. **Вход:** доменный порт-`Protocol` из `core/<bc>/port/` (от `ucp-py-pattern-design`) + агрегат.

3. **Произведи код** (SQLAlchemy 2.0 async, тайп-хинты; без комментариев; коды правил НЕ цитируй):
   - `adapters/out/persistence/models.py` — ORM-модели (`DeclarativeBase`+`mapped_column`), типы: `Numeric`→Decimal (деньги), `DateTime(timezone=True)`, `UUID` (`R-SQLA-MODEL-1/2`).
   - `adapters/out/persistence/<x>_mapper.py` — явный `to_domain`/`to_model` (`R-SQLA-MAP-1`).
   - `adapters/out/persistence/<x>_repository.py` — `SqlAlchemy<X>Repository` реализует порт; `AsyncSession` инжектится; методы возвращают домен; `select()` 2.0 + eager-load (`selectinload`); `relationship(..., lazy="raise")` (`R-SQLA-REPO-*`, `R-SQLA-QRY-1/2`).
   - read-проекции — `SqlAlchemy<X>ViewRepository` → read-DTO (`R-SQLA-QRY-5`).
   - Alembic-ревизия (`alembic revision --autogenerate`), вычитать diff руками (`R-SQLA-MIG-1/3`); безопасность по `PG-M-*`.

4. **Граница транзакции — НЕ в репозитории** (`commit` на Handler через UoW, `R-SQLA-SESS-1`). Маппинг в домен — до `commit` (`R-SQLA-SESS-X2`).

5. **Самопроверка** + предложи `ucp-py-sqlalchemy-review`. Для DDL/типов — `ucp-pg-schema-review`.

## Антипаттерны, которые НЕ генерировать

- Возврат ORM-модели наружу (`R-SQLA-REPO-X1`); бизнес-логика/`commit` в репозитории (`R-SQLA-REPO-X2`/`R-SQLA-SESS-X1`).
- `select(...)` или сессия в `core/` (`R-SQLA-REPO-X3`); доменная логика на ORM-модели (`R-SQLA-MODEL-X1`).
- `session.query(...)` legacy (`R-SQLA-QRY-X1`); ленивая загрузка связей в async (`R-SQLA-QRY-X2`); деньги `Float`.
- `text(f"...{x}")` с конкатенацией (`R-SQLA-QRY-X4`); `create_all()` в проде вместо Alembic.

После работы скилла — обязательно `ucp-py-sqlalchemy-review`.

$ARGUMENTS
