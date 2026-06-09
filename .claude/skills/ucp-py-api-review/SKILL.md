---
name: ucp-py-api-review
lang: python
description: Ревью REST API-контракта/кода FastAPI (Python, code-first) по UCP (коды R-URL/MTH/RSP/ERR/OAS-*) — URL и методы, query/JSON camelCase, коллекции, problem+json RFC 9457, заголовки, operation_id/tags.
when_to_use: Ревью роутеров FastAPI, Pydantic-DTO, сгенерированной OpenAPI, exception-handlers.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью REST API (Python / FastAPI, code-first)

Ты ревьюишь REST-контракт на соответствие **контракту** `backend/rest-api/rest-api-rules.md` и **Python-реализации**
`backend/rest-api/python/rest-api-style-guide.md`. FastAPI code-first: Pydantic = источник, OpenAPI генерируется.

## Зависимости

- **`.claude/docs/backend/rest-api/rest-api-rules.md`** + **`backend/rest-api/python/rest-api-style-guide.md`**.
- Парные: `backend/validation/python/...` (OAS-инверсия), `backend/error-handling/python/...` (problem+json), `backend/usecase-pattern/python/...` (роутер→Dispatcher).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй конкретные коды (`R-RSP-X1`, `R-ERR-X1`, `R-URL-X2`), не префикс. Помни инверсию: дубли правил (Pydantic + ручной чек) — нарушение, не «не править generated».

2. **Скоп.** Роутеры (`@router.*`), Pydantic request/response-DTO, exception-handlers, сгенерированный `/openapi.json`, `APIRouter`-конфиг; `git diff`.

3. **Прогон.**
   - **URL/методы (`R-URL/MTH/NEST/ACT/VER-*`):** kebab-case, без trailing-slash, `/api/v1`-префикс; trailing-slash/заглавные/глагол-в-CRUD → `R-URL-X1/X2`; >2 уровня → `R-NEST-X1`; action не-POST → `R-ACT-X2`; версия в query → `R-VER-X2`.
   - **Query (`R-QRY-*`):** camelCase-алиасы; CSV-массив → `R-QRY-X3`; `page=0` → `R-QRY-X2`; бизнес-логика в query → `R-QRY-X4`.
   - **JSON/ответы (`R-FLD/RSP-*`):** camelCase, enum UPPER_SNAKE, ISO-даты; `null`/`""` в 2xx → `R-RSP-X1/X2` (проверь `exclude_none`); envelope единичного → `R-RSP-X4`; коллекция без `content`/метаданных → `R-RSP-2`; пустая коллекция как `null` → `R-RSP-7`.
   - **Ошибки (`R-ERR-*`):** problem+json (`application/json` → `R-ERR-X1`); дефолтный FastAPI 422 вместо 400+`VALIDATION_ERROR`+`violations` → нарушение `R-ERR-5`/`R-ERR-X3`; stack/SQL в 500 → `R-ERR-X4`; `code` UPPER_SNAKE из enum.
   - **Заголовки (`R-HDR-*`):** кастомные с доменным префиксом, `X-`-префикс → `R-HDR-X1`; `Idempotency-Key` для money-POST; `traceparent`.
   - **OpenAPI (`R-OAS-*`):** `operation_id` camelCase (отсутствует → авто-длинный), `tags`, `summary`; контракт = Pydantic, не голый `dict`.

4. **Cross-check:** Pydantic-валидация/constraints — `ucp-py-validation-review`; problem+json mapping/иерархия — `ucp-py-error-handling-review`; роутер→Dispatcher — `ucp-py-pattern-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `null` в 2xx (`R-RSP-X1`), `application/json` вместо problem+json (`R-ERR-X1`), stack/SQL в 500 (`R-ERR-X4`), эндпоинт без `/api`+версии (`R-VER-X3`), CSV-массивы (`R-QRY-X3`).
   - **Предупреждение** — trailing-slash/заглавные в URL (`R-URL-X1/X2`), дефолтный 422 вместо 400+violations, `X-`-заголовок (`R-HDR-X1`), envelope единичного (`R-RSP-X4`), action не-POST (`R-ACT-X2`).
   - **Замечание** — нет `operation_id`/`summary` (`R-OAS-1/4`), >2 уровня вложенности (`R-NEST-X1`), boolean без `is/has` префикса.

## Что не входит

- Pydantic-constraints/cross-field — `ucp-py-validation-review`. problem+json иерархия исключений — `ucp-py-error-handling-review`.
- Роутер→Dispatcher/слои — `ucp-py-pattern-review`. Rate-limit реализация — `ucp-py-resilience-review`.

$ARGUMENTS
