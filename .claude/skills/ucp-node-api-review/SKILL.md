---
name: ucp-node-api-review
lang: node
description: Ревью REST API-контракта/кода NestJS (Node, code-first) по UCP (коды R-URL/MTH/RSP/ERR/OAS-*) — URL и методы, query/JSON camelCase, коллекции, problem+json RFC 9457, заголовки, operationId/@ApiTags.
when_to_use: Ревью контроллеров NestJS, DTO-классов, сгенерированной OpenAPI, Exception Filters.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью REST API (Node / NestJS, code-first)

Ты ревьюишь REST-контракт на соответствие **контракту** `backend/rest-api/rest-api-rules.md` и **Node-реализации**
`backend/rest-api/node/rest-api-style-guide.md`. NestJS code-first: DTO-классы = источник, OpenAPI генерируется.

## Зависимости

- **`.claude/docs/backend/rest-api/rest-api-rules.md`** + **`backend/rest-api/node/rest-api-style-guide.md`**.
- Парные: `backend/validation/node/...` (OAS-инверсия), `backend/error-handling/node/...` (problem+json), `backend/usecase-pattern/node/...` (контроллер→Handler).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй конкретные коды (`R-RSP-X1`, `R-ERR-X1`, `R-URL-X2`), не префикс. Помни инверсию: дубли правил (class-validator + ручной чек) — нарушение, не «не править generated».

2. **Скоп.** Контроллеры (`@Controller`/`@Get`/`@Post`...), request/response DTO-классы, Exception Filters, сгенерированная Swagger-спека, `main.ts` (`setGlobalPrefix`/`enableVersioning`); `git diff`.

3. **Прогон.**
   - **URL/методы (`R-URL/MTH/NEST/ACT/VER-*`):** kebab-case, без trailing-slash, `/api/v1` через `setGlobalPrefix`+URI-versioning; trailing-slash/заглавные/глагол-в-CRUD → `R-URL-X1/X2`; >2 уровня → `R-NEST-X1`; action не-POST → `R-ACT-X2`; версия в query/header → `R-VER-X2`; статусы — `@HttpCode` (`@Delete`→204, action→200).
   - **Query (`R-QRY-*`):** Query-DTO + `transform: true`; CSV-массив → `R-QRY-X3`; `page=0` → `R-QRY-X2`; бизнес-логика в query → `R-QRY-X4`.
   - **JSON/ответы (`R-FLD/RSP-*`):** camelCase, enum UPPER_SNAKE, ISO-даты; `null`/`""` в 2xx → `R-RSP-X1/X2` (проверь `note?: string`, не `string | null`); envelope единичного → `R-RSP-X4`; коллекция без `content`/метаданных → `R-RSP-2`; пустая коллекция как `null` → `R-RSP-7`; create без `201`+`Location` → `R-RSP-3`.
   - **Ошибки (`R-ERR-*`):** problem+json (`application/json` → `R-ERR-X1`); дефолтный `BadRequestException`-формат вместо 400+`VALIDATION_ERROR`+`violations` через `exceptionFactory` → нарушение `R-ERR-5`/`R-ERR-X3`; stack/SQL в 500 → `R-ERR-X4`; `code` UPPER_SNAKE из enum.
   - **Заголовки (`R-HDR-*`):** кастомные с доменным префиксом, `X-`-префикс → `R-HDR-X1`; `Idempotency-Key` для money-POST; `traceparent`.
   - **OpenAPI (`R-OAS-*`):** `operationId` camelCase в `@ApiOperation` (отсутствует → авто `ControllerName_method`), `@ApiTags`, `summary`; схемы из DTO-классов, не голые `any`/`Record`.

4. **Cross-check:** class-validator constraints — `ucp-node-validation-review`; problem+json mapping/иерархия — `ucp-node-error-handling-review`; контроллер→Handler — `ucp-node-pattern-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `null` в 2xx (`R-RSP-X1`), `application/json` вместо problem+json (`R-ERR-X1`), stack/SQL в 500 (`R-ERR-X4`), эндпоинт без `/api`+версии (`R-VER-X3`), CSV-массивы (`R-QRY-X3`).
   - **Предупреждение** — trailing-slash/заглавные в URL (`R-URL-X1/X2`), дефолтный `BadRequestException`-формат вместо 400+violations, `X-`-заголовок (`R-HDR-X1`), envelope единичного (`R-RSP-X4`), action не-POST (`R-ACT-X2`).
   - **Замечание** — нет `operationId`/`summary` (`R-OAS-1/4`), >2 уровня вложенности (`R-NEST-X1`), boolean без `is/has` префикса.

## Что не входит

- class-validator constraints/cross-field — `ucp-node-validation-review`. problem+json иерархия ошибок — `ucp-node-error-handling-review`.
- Контроллер→Handler/слои — `ucp-node-pattern-review`. Rate-limit реализация — `ucp-node-resilience-review`.

$ARGUMENTS
