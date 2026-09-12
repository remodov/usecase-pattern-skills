---
name: ucp-py-validation-design
lang: python
description: Спроектировать валидацию входа в FastAPI-сервисе на Python, Pydantic v2 (требования validation/*) — DTO как Pydantic-модели на границе, constraints через Field, custom через Annotated+AfterValidator, cross-field model_validator, BaseSettings-конфиг.
when_to_use: Триггеры — «валидация запроса в FastAPI», «pydantic-модель для X», «настрой BaseSettings». При новом эндпоинте/DTO/конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Проектирование валидации (Python / Pydantic v2 / FastAPI)

Ты проектируешь валидацию входа согласно **общему контракту** `backend/validation/spec.md` (`R-VLD-*`)
и его **Python-реализации** `backend/validation/references/python/implementation.md` (Pydantic v2, code-first).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/validation/spec.md` — контракт, коды `R-VLD-*`.
   - `.claude/docs/backend/validation/references/python/implementation.md` — Pydantic-реализация (Field/Annotated/model_validator/BaseSettings).
   - `.claude/docs/backend/error-handling/spec.md` — как `RequestValidationError` станет 400 (`error-handling/domain-and-validation-mapping`).

2. **Определи объект.** Входной HTTP-DTO эндпоинта / nested-DTO / конфиг / cross-field-правило.

3. **Произведи код** (Pydantic v2, тайп-хинты; без комментариев; коды правил НЕ цитируй в коде):
   - Входные DTO — `BaseModel` в сигнатуре эндпоинта; required vs `| None`; constraints через `Field(ge=,le=,min_length=,...)`/спец-типы (`EmailStr`/`UUID`); деньги — `Decimal`, не `float` (`R-VLD-STD-*`, `R-VLD-WHERE-1/4`).
   - Custom — `Annotated[T, AfterValidator(fn)]` в `backend/validation/types.py`, имя по домену, на не-None (`R-VLD-CC-*`).
   - Cross-field — `@model_validator(mode="after")` с говорящим именем (`R-VLD-XF-1/2`).
   - Конфиг — `pydantic-settings BaseSettings`, required без default, nested валидируется (`R-VLD-CFG-*`).
   - Сообщения валидаторов — на русском, человекочитаемые (`R-VLD-MSG-*`).

4. **Самопроверка** — чеклист из `python/implementation.md`.

5. **Финальный шаг:** предложи «запусти `ucp-py-validation-review`».

## Антипаттерны, которые НЕ генерировать

- Ручная `if req.x < 0: raise` в Handler (`validation/input-validated-at-edge`); повторная валидация UseCase-команды (`validation/no-revalidation-after-edge`).
- Pydantic-constraints на доменном агрегате (`validation/domain-invariants-in-aggregate`); инвариант — в конструкторе агрегата.
- `@field_validator` «не None» на non-Optional (`validation/no-false-or-composite-constraints`); самописный email-regex вместо `EmailStr` (`validation/standard-constraints-preferred`).
- Custom-валидатор inline в DTO (`validation/custom-constraint-is-reusable`); деньги во `float`.
- `os.environ[...]` для required-конфига вместо `BaseSettings` (`validation/config-validated-at-startup`); дубли правил (`validation/single-source-of-truth`).
- Английский / технические термины в пользовательском сообщении (`R-VLD-MSG-X1/X2`).

После работы скилла — обязательно `ucp-py-validation-review`.

$ARGUMENTS
