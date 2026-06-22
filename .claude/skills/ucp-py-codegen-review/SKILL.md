---
name: ucp-py-codegen-review
lang: python
description: Проверить contract/DB-first codegen FastAPI-сервиса по UCP (коды PYGEN-*) — схемы сгенерированы из OpenAPI (не руками), Pydantic v2 + StrEnum + snake/camelCase alias + ApiBaseModel, ORM из DBML через dbml2sql→Liquibase→sqlacodegen, Decimal для денег (не float), DateTime(timezone=True) (не naive), PG_ENUM(create_type=False), миграции Liquibase (единственный источник DDL). Вызывается на ревью schemas/*.py, models.py, openapi.yaml, schema.dbml, команд генерации, Liquibase changelog.
allowed-tools: Read Glob Grep
---

# Ревью codegen-пайплайна (Python / contract+DB-first)

Ты проверяешь генерацию артефактов против `backend/python/codegen/codegen-rules.md` (`PYGEN-*`).
Формат findings — `shared/review-finding-format.md` (`RFF-*`).

## Процесс ревью

1. **Прочитай** `.claude/docs/backend/python/codegen/codegen-rules.md` (`PYGEN-*`) и `.claude/docs/shared/review-finding-format.md`. Связанные: `R-API-*`, `R-SQLA-MODEL-*`, `PG-T-*`, `PG-M-*`.

2. **Определи объект:** `<pkg>/schemas/*.py`, `<pkg>/adapters/out/persistence/models.py`, `doc/openapi.yaml`, `doc/schema.dbml`, команды генерации (Makefile/justfile/scripts), Liquibase changelog.

3. **Проверь по подгруппам кодов** (цитируй коды в findings):
   - **SC** (`PYGEN-SC-*`): схемы сгенерированы из контракта, не написаны с нуля (`X1`) и не правлены в обход источника (`X2`); Pydantic v2 + `populate_by_name`; snake+camelCase alias; `StrEnum` не `class X(str, Enum)` (`X3`); `ApiBaseModel` с `model_config`; `Decimal` не `float` (`X4`); `exclude_none` (нет `null` в 2xx).
   - **MD** (`PYGEN-MD-*`): источник `schema.dbml`; пайплайн с `dbml2sql --postgres` (не пропущен, `X3`); типы — `Decimal` (не `Mapped[float]`, `X1`), `DateTime(timezone=True)` (не naive, `X2`), `UUID(as_uuid=True)`, `PG_ENUM(create_type=False)`; модели в `adapters/out/persistence/`; нет доменной логики на модели (`X4`).
   - **MIG** (`PYGEN-MIG-*`): миграции — Liquibase (единственный источник DDL, без ручного DDL мимо changelog — `X1`); нет правки применённого changelog (`X2`); безопасность по `PG-M-*`.

4. **Частые реальные дефекты** (приоритет): `Mapped[float]` для денег; `DateTime` без tz с доклейкой только на сериализации; `class X(str, Enum)` вместо `StrEnum`; пропущенный `dbml2sql`; схемы/модели, написанные руками при наличии контракта/DBML (дрейф); OpenAPI-версия и пути артефактов рассинхронены с реальными.

5. **Выдай findings** по `RFF-*` (severity, код, файл:строка, фикс) и предложи парный `ucp-py-codegen-design`.

## Что не входит

- Семантика самого REST-контракта (URL/методы/статусы) — `ucp-py-api-review`. Качество persistence-слоя (репозиторий/UoW/маппер/запросы) — `ucp-py-sqlalchemy-review`. Безопасность DDL/типы на уровне PG — `ucp-pg-schema-review`. Безопасность миграций — `ucp-pg-migration-review`.

$ARGUMENTS
