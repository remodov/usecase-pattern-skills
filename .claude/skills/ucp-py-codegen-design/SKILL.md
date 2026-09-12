---
name: ucp-py-codegen-design
lang: python
description: Настроить contract/DB-first генерацию артефактов FastAPI-сервиса по UCP (требования codegen/*) — Pydantic v2-схемы из OpenAPI, ORM-модели из DBML через Liquibase, Decimal для денег и tz-aware время.
when_to_use: В начале сервиса при contract/DB-first: есть openapi.yaml и schema.dbml как источники истины. Перед ucp-py-sqlalchemy-design.
allowed-tools: Read Glob Grep Write Edit Bash(datamodel-codegen*) Bash(sqlacodegen*) Bash(dbml2sql*) Bash(python*)
---

# Проектирование codegen-пайплайна (Python / contract+DB-first)

Ты настраиваешь генерацию артефактов согласно `backend/python/codegen/spec.md` (`PYGEN-*`).
Контракт OpenAPI и DBML — **источники истины**; код генерируется из них. Это командный contract/DB-first binding;
для таких сервисов миграции ведёт **Liquibase** (переопределяет `sqlalchemy/schema-via-migrations`).

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/codegen/spec.md` (`PYGEN-*`). Связанные: `backend/rest-api/spec.md` (`R-API-*` — формат DTO/JSON), `backend/python/sqlalchemy/spec.md` (`R-SQLA-MODEL-*` — типы/слой ORM), `backend/pg-types/spec.md` (`PG-T-*`), `backend/pg-migrations/spec.md` (`PG-M-*`).

2. **Определи источники:** `doc/openapi.yaml` (≥3.0.3) и `doc/schema.dbml` — есть/создать. Они в репозитории.

3. **Настрой генерацию** (воспроизводимые команды в Makefile/justfile; коды правил НЕ цитируй в коде):
   - **Схемы** — `datamodel-codegen`: Pydantic v2, `--use-subclass-enum` (StrEnum), `--snake-case-field` + `--allow-population-by-field-name` (snake+alias, `populate_by_name`), `--use-annotated --use-union-operator` (`PYGEN-SC-1..4`). Заведи ручной `ApiBaseModel` с `model_config` и datetime→ISO 8601 `Z` (`codegen/shared-base-model`). Деньги — `Decimal` (`codegen/precise-schema-types`).
   - **Модели** — пайплайн `dbml2sql schema.dbml --postgres` → Liquibase changelog (`liquibase/changelog/generated/`) → `sqlacodegen` черновик (`codegen/schema-pipeline`). Доведи типы: `Numeric→Decimal`, `DateTime(timezone=True)`, `UUID(as_uuid=True)`, `PG_ENUM(create_type=False)` (`codegen/precise-orm-types`); модели — в `adapters/out/persistence/` (`codegen/orm-draft-is-finished-by-hand`).
   - **Миграции** — Liquibase changelog (единственный источник DDL); безопасность по `PG-M-*` (`PYGEN-MIG-1/2`).

4. **Регенерация не затирает ручное** (ApiBaseModel, доводку models.py держать вне генерируемых блоков).

5. **Самопроверка** + предложи `ucp-py-codegen-review`. Для качества ORM-слоя дальше — `ucp-py-sqlalchemy-design`; для контракта — `ucp-py-api-review`.

## Антипаттерны, которые НЕ генерировать

- Схемы/модели руками с нуля вместо генерации из контракта/DBML (`codegen/schemas-generated-from-contract`); правка сгенерированного без обновления источника (`codegen/generated-files-not-edited`).
- `class X(str, Enum)` вместо `StrEnum`, `null` в 2xx (`codegen/generation-settings`); `float`/`Mapped[float]` для денег (`codegen/precise-schema-types`/`codegen/precise-orm-types`).
- `DateTime` без `timezone=True` (`codegen/precise-orm-types`); пропуск `dbml2sql` (`codegen/schema-pipeline`).
- Ручной DDL мимо Liquibase changelog / несколько источников схемы (`codegen/single-source-of-schema-truth`); правка применённого changelog (`codegen/single-source-of-schema-truth`).

После работы скилла — обязательно `ucp-py-codegen-review`.

$ARGUMENTS
