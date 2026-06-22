---
name: ucp-py-codegen-design
lang: python
description: Настроить contract/DB-first генерацию артефактов FastAPI-сервиса по UCP (коды PYGEN-*) — Pydantic v2-схемы из OpenAPI через datamodel-codegen (StrEnum, snake+camelCase alias, ApiBaseModel) и ORM-модели из DBML через dbml2sql→Liquibase→sqlacodegen (Decimal для денег, DateTime tz=True, PG_ENUM create_type=False). Миграции — Liquibase (DB-first). Триггеры — «генерация схем из OpenAPI», «модели из DBML», «настрой codegen-пайплайн».
when_to_use: В начале сервиса при contract/DB-first подходе — когда есть (или создаётся) openapi.yaml и schema.dbml как источники истины. Перед ucp-py-sqlalchemy-design (даёт ORM-черновик).
allowed-tools: Read Glob Grep Write Edit Bash(datamodel-codegen*) Bash(sqlacodegen*) Bash(dbml2sql*) Bash(python*)
---

# Проектирование codegen-пайплайна (Python / contract+DB-first)

Ты настраиваешь генерацию артефактов согласно `backend/python/codegen/codegen-rules.md` (`PYGEN-*`).
Контракт OpenAPI и DBML — **источники истины**; код генерируется из них. Это командный contract/DB-first binding;
для таких сервисов миграции ведёт **Liquibase** (переопределяет `R-SQLA-MIG-1`).

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/codegen/codegen-rules.md` (`PYGEN-*`). Связанные: `backend/rest-api/rest-api-rules.md` (`R-API-*` — формат DTO/JSON), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-MODEL-*` — типы/слой ORM), `backend/pg-types/pg-types-rules.md` (`PG-T-*`), `backend/pg-migrations/pg-migrations-rules.md` (`PG-M-*`).

2. **Определи источники:** `doc/openapi.yaml` (≥3.0.3) и `doc/schema.dbml` — есть/создать. Они в репозитории.

3. **Настрой генерацию** (воспроизводимые команды в Makefile/justfile; коды правил НЕ цитируй в коде):
   - **Схемы** — `datamodel-codegen`: Pydantic v2, `--use-subclass-enum` (StrEnum), `--snake-case-field` + `--allow-population-by-field-name` (snake+alias, `populate_by_name`), `--use-annotated --use-union-operator` (`PYGEN-SC-1..4`). Заведи ручной `ApiBaseModel` с `model_config` и datetime→ISO 8601 `Z` (`PYGEN-SC-5`). Деньги — `Decimal` (`PYGEN-SC-6`).
   - **Модели** — пайплайн `dbml2sql schema.dbml --postgres` → Liquibase changelog (`liquibase/changelog/generated/`) → `sqlacodegen` черновик (`PYGEN-MD-2`). Доведи типы: `Numeric→Decimal`, `DateTime(timezone=True)`, `UUID(as_uuid=True)`, `PG_ENUM(create_type=False)` (`PYGEN-MD-3`); модели — в `adapters/out/persistence/` (`PYGEN-MD-4`).
   - **Миграции** — Liquibase changelog (единственный источник DDL); безопасность по `PG-M-*` (`PYGEN-MIG-1/2`).

4. **Регенерация не затирает ручное** (ApiBaseModel, доводку models.py держать вне генерируемых блоков).

5. **Самопроверка** + предложи `ucp-py-codegen-review`. Для качества ORM-слоя дальше — `ucp-py-sqlalchemy-design`; для контракта — `ucp-py-api-review`.

## Антипаттерны, которые НЕ генерировать

- Схемы/модели руками с нуля вместо генерации из контракта/DBML (`PYGEN-SC-X1`); правка сгенерированного без обновления источника (`PYGEN-SC-X2`).
- `class X(str, Enum)` вместо `StrEnum`, `null` в 2xx (`PYGEN-SC-X3`); `float`/`Mapped[float]` для денег (`PYGEN-SC-X4`/`PYGEN-MD-X1`).
- `DateTime` без `timezone=True` (`PYGEN-MD-X2`); пропуск `dbml2sql` (`PYGEN-MD-X3`).
- Ручной DDL мимо Liquibase changelog / несколько источников схемы (`PYGEN-MIG-X1`); правка применённого changelog (`PYGEN-MIG-X2`).

После работы скилла — обязательно `ucp-py-codegen-review`.

$ARGUMENTS
