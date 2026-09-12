---
name: ucp-py-validation-review
lang: python
description: Ревью валидации входа в Python/FastAPI (Pydantic v2) по UCP — DTO как Pydantic-модели на границе, constraints через Field, custom через Annotated+AfterValidator, cross-field через model_validator, BaseSettings, деньги Decimal.
when_to_use: Изменения в Pydantic-моделях, эндпоинтах, validation/types.py или settings.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью валидации (Python / Pydantic v2 / FastAPI)

Ты ревьюишь валидацию входа на соответствие **общему контракту** `backend/validation/spec.md` (`R-VLD-*`)
и **Python-реализации** `backend/validation/references/python/implementation.md`. Помни инверсию: FastAPI code-first
(Pydantic = источник, OpenAPI генерируется) — актуально «нет дублей правил», не «не править generated».

## Зависимости

- **`.claude/docs/backend/validation/spec.md`** — контракт (`R-VLD-WHERE-*`/`STD-*`/`CC-*`/`GRP-*`/`XF-*`/`OAS-*`/`CFG-*`/`MSG-*`).
- **`.claude/docs/backend/validation/references/python/implementation.md`** — Pydantic-реализация.
- Парные: `backend/error-handling/spec.md` (`error-handling/domain-and-validation-mapping`), `backend/ddd-tactical/spec.md` (инварианты ≠ валидация).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`validation/input-validated-at-edge`), не префикс.

2. **Скоп.** `**/*request*.py`, `**/*dto*.py`, эндпоинты, `backend/validation/types.py`, `settings.py`/`config.py`, `git diff` на `.py`.

3. **Прогон.**
   - **WHERE:** входной DTO — Pydantic-модель в сигнатуре эндпоинта? (`validation/input-validated-at-edge`). Ручная `if ...: raise` в Handler → `validation/input-validated-at-edge`. Pydantic-constraints на агрегате → `validation/domain-invariants-in-aggregate`. Конфиг — `BaseSettings`? (`validation/config-validated-at-startup`/`CFG-1`).
   - **STD:** `Field`-constraints/спец-типы (`EmailStr`/`UUID`); деньги — `Decimal` не `float`. `@field_validator` «не None» на non-Optional → `validation/no-false-or-composite-constraints`; email-regex вместо `EmailStr` → `validation/standard-constraints-preferred`.
   - **CC:** custom — `Annotated[..., AfterValidator]` в общем модуле, имя по домену, на не-None? inline в DTO → `validation/custom-constraint-is-reusable`.
   - **XF:** cross-field — `@model_validator(mode="after")`, говорящее имя; в Handler перед dispatch → `validation/cross-field-rules-on-object`.
   - **GRP:** разные сценарии — отдельные модели, не один тип с режимами (`validation/scenario-groups-are-narrow`).
   - **OAS (code-first):** контракт = Pydantic-модель, не голый `dict` (`validation/controller-implements-generated-contract`); дубли правил (Pydantic + ручной чек) → `validation/single-source-of-truth`.
   - **CFG:** `BaseSettings`, required без default, nested валидируется; `os.environ[...]` для required → `validation/config-validated-at-startup`.
   - **MSG:** сообщения на русском, человекочитаемые; английский/тех-термины → `R-VLD-MSG-X1/X2`.

4. **Cross-check:** 400-маппинг → `ucp-py-error-handling-review` (`error-handling/domain-and-validation-mapping`); доменные инварианты → `ucp-py-ddd-tactical-review`/`pattern`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — ручная input-валидация в Handler (`validation/input-validated-at-edge`), inbound как голый `dict` (`validation/controller-implements-generated-contract`), деньги во `float`, `os.environ` для required-конфига.
   - **Предупреждение** — Pydantic на агрегате (`validation/domain-invariants-in-aggregate`), дубли правил (`validation/single-source-of-truth`), custom inline в DTO (`validation/custom-constraint-is-reusable`), email-regex вместо `EmailStr`.
   - **Замечание** — английский message, отсутствие говорящего имени у model_validator, один тип на 3+ сценария.

## Что не входит

- Маппинг ошибки в 400/problem+json — `ucp-py-error-handling-review`.
- Доменные инварианты — `ucp-py-ddd-tactical-review` / `ucp-py-pattern-review`.

$ARGUMENTS
