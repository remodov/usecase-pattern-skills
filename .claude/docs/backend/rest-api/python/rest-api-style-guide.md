# REST API — Python Style Guide (FastAPI, code-first)

Реализация язык-нейтрального контракта `../rest-api-rules.md` на FastAPI. Коды общие с Java. **Бо́льшая часть
правил — протокольного уровня** (URL, методы, статусы, заголовки, problem+json, пагинация) и **идентична** —
здесь только то, что меняется в Python.

## Ключевая инверсия: code-first

Java — **contract-first**: OpenAPI-спека → генерация серверных интерфейсов; правило «не править generated».
FastAPI — **code-first**: Pydantic-модели + декораторы маршрутов → OpenAPI **генерируется** (`/openapi.json`).
Поэтому актуальная формулировка для Python: **Pydantic-модель = источник контракта, дублировать правила нельзя**
(cross-ref та же инверсия в `backend/validation/python` `R-VLD-OAS`). Перед мержем — review сгенерированной спеки на
соответствие разделам ниже.

## URL / ресурсы / методы / вложенность / actions / версии (`R-PRIN/URL/RES/MTH/NEST/ALIAS/ACT/VER-*`)

Протокольные — идентичны Java. Специфика FastAPI:
- `R-URL-*` — путь в декораторе (`@router.get("/orders/{order_id}/items")`), kebab-case, без trailing-slash
  (`redirect_slashes=False`, иначе FastAPI редиректит). `R-VER-3` — `APIRouter(prefix="/api/v1")`.
- `R-MTH-*` — метод = декоратор (`@router.post`); статусы — `status_code=201`. `R-ACT-3` — action всегда `POST`
  (`POST /orders/{id}/confirm`).
- `R-NEST-4`/`R-OAS-3` — path-параметр в FastAPI именуется уникально (`{order_id}`), это требование инструмента;
  в дизайне — `{id}`.

## Query-параметры (`R-QRY-*`)

`Query(...)` с camelCase-алиасами (`Query(alias="pageSize")`); `page` 1-based + `size`; диапазоны `*From`/`*To`;
сортировка `sort=field,dir`; массивы — повтор параметра (`list[str] = Query(...)`, FastAPI = `style: form, explode:
true`), **не** comma-separated (`R-QRY-X3`); сложный поиск — `POST /resources/search` (`R-QRY-9`).

## JSON: поля и ответы (`R-FLD/RSP-*`)

`R-FLD-1` — camelCase через Pydantic `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`.
`R-FLD-2` — даты ISO 8601 (Pydantic сериализует `datetime` так по умолчанию). `R-FLD-3` — enum-значения
UPPER_SNAKE (`class OrderStatus(StrEnum)`). `R-RSP-X1` — **нет `null` в 2xx**: `response_model_exclude_none=True`
на маршруте / `model_config exclude_none`. `R-RSP-2` — коллекция `{ "content": [...] }` + метаданные пагинации.
`R-RSP-3` — `201` + `Location`-заголовок + тело-ресурс. `R-RSP-7` — пустая коллекция `[]`, не `null`. `R-RSP-X3` —
не `Optional`-в-ответе-ради-`null`; поле либо есть, либо отсутствует (управляй `exclude_none`/`required`).

## Заголовки / ошибки / rate-limit (`R-HDR/ERR/RATE-*`)

`R-HDR-*` — стандартные заголовки; кастомные с доменным префиксом, **без `X-`**; `Idempotency-Key`; `traceparent`
(W3C). `R-ERR-*` — **problem+json (RFC 9457)**: exception-handler возвращает `Response(media_type="application/
problem+json")` (cross-ref `backend/error-handling/python` `R-ERR-MAP-*`); `code` UPPER_SNAKE из enum; валидация → `400`
`VALIDATION_ERROR` + `violations` (маппинг `RequestValidationError` FastAPI/Pydantic в этот формат, не дефолтный
422 FastAPI — переопредели handler); не светить stack/SQL в `500` (`R-ERR-X4`). `R-RATE-*` — `429` + `Retry-After`
+ `RateLimit-*` (через middleware/gateway).

> Внимание: дефолтный FastAPI отдаёт `422` на ошибку валидации — переопредели `RequestValidationError`-handler
> на `400` + problem+json (`R-ERR-5`, `R-ERR-X3` запрещает `422`).

## Файлы / deprecation / batch / async / локализация (`R-FILE/DEP/BATCH/ASYNC/LOC-*`)

Протокольные — идентичны. FastAPI: `R-FILE-*` — `UploadFile` + `multipart/form-data`, скачивание —
`StreamingResponse`/`FileResponse` + `Content-Disposition`. `R-ASYNC-*` — `202` + `taskId`/`statusUrl`, опрос
`GET /api/v1/tasks/{id}`. `R-LOC-*` — `Accept-Language`, дефолт `ru`, не локализовать enum/URI (`R-LOC-X1`).

## OpenAPI-метаданные (`R-OAS-*`)

`R-OAS-1` — `operation_id` в `camelCase` на каждом маршруте (`@router.post(..., operation_id="createOrder")`) —
FastAPI иначе генерирует длинные авто-id. `R-OAS-2` — `tags=["Orders"]`, action к тегу родителя. `R-OAS-4` —
`summary`/`description` в декораторе. Контракт = Pydantic-модели (не голый `dict`, cross-ref `R-VLD-OAS-X5`).

## Чеклист подключения к новому сервису (Python)

1. Code-first: Pydantic-модели — источник; нет дублирования правил; спека сгенерирована.
2. URL kebab-case без trailing-slash; `/api/v1`-префикс; методы/статусы по семантике; action = POST.
3. Query camelCase, page 1-based, массивы повтором (не CSV); сложный поиск — POST /search.
4. JSON camelCase, enum UPPER_SNAKE, нет `null` в 2xx (`exclude_none`), коллекция `content`+метаданные.
5. problem+json (RFC 9457), `400 VALIDATION_ERROR`+`violations` (переопределён 422→400), нет stack/SQL в 500.
6. Кастомные заголовки без `X-`; `Idempotency-Key`/`traceparent`; `429`+`Retry-After`.
7. `operation_id` camelCase, `tags`, `summary` на каждом маршруте.
