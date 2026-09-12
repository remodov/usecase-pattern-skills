---
name: ucp-py-api-design
lang: python
description: Спроектировать REST API-эндпоинт/ресурс на Python/FastAPI code-first (требования rest-api/*) — kebab-case URL + /api/v1, query camelCase, JSON camelCase без null в 2xx, Pydantic-DTO, problem+json (RFC 9457), operation_id + tags.
when_to_use: Триггеры — «спроектируй эндпоинт X», «REST-ресурс Y на FastAPI», «OpenAPI для Z». При создании эндпоинтов и Pydantic-DTO.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# REST API — проектирование (Python / FastAPI, code-first)

Ты проектируешь REST-контракт по **контракту** `backend/rest-api/spec.md` и **Python-реализации**
`backend/rest-api/references/python/implementation.md`. FastAPI **code-first**: Pydantic-модели + декораторы → OpenAPI генерируется.

## Инструкции

1. **Прочитай** требования `python-style/*` (бо́льшая часть правил протокольная — идентична). Коды в обосновании, не в коде. Связанные: `backend/validation/python/...` (Pydantic-DTO, OAS-инверсия), `backend/error-handling/python/...` (problem+json handler), `backend/usecase-pattern/python/...` (роутер→Dispatcher).

2. **URL/методы/версии** (`R-URL/MTH/NEST/ACT/VER-*`): kebab-case, без trailing-slash (`redirect_slashes=False`), `APIRouter(prefix="/api/v1")`; метод=декоратор + `status_code`; action всегда `POST` (`/orders/{id}/confirm`); ≤2 уровня вложенности.

3. **Query** (`R-QRY-*`): `Query(alias=camelCase)`; `page` 1-based + `size`; массивы — `list[str] = Query(...)` (повтор, не CSV); сложный поиск — `POST /resources/search`.

4. **JSON/ответы** (`R-FLD/RSP-*`): Pydantic `alias_generator=to_camel` + `populate_by_name`; enum `StrEnum` UPPER_SNAKE; даты ISO 8601; **нет `null` в 2xx** (`response_model_exclude_none=True`); коллекция `{content:[...]}`+метаданные; `201`+`Location` на create; пустая коллекция `[]`.

5. **Ошибки** (`R-ERR-*`): problem+json (RFC 9457), `code` UPPER_SNAKE из enum; переопредели `RequestValidationError`-handler на `400 VALIDATION_ERROR`+`violations` (не дефолтный 422); не светить stack/SQL в 500 (делегируй `ucp-py-error-handling-design`).

6. **Заголовки/OpenAPI** (`R-HDR/OAS-*`): кастомные без `X-`; `Idempotency-Key` для money-POST; `traceparent`; `operation_id` camelCase + `tags` + `summary` на каждом маршруте.

7. **Самопроверка** (§чек-лист) + предложи `ucp-py-api-review`. Pydantic-валидация — `ucp-py-validation-design`.

## Антипаттерны, которые НЕ генерировать

- trailing-slash / заглавные / глаголы в CRUD-пути (`R-URL-X1/X2`/`R-MTH`); >2 уровня вложенности (`rest-api/nesting-max-two-levels`); версия в query (`rest-api/version-in-path`).
- CSV-массивы в query (`rest-api/arrays-as-repeated-parameters`); `page=0` (`rest-api/pagination-forms`); бизнес-логика в query (`rest-api/filters-ranges-and-search`).
- `null`/`""` в 2xx (`R-RSP-X1/X2`); envelope для единичного ресурса (`rest-api/single-resource-is-flat`); `nullable: true` (`rest-api/no-nulls-in-successful-response`).
- `application/json` для ошибки (`rest-api/error-body-follows-standard`); дефолтный 422 вместо 400+problem+json; stack/SQL в 500 (`rest-api/no-internals-in-error-body`); `X-`-префикс заголовка (`rest-api/headers-standard-and-prefixed`); контракт как голый `dict` (`R-OAS`/`validation/controller-implements-generated-contract`).

После работы скилла — обязательно `ucp-py-api-review`.

$ARGUMENTS
