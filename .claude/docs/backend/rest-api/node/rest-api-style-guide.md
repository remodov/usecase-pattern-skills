# REST API — Node Style Guide (NestJS, code-first)

Реализация язык-нейтрального контракта `../rest-api-rules.md` на NestJS. Коды общие с Java и Python.
**Бо́льшая часть правил — протокольного уровня** (URL, методы, статусы, заголовки, problem+json, пагинация)
и **идентична** — здесь только то, что меняется в Node.

## Ключевая инверсия: code-first

Java — **contract-first** (OpenAPI → generated interfaces). NestJS, как и FastAPI, — **code-first**:
DTO-классы (class-validator) + декораторы `@nestjs/swagger` → OpenAPI **генерируется** (`SwaggerModule`,
гейт вне production — `NESTBOOT-14`). Формулировка для Node: **DTO-класс = источник контракта, дублировать
правила нельзя** (cross-ref `R-VLD-OAS-*` в `backend/validation/node`). Перед мержем — review сгенерированной
спеки на соответствие разделам ниже.

## URL / ресурсы / методы / вложенность / actions / версии (`R-PRIN/URL/RES/MTH/NEST/ALIAS/ACT/VER-*`)

Протокольные — идентичны Java. Специфика NestJS:
- `R-URL-*` — путь в декораторе (`@Controller('orders')` + `@Get(':id/items')`), kebab-case; NestJS не
  редиректит trailing-slash сам — не объявлять пути со слешем на конце.
- `R-VER-1..3` — `app.setGlobalPrefix('api')` + `app.enableVersioning({ type: VersioningType.URI, defaultVersion: '1' })`
  → `/api/v1/...`. Версия только в URI, не в header/query (`R-VER-X2`).
- `R-MTH-*` — метод = декоратор (`@Post()`); статусы — `@HttpCode(...)` там, где дефолт NestJS не совпадает:
  `@Delete` → `@HttpCode(204)` (`R-RSP-5`), action-`@Post` → `@HttpCode(200)` (`R-RSP-6`); `@Post`-создание
  отдаёт 201 по дефолту (`R-RSP-3`).
- `R-ACT-3` — action-эндпоинт всегда `@Post('orders/:id/confirm')`.
- `R-NEST-4`/`R-OAS-3` — path-параметр в коде именуется уникально (`:orderId`, `:itemId`) — требование
  Swagger-инструмента; в дизайн-документации — `{id}`.

## Query-параметры (`R-QRY-*`)

Query-DTO-класс + глобальный `ValidationPipe({ transform: true })` — camelCase нативен для TS, алиасы не нужны;
`page` 1-based + `size` с `@Type(() => Number)`; диапазоны `*From`/`*To`; сортировка `sort=field,dir`;
массивы — повтор параметра (`@IsArray()` на поле, Express парсит `?status=A&status=B` в массив), **не**
comma-separated (`R-QRY-X3`); сложный поиск — `POST /resources/search` (`R-QRY-9`).

## JSON: поля и ответы (`R-FLD/RSP-*`)

`R-FLD-1` — camelCase нативен (поля TS-класса). `R-FLD-2` — даты ISO 8601 (`Date` сериализуется в ISO при
`JSON.stringify`). `R-FLD-3` — enum-значения UPPER_SNAKE (`enum OrderStatus { CONFIRMED = 'CONFIRMED' }`).
`R-RSP-X1` — **нет `null` в 2xx**: незаполненное поле — `undefined` (выпадает из JSON), не `null`:

```ts
// PREFER
note?: string;                       // отсутствует в ответе, если не заполнено
// AVOID
note: string | null = null;          // null попадёт в JSON — нарушение R-RSP-X1
```

`R-RSP-2` — коллекция `{ "content": [...] }` + метаданные пагинации. `R-RSP-3` — 201 + `Location`
(`res.location(...)` или interceptor) + тело-ресурс. `R-RSP-7` — пустая коллекция `[]`, не `null`.
`R-RSP-X4` — без envelope для единичного ресурса (response-DTO — сам ресурс).

## Заголовки / ошибки / rate-limit (`R-HDR/ERR/RATE-*`)

`R-HDR-*` — стандартные заголовки; кастомные с доменным префиксом, **без `X-`**; `Idempotency-Key`
(cross-ref `AUTH-19`); `traceparent` (W3C, `@opentelemetry/instrumentation-http` прокидывает). `R-ERR-*` —
**problem+json (RFC 9457)** через Exception Filters: хелпер `sendProblem` и маппинг типов — в
`backend/error-handling/node` (`R-ERR-MAP-*`); `code` UPPER_SNAKE из enum; ошибки `ValidationPipe` →
`400 VALIDATION_ERROR` + `violations` через `exceptionFactory`, не дефолтный `BadRequestException`-формат
NestJS; не светить stack/SQL в `500` (`R-ERR-X4`). `R-RATE-*` — `429` + `Retry-After` + `RateLimit-*`
(`@nestjs/throttler` или gateway; дефолтный throttler не шлёт `RateLimit-*` — добавить).

## Файлы / deprecation / batch / async / локализация (`R-FILE/DEP/BATCH/ASYNC/LOC-*`)

Протокольные — идентичны. NestJS: `R-FILE-*` — `@UseInterceptors(FileInterceptor('file'))` + `@UploadedFile()`
(`multipart/form-data`), скачивание — `StreamableFile` + `Content-Disposition`. `R-DEP-*` — `@ApiOperation({
deprecated: true })` + заголовки `Sunset`/`Deprecation` (interceptor). `R-ASYNC-*` — `202` + `taskId`/`statusUrl`,
опрос `GET /api/v1/tasks/{id}`. `R-LOC-*` — `Accept-Language` (например, `nestjs-i18n`), дефолт `ru`,
не локализовать enum/URI (`R-LOC-X1`).

## OpenAPI-метаданные (`R-OAS-*`)

`R-OAS-1` — `operationId` в `camelCase` на каждом маршруте: `@ApiOperation({ operationId: 'createOrder',
summary: '...' })` — иначе NestJS генерирует `ControllerName_method`. `R-OAS-2` — `@ApiTags('Orders')` на
контроллере, action к тегу родителя. `R-OAS-4` — `summary` обязателен, `description` по необходимости.
Схемы — из DTO-классов (`@ApiProperty` или CLI-plugin `@nestjs/swagger`); не голые `any`/`Record`
(cross-ref `R-VLD-OAS-X5`).

## Чеклист подключения к новому сервису (Node/NestJS)

1. Code-first: DTO-классы — источник; `SwaggerModule` генерирует спеку (вне production); нет дублей правил.
2. URL kebab-case; `setGlobalPrefix('api')` + URI-versioning `v1`; методы/статусы по семантике (`@HttpCode`
   на DELETE→204, action→200); action = POST.
3. Query через DTO + `transform: true`, page 1-based, массивы повтором (не CSV); сложный поиск — POST /search.
4. JSON camelCase, enum UPPER_SNAKE, нет `null` в 2xx (`undefined`-поля, не `null`), коллекция `content`+метаданные.
5. problem+json (RFC 9457) через Exception Filters, `400 VALIDATION_ERROR`+`violations` через `exceptionFactory`,
   нет stack/SQL в 500.
6. Кастомные заголовки без `X-`; `Idempotency-Key`/`traceparent`; `429`+`Retry-After`+`RateLimit-*`.
7. `operationId` camelCase, `@ApiTags`, `summary` на каждом маршруте.
