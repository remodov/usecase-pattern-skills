---
name: ucp-py-api-review
lang: python
description: Ревью REST API-контракта/кода FastAPI (Python, code-first) по UCP (требования rest-api/*) — URL и методы, query/JSON camelCase, коллекции, problem+json RFC 9457, заголовки, operation_id/tags.
when_to_use: Ревью роутеров FastAPI, Pydantic-DTO, сгенерированной OpenAPI, exception-handlers.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью REST API (Python / FastAPI, code-first)

Ты ревьюишь REST-контракт на соответствие **контракту** `backend/rest-api/spec.md` и **Python-реализации**
`backend/rest-api/references/python/implementation.md`. FastAPI code-first: Pydantic = источник, OpenAPI генерируется.

## Зависимости

- **`.claude/docs/backend/rest-api/spec.md`** + **`backend/rest-api/references/python/implementation.md`**.
- Парные: `backend/validation/python/...` (OAS-инверсия), `backend/error-handling/python/...` (problem+json), `backend/usecase-pattern/python/...` (роутер→Dispatcher).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй конкретные коды (`rest-api/no-nulls-in-successful-response`, `rest-api/error-body-follows-standard`, `rest-api/path-lowercase-kebab-case`), не префикс. Помни инверсию: дубли правил (Pydantic + ручной чек) — нарушение, не «не править generated».

2. **Скоп.** Роутеры (`@router.*`), Pydantic request/response-DTO, exception-handlers, сгенерированный `/openapi.json`, `APIRouter`-конфиг; `git diff`.

3. **Прогон.**
   - **URL/методы (`R-URL/MTH/NEST/ACT/VER-*`):** kebab-case, без trailing-slash, `/api/v1`-префикс; trailing-slash/заглавные/глагол-в-CRUD → `R-URL-X1/X2`; >2 уровня → `rest-api/nesting-max-two-levels`; action не-POST → `rest-api/action-endpoints-shape`; версия в query → `rest-api/version-in-path`.
   - **Query (`R-QRY-*`):** camelCase-алиасы; CSV-массив → `rest-api/arrays-as-repeated-parameters`; `page=0` → `rest-api/pagination-forms`; бизнес-логика в query → `rest-api/filters-ranges-and-search`.
   - **JSON/ответы (`R-FLD/RSP-*`):** camelCase, enum UPPER_SNAKE, ISO-даты; `null`/`""` в 2xx → `R-RSP-X1/X2` (проверь `exclude_none`); envelope единичного → `rest-api/single-resource-is-flat`; коллекция без `content`/метаданных → `rest-api/collection-response-shape`; пустая коллекция как `null` → `rest-api/no-nulls-in-successful-response`.
   - **Ошибки (`R-ERR-*`):** problem+json (`application/json` → `rest-api/error-body-follows-standard`); дефолтный FastAPI 422 вместо 400+`VALIDATION_ERROR`+`violations` → нарушение `rest-api/validation-errors-list-violations`/`rest-api/error-status-codes-limited`; stack/SQL в 500 → `rest-api/no-internals-in-error-body`; `code` UPPER_SNAKE из enum.
   - **Заголовки (`R-HDR-*`):** кастомные с доменным префиксом, `X-`-префикс → `rest-api/headers-standard-and-prefixed`; `Idempotency-Key` для money-POST; `traceparent`.
   - **OpenAPI (`R-OAS-*`):** `operation_id` camelCase (отсутствует → авто-длинный), `tags`, `summary`; контракт = Pydantic, не голый `dict`.

4. **Cross-check:** Pydantic-валидация/constraints — `ucp-py-validation-review`; problem+json mapping/иерархия — `ucp-py-error-handling-review`; роутер→Dispatcher — `ucp-py-pattern-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `null` в 2xx (`rest-api/no-nulls-in-successful-response`), `application/json` вместо problem+json (`rest-api/error-body-follows-standard`), stack/SQL в 500 (`rest-api/no-internals-in-error-body`), эндпоинт без `/api`+версии (`rest-api/version-in-path`), CSV-массивы (`rest-api/arrays-as-repeated-parameters`).
   - **Предупреждение** — trailing-slash/заглавные в URL (`R-URL-X1/X2`), дефолтный 422 вместо 400+violations, `X-`-заголовок (`rest-api/headers-standard-and-prefixed`), envelope единичного (`rest-api/single-resource-is-flat`), action не-POST (`rest-api/action-endpoints-shape`).
   - **Замечание** — нет `operation_id`/`summary` (`R-OAS-1/4`), >2 уровня вложенности (`rest-api/nesting-max-two-levels`), boolean без `is/has` префикса.

## Что не входит

- Pydantic-constraints/cross-field — `ucp-py-validation-review`. problem+json иерархия исключений — `ucp-py-error-handling-review`.
- Роутер→Dispatcher/слои — `ucp-py-pattern-review`. Rate-limit реализация — `ucp-py-resilience-review`.

$ARGUMENTS
