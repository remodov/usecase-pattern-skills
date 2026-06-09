---
name: ucp-py-validation-review
lang: python
description: Ревью валидации входа в Python/FastAPI (Pydantic v2) по UCP (коды R-VLD-*) — DTO как Pydantic-модели на границе, constraints через Field, custom через Annotated+AfterValidator, cross-field через model_validator, BaseSettings, деньги Decimal.
when_to_use: Изменения в Pydantic-моделях, эндпоинтах, validation/types.py или settings.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью валидации (Python / Pydantic v2 / FastAPI)

Ты ревьюишь валидацию входа на соответствие **общему контракту** `backend/validation/validation-rules.md` (`R-VLD-*`)
и **Python-реализации** `backend/validation/python/validation-style-guide.md`. Помни инверсию: FastAPI code-first
(Pydantic = источник, OpenAPI генерируется) — актуально «нет дублей правил», не «не править generated».

## Зависимости

- **`.claude/docs/backend/validation/validation-rules.md`** — контракт (`R-VLD-WHERE-*`/`STD-*`/`CC-*`/`GRP-*`/`XF-*`/`OAS-*`/`CFG-*`/`MSG-*`).
- **`.claude/docs/backend/validation/python/validation-style-guide.md`** — Pydantic-реализация.
- Парные: `backend/error-handling/error-handling-rules.md` (`R-ERR-MAP-2`), `backend/ddd-tactical/ddd-tactical-rules.md` (инварианты ≠ валидация).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-VLD-WHERE-X1`), не префикс.

2. **Скоп.** `**/*request*.py`, `**/*dto*.py`, эндпоинты, `backend/validation/types.py`, `settings.py`/`config.py`, `git diff` на `.py`.

3. **Прогон.**
   - **WHERE:** входной DTO — Pydantic-модель в сигнатуре эндпоинта? (`R-VLD-WHERE-1`). Ручная `if ...: raise` в Handler → `R-VLD-WHERE-X1`. Pydantic-constraints на агрегате → `R-VLD-WHERE-X4`. Конфиг — `BaseSettings`? (`R-VLD-WHERE-2`/`CFG-1`).
   - **STD:** `Field`-constraints/спец-типы (`EmailStr`/`UUID`); деньги — `Decimal` не `float`. `@field_validator` «не None» на non-Optional → `R-VLD-STD-X1`; email-regex вместо `EmailStr` → `R-VLD-STD-X2`.
   - **CC:** custom — `Annotated[..., AfterValidator]` в общем модуле, имя по домену, на не-None? inline в DTO → `R-VLD-CC-X2`.
   - **XF:** cross-field — `@model_validator(mode="after")`, говорящее имя; в Handler перед dispatch → `R-VLD-XF-X2`.
   - **GRP:** разные сценарии — отдельные модели, не один тип с режимами (`R-VLD-GRP-X1`).
   - **OAS (code-first):** контракт = Pydantic-модель, не голый `dict` (`R-VLD-OAS-X5`); дубли правил (Pydantic + ручной чек) → `R-VLD-OAS-X4`.
   - **CFG:** `BaseSettings`, required без default, nested валидируется; `os.environ[...]` для required → `R-VLD-CFG-X2`.
   - **MSG:** сообщения на русском, человекочитаемые; английский/тех-термины → `R-VLD-MSG-X1/X2`.

4. **Cross-check:** 400-маппинг → `ucp-py-error-handling-review` (`R-ERR-MAP-2`); доменные инварианты → `ucp-py-ddd-tactical-review`/`pattern`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — ручная input-валидация в Handler (`R-VLD-WHERE-X1`), inbound как голый `dict` (`R-VLD-OAS-X5`), деньги во `float`, `os.environ` для required-конфига.
   - **Предупреждение** — Pydantic на агрегате (`R-VLD-WHERE-X4`), дубли правил (`R-VLD-OAS-X4`), custom inline в DTO (`R-VLD-CC-X2`), email-regex вместо `EmailStr`.
   - **Замечание** — английский message, отсутствие говорящего имени у model_validator, один тип на 3+ сценария.

## Что не входит

- Маппинг ошибки в 400/problem+json — `ucp-py-error-handling-review`.
- Доменные инварианты — `ucp-py-ddd-tactical-review` / `ucp-py-pattern-review`.

$ARGUMENTS
