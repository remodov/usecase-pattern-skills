---
name: ucp-py-validation-design
lang: python
description: Спроектировать валидацию входа в FastAPI-сервисе на Python, Pydantic v2 (коды R-VLD-*) — DTO как Pydantic-модели на границе, constraints через Field, custom через Annotated+AfterValidator, cross-field model_validator, BaseSettings-конфиг.
when_to_use: Триггеры — «валидация запроса в FastAPI», «pydantic-модель для X», «настрой BaseSettings». При новом эндпоинте/DTO/конфиге.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Проектирование валидации (Python / Pydantic v2 / FastAPI)

Ты проектируешь валидацию входа согласно **общему контракту** `backend/validation/validation-rules.md` (`R-VLD-*`)
и его **Python-реализации** `backend/validation/python/validation-style-guide.md` (Pydantic v2, code-first).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/validation/validation-rules.md` — контракт, коды `R-VLD-*`.
   - `.claude/docs/backend/validation/python/validation-style-guide.md` — Pydantic-реализация (Field/Annotated/model_validator/BaseSettings).
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — как `RequestValidationError` станет 400 (`R-ERR-MAP-2`).

2. **Определи объект.** Входной HTTP-DTO эндпоинта / nested-DTO / конфиг / cross-field-правило.

3. **Произведи код** (Pydantic v2, тайп-хинты; без комментариев; коды правил НЕ цитируй в коде):
   - Входные DTO — `BaseModel` в сигнатуре эндпоинта; required vs `| None`; constraints через `Field(ge=,le=,min_length=,...)`/спец-типы (`EmailStr`/`UUID`); деньги — `Decimal`, не `float` (`R-VLD-STD-*`, `R-VLD-WHERE-1/4`).
   - Custom — `Annotated[T, AfterValidator(fn)]` в `backend/validation/types.py`, имя по домену, на не-None (`R-VLD-CC-*`).
   - Cross-field — `@model_validator(mode="after")` с говорящим именем (`R-VLD-XF-1/2`).
   - Конфиг — `pydantic-settings BaseSettings`, required без default, nested валидируется (`R-VLD-CFG-*`).
   - Сообщения валидаторов — на русском, человекочитаемые (`R-VLD-MSG-*`).

4. **Самопроверка** — чеклист из `python/validation-style-guide.md`.

5. **Финальный шаг:** предложи «запусти `ucp-py-validation-review`».

## Антипаттерны, которые НЕ генерировать

- Ручная `if req.x < 0: raise` в Handler (`R-VLD-WHERE-X1`); повторная валидация UseCase-команды (`R-VLD-WHERE-X2`).
- Pydantic-constraints на доменном агрегате (`R-VLD-WHERE-X4`); инвариант — в конструкторе агрегата.
- `@field_validator` «не None» на non-Optional (`R-VLD-STD-X1`); самописный email-regex вместо `EmailStr` (`R-VLD-STD-X2`).
- Custom-валидатор inline в DTO (`R-VLD-CC-X2`); деньги во `float`.
- `os.environ[...]` для required-конфига вместо `BaseSettings` (`R-VLD-CFG-X2`); дубли правил (`R-VLD-OAS-X4`).
- Английский / технические термины в пользовательском сообщении (`R-VLD-MSG-X1/X2`).

После работы скилла — обязательно `ucp-py-validation-review`.

$ARGUMENTS
