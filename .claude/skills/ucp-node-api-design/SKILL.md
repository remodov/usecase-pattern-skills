---
name: ucp-node-api-design
lang: node
description: Спроектировать REST API-эндпоинт/ресурс на NestJS code-first (коды R-URL/MTH/QRY/FLD/RSP/ERR/OAS-*) — kebab-case URL + /api/v1 (URI-versioning), JSON camelCase без null в 2xx, DTO на class-validator, problem+json (RFC 9457), operationId + @ApiTags.
when_to_use: Триггеры — «спроектируй эндпоинт X», «REST-ресурс Y на NestJS», «OpenAPI для Z». При создании эндпоинтов и DTO-классов.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# REST API — проектирование (Node / NestJS, code-first)

Ты проектируешь REST-контракт по **контракту** `backend/rest-api/rest-api-rules.md` и **Node-реализации**
`backend/rest-api/node/rest-api-style-guide.md`. NestJS **code-first**: DTO-классы (class-validator) +
декораторы `@nestjs/swagger` → OpenAPI генерируется (`SwaggerModule`, гейт вне production — `NESTBOOT-14`).

## Инструкции

1. **Прочитай** контракт + Node-style-guide (бо́льшая часть правил протокольная — идентична). Коды в обосновании, не в коде. Связанные: `backend/validation/node/...` (DTO-классы, OAS-инверсия), `backend/error-handling/node/...` (problem+json filters), `backend/usecase-pattern/node/...` (контроллер→Handler).

2. **URL/методы/версии** (`R-URL/MTH/NEST/ACT/VER-*`): kebab-case в декораторах (`@Controller('orders')` + `@Get(':id/items')`), без trailing-slash; `app.setGlobalPrefix('api')` + `enableVersioning({ type: VersioningType.URI, defaultVersion: '1' })` → `/api/v1`; метод = декоратор, статус — `@HttpCode` где дефолт NestJS не совпадает (`@Delete`→204, action-`@Post`→200); action всегда `@Post('orders/:id/confirm')`; ≤2 уровня вложенности; path-параметры уникальны (`:orderId`, `:itemId`).

3. **Query** (`R-QRY-*`): Query-DTO-класс + глобальный `ValidationPipe({ transform: true })` (camelCase нативен, алиасы не нужны); `page` 1-based + `size` с `@Type(() => Number)`; массивы — повтор параметра (`@IsArray()`), не CSV; сложный поиск — `POST /resources/search`.

4. **JSON/ответы** (`R-FLD/RSP-*`): camelCase нативен (поля TS-класса); enum UPPER_SNAKE; даты ISO 8601; **нет `null` в 2xx** — незаполненное поле `note?: string` (`undefined` выпадает из JSON), не `null`; коллекция `{content:[...]}`+метаданные; `201`+`Location` на create; пустая коллекция `[]`.

5. **Ошибки** (`R-ERR-*`): problem+json (RFC 9457) через Exception Filters, `code` UPPER_SNAKE из enum; ошибки `ValidationPipe` → `400 VALIDATION_ERROR`+`violations` через `exceptionFactory` (не дефолтный `BadRequestException`-формат); не светить stack/SQL в 500 (делегируй `ucp-node-error-handling-design`).

6. **Заголовки/OpenAPI** (`R-HDR/OAS-*`): кастомные без `X-`; `Idempotency-Key` для money-POST; `traceparent`; `@ApiOperation({ operationId: 'createOrder', summary: '...' })` camelCase + `@ApiTags` на каждом маршруте — иначе NestJS генерирует `ControllerName_method`.

7. **Самопроверка** (§чек-лист) + предложи `ucp-node-api-review`. class-validator-валидация — `ucp-node-validation-design`.

## Антипаттерны, которые НЕ генерировать

- trailing-slash / заглавные / глаголы в CRUD-пути (`R-URL-X1/X2`/`R-MTH`); >2 уровня вложенности (`R-NEST-X1`); версия в query (`R-VER-X2`).
- CSV-массивы в query (`R-QRY-X3`); `page=0` (`R-QRY-X2`); бизнес-логика в query (`R-QRY-X4`).
- `null`/`""` в 2xx (`R-RSP-X1/X2`); envelope для единичного ресурса (`R-RSP-X4`).
- `application/json` для ошибки (`R-ERR-X1`); дефолтный `BadRequestException`-формат вместо 400+problem+json; stack/SQL в 500 (`R-ERR-X4`); `X-`-префикс заголовка (`R-HDR-X1`); схема как голый `any`/`Record` (`R-OAS`/`R-VLD-OAS-X5`).

После работы скилла — обязательно `ucp-node-api-review`.

$ARGUMENTS
