---
name: ucp-node-api-review
lang: node
description: Ревью REST API-контракта/кода NestJS (Node, code-first) по UCP (требования rest-api/*) — URL и методы, query/JSON camelCase, коллекции, problem+json RFC 9457, заголовки, operationId/@ApiTags.
when_to_use: Ревью контроллеров NestJS, DTO-классов, сгенерированной OpenAPI, Exception Filters.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью REST API (Node / NestJS, code-first)

Ты ревьюишь REST-контракт на соответствие **контракту** `backend/rest-api/spec.md` и **Node-реализации**
`backend/rest-api/references/node/implementation.md`. NestJS code-first: DTO-классы = источник, OpenAPI генерируется.

## Зависимости

- **`.claude/docs/backend/rest-api/spec.md`** + **`backend/rest-api/references/node/implementation.md`**.
- Парные: `backend/validation/node/...` (OAS-инверсия), `backend/error-handling/node/...` (problem+json), `backend/usecase-pattern/node/...` (контроллер→Handler).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй конкретные коды (`rest-api/no-nulls-in-successful-response`, `rest-api/error-body-follows-standard`, `rest-api/path-lowercase-kebab-case`), не префикс. Помни инверсию: дубли правил (class-validator + ручной чек) — нарушение, не «не править generated».

2. **Скоп.** Контроллеры (`@Controller`/`@Get`/`@Post`...), request/response DTO-классы, Exception Filters, сгенерированная Swagger-спека, `main.ts` (`setGlobalPrefix`/`enableVersioning`); `git diff`.

3. **Прогон.**
   - **URL/методы (`R-URL/MTH/NEST/ACT/VER-*`):** kebab-case, без trailing-slash, `/api/v1` через `setGlobalPrefix`+URI-versioning; trailing-slash/заглавные/глагол-в-CRUD → `R-URL-X1/X2`; >2 уровня → `rest-api/nesting-max-two-levels`; action не-POST → `rest-api/action-endpoints-shape`; версия в query/header → `rest-api/version-in-path`; статусы — `@HttpCode` (`@Delete`→204, action→200).
   - **Query (`R-QRY-*`):** Query-DTO + `transform: true`; CSV-массив → `rest-api/arrays-as-repeated-parameters`; `page=0` → `rest-api/pagination-forms`; бизнес-логика в query → `rest-api/filters-ranges-and-search`.
   - **JSON/ответы (`R-FLD/RSP-*`):** camelCase, enum UPPER_SNAKE, ISO-даты; `null`/`""` в 2xx → `R-RSP-X1/X2` (проверь `note?: string`, не `string | null`); envelope единичного → `rest-api/single-resource-is-flat`; коллекция без `content`/метаданных → `rest-api/collection-response-shape`; пустая коллекция как `null` → `rest-api/no-nulls-in-successful-response`; create без `201`+`Location` → `rest-api/status-codes-and-bodies`.
   - **Ошибки (`R-ERR-*`):** problem+json (`application/json` → `rest-api/error-body-follows-standard`); дефолтный `BadRequestException`-формат вместо 400+`VALIDATION_ERROR`+`violations` через `exceptionFactory` → нарушение `rest-api/validation-errors-list-violations`/`rest-api/error-status-codes-limited`; stack/SQL в 500 → `rest-api/no-internals-in-error-body`; `code` UPPER_SNAKE из enum.
   - **Заголовки (`R-HDR-*`):** кастомные с доменным префиксом, `X-`-префикс → `rest-api/headers-standard-and-prefixed`; `Idempotency-Key` для money-POST; `traceparent`.
   - **OpenAPI (`R-OAS-*`):** `operationId` camelCase в `@ApiOperation` (отсутствует → авто `ControllerName_method`), `@ApiTags`, `summary`; схемы из DTO-классов, не голые `any`/`Record`.

4. **Cross-check:** class-validator constraints — `ucp-node-validation-review`; problem+json mapping/иерархия — `ucp-node-error-handling-review`; контроллер→Handler — `ucp-node-pattern-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `null` в 2xx (`rest-api/no-nulls-in-successful-response`), `application/json` вместо problem+json (`rest-api/error-body-follows-standard`), stack/SQL в 500 (`rest-api/no-internals-in-error-body`), эндпоинт без `/api`+версии (`rest-api/version-in-path`), CSV-массивы (`rest-api/arrays-as-repeated-parameters`).
   - **Предупреждение** — trailing-slash/заглавные в URL (`R-URL-X1/X2`), дефолтный `BadRequestException`-формат вместо 400+violations, `X-`-заголовок (`rest-api/headers-standard-and-prefixed`), envelope единичного (`rest-api/single-resource-is-flat`), action не-POST (`rest-api/action-endpoints-shape`).
   - **Замечание** — нет `operationId`/`summary` (`R-OAS-1/4`), >2 уровня вложенности (`rest-api/nesting-max-two-levels`), boolean без `is/has` префикса.

## Что не входит

- class-validator constraints/cross-field — `ucp-node-validation-review`. problem+json иерархия ошибок — `ucp-node-error-handling-review`.
- Контроллер→Handler/слои — `ucp-node-pattern-review`. Rate-limit реализация — `ucp-node-resilience-review`.

$ARGUMENTS
