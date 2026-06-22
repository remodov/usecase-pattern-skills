# REST API — Python Style Guide (FastAPI, contract-first codegen)

Реализация язык-нейтрального контракта `../rest-api-rules.md` на FastAPI. Коды общие с Java. **Бо́льшая часть
правил — протокольного уровня** (URL, методы, статусы, заголовки, problem+json, пагинация) и **идентична** —
здесь только то, что меняется в Python.

## Парадигма: contract-first через codegen

Командный канон на UCP-сервисах — **contract-first** (как в Java): источник истины — `doc/openapi.yaml`, из него
`datamodel-codegen` генерирует Pydantic v2-схемы (concern `codegen`, `PYGEN-SC-1..6`). Контракт первичен; DTO-схемы
**не пишутся руками** — правило «не править сгенерированное» действует (`PYGEN-SC-X2`), правки только в `ApiBaseModel`
поверх генерации (`PYGEN-SC-5`). Сгенерированные схемы дают `snake_case` поля + `camelCase` alias, `populate_by_name`,
`StrEnum`, `exclude_none` ровно как требуют разделы ниже. Перед мержем — review контракта и сгенерированных схем на
соответствие разделам ниже (cross-ref та же парадигма в `backend/validation/python` `R-VLD-OAS`). Фрагмент контракта
и команда генерации — в разделе OpenAPI ниже.

> **Альтернатива — code-first.** Чистый FastAPI допускает обратный поток: Pydantic-модели руками + декораторы →
> OpenAPI **генерируется** (`/openapi.json`); тогда модель = источник контракта, дублировать правила нельзя.
> Применять, **только** если сервис сознательно не использует codegen-трек.

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

```python
@router.get("/orders", operation_id="listOrders", tags=["Orders"])      # R-OAS-1/2
async def list_orders(
    page: Annotated[int, Query(ge=1)] = 1,                               # R-QRY-4: 1-based, не 0-based (R-QRY-X2)
    size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,    # R-QRY-1: camelCase alias
    statuses: Annotated[list[OrderStatus], Query(alias="status")] = [],  # R-QRY-8: массив повтором ?status=A&status=B
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,   # R-QRY-3: диапазон *From/*To
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    sort: Annotated[str, Query()] = "createdAt,desc",                    # R-QRY-6: field,dir
    repo: OrderQueryRepository = Depends(get_order_query_repository),    # БД — только через репозиторий (R-SQLA-REPO)
) -> OrderPage:
    # page 1-based: конвертацию page-1 делает репозиторий в одном месте, не в роутере
    return await repo.find_page(page=page, size=size, statuses=statuses,
                                date_from=date_from, date_to=date_to, sort=sort)
```

> `?status=CREATED,CONFIRMED` (CSV) — `R-QRY-X3`. FastAPI с `list[...]` = `?status=CREATED&status=CONFIRMED`.
> Raw-`select(...)` в роутере — запрещено; пагинация/фильтры исполняются в `OrderQueryRepository` (`R-SQLA-REPO`).

## JSON: поля и ответы (`R-FLD/RSP-*`)

`R-FLD-1` — camelCase через Pydantic `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)`.
`R-FLD-2` — даты ISO 8601 (Pydantic сериализует `datetime` так по умолчанию). `R-FLD-3` — enum-значения
UPPER_SNAKE (`class OrderStatus(StrEnum)`). `R-RSP-X1` — **нет `null` в 2xx**: `response_model_exclude_none=True`
на маршруте / `model_config exclude_none`. `R-RSP-2` — коллекция `{ "items": [...] }` + метаданные пагинации.
`R-RSP-3` — `201` + `Location`-заголовок + тело-ресурс. `R-RSP-7` — пустая коллекция `[]`, не `null`. `R-RSP-X3` —
не `Optional`-в-ответе-ради-`null`; поле либо есть, либо отсутствует (управляй `exclude_none`/`required`).

```python
class OrderStatus(StrEnum):                                   # R-FLD-3: enum-значения UPPER_SNAKE
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"

class OrderItemResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)  # R-FLD-1: snake_case → camelCase JSON
    item_id: UUID
    product_name: str
    quantity: int
    price: Decimal                                            # деньги — Decimal, не float

class OrderResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    order_id: UUID                                            # → "orderId" (R-FLD-5: суффикс Id)
    status: OrderStatus
    total_amount: Decimal                                     # → "totalAmount"
    created_at: datetime                                      # → "createdAt", ISO 8601 (R-FLD-2)
    items: list[OrderItemResponse] = []                       # R-RSP-7: пустая [], не null
    discount: Decimal | None = None                           # отсутствует в JSON при None (exclude_none)
    comment: str | None = None

@router.post("/orders", status_code=201, response_model=OrderResponse,
             response_model_exclude_none=True, operation_id="createOrder", tags=["Orders"],  # R-RSP-X1
             responses=get_error_responses(401, 409, 503))   # R-ERR/R-OAS: ошибки в OpenAPI
async def create_order(req: CreateOrderRequest, response: Response, ...) -> OrderResponse:
    order = await dispatcher.dispatch(CreateOrder(...))
    response.headers["Location"] = f"/api/v1/orders/{order.order_id}"   # R-RSP-3: Location при 201
    return order
```

> `discount=None`/`comment=None` **не** попадут в 2xx-ответ благодаря `exclude_none` (`R-RSP-X1`); поле либо есть,
> либо отсутствует — не `"discount": null`.

## Заголовки / ошибки / rate-limit (`R-HDR/ERR/RATE-*`)

`R-HDR-*` — стандартные заголовки; кастомные с доменным префиксом, **без `X-`**; `Idempotency-Key`; `traceparent`
(W3C). `R-ERR-*` — **problem+json (RFC 9457)**: exception-handler возвращает `Response(media_type="application/
problem+json")` (cross-ref `backend/error-handling/python` `R-ERR-MAP-*`); `code` UPPER_SNAKE из enum; валидация → `400`
`VALIDATION_ERROR` + `violations` (маппинг `RequestValidationError` FastAPI/Pydantic в этот формат, не дефолтный
422 FastAPI — переопредели handler); не светить stack/SQL в `500` (`R-ERR-X4`). `R-RATE-*` — `429` + `Retry-After`
+ `RateLimit-*` (через middleware/gateway).

Документирование ошибок в OpenAPI — единый каталог `DEFAULT_ERRORS` + хелпер `get_error_responses(*codes)`;
в декораторе перечисляются статусы, которые эндпоинт реально возвращает (`R-OAS`, cross-ref `R-ERR-MAP-*`):

```python
# app/error_responses.py — каталог problem+json и хелпер для responses=
from app.schemas.errors import ProblemDetails

DEFAULT_ERRORS: dict[int, ProblemDetails] = {
    401: ProblemDetails(type_="urn:svc:error:UNAUTHORIZED", status=401,
                        title="Не авторизован", detail="Невалидный или отсутствующий JWT", code="UNAUTHORIZED"),
    402: ProblemDetails(type_="urn:svc:error:PAYMENT_FAILED", status=402,
                        title="Ошибка оплаты", detail="Не удалось провести оплату", code="PAYMENT_FAILED"),
    409: ProblemDetails(type_="urn:svc:error:ACTIVE_ORDER_EXISTS", status=409,
                        title="Конфликт состояния", detail="У вас уже есть активный заказ", code="ACTIVE_ORDER_EXISTS"),
    503: ProblemDetails(type_="urn:svc:error:PROVIDER_UNAVAILABLE", status=503,
                        title="Сервис недоступен", detail="Внешний сервис временно недоступен", code="PROVIDER_UNAVAILABLE"),
}

def get_error_responses(*codes: int | ProblemDetails) -> dict[int | str, dict]:
    out: dict[int | str, dict] = {}
    for item in codes:
        inst = DEFAULT_ERRORS[item] if isinstance(item, int) else item   # код из каталога или готовый ProblemDetails
        out[inst.status] = {
            "model": type(inst),
            "description": inst.title,
            "content": {"application/json": {"example": inst.model_dump(by_alias=True)}},
        }
    return out

# В декораторе — только статусы, которые маршрут реально отдаёт:
@router.post("/orders/{order_id}/pay", responses=get_error_responses(401, 402, 503))
async def pay_order(order_id: UUID, ...) -> PaymentResponse: ...
```

> Внимание: дефолтный FastAPI отдаёт `422` на ошибку валидации — переопредели `RequestValidationError`-handler
> на `400` + problem+json (`R-ERR-5`, `R-ERR-X3` запрещает `422`).

```python
# Маппинг дефолтного FastAPI 422 → 400 VALIDATION_ERROR + problem+json (R-ERR-5; полный handler — в backend/validation/python)
@app.exception_handler(RequestValidationError)
async def on_validation_error(request: Request, exc: RequestValidationError) -> Response:
    violations = [                                            # R-ERR-6: все ошибки, dot-path вложенных полей
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
        for e in exc.errors()
    ]
    body = {
        "type": "urn:problem:order-service:validation-error",
        "status": 400, "title": "Bad Request",               # R-ERR-X3: НЕ 422
        "detail": "Ошибка валидации входных данных",
        "traceId": get_trace_id(),
        "code": "VALIDATION_ERROR",                           # R-ERR-4: UPPER_SNAKE
        "violations": violations,
    }
    return JSONResponse(status_code=400, content=body,
                        media_type="application/problem+json")  # R-ERR-3
```

Тело 2xx/4xx — пример `400` problem+json, который вернёт handler выше (`R-ERR-5`/`R-ERR-6`):

```json
{
  "type": "urn:problem:order-service:validation-error",
  "status": 400,
  "title": "Bad Request",
  "detail": "Ошибка валидации входных данных",
  "instance": "urn:uuid:9f2d6c22-8e6d-4c2a-9b41-6b9a5e2f6c10",
  "traceId": "00-1f2a8b6c7d3e4f5a9b0c1d2e3f4a5b6c-7a8b9c0d1e2f3a4b-01",
  "code": "VALIDATION_ERROR",
  "violations": [
    { "field": "amount", "message": "Сумма должна быть больше 0" },
    { "field": "deliveryAddress.zipCode", "message": "Почтовый индекс обязателен" },
    { "field": "items[0].quantity", "message": "Количество должно быть от 1 до 99" }
  ]
}
```

## Файлы / deprecation / batch / async / локализация (`R-FILE/DEP/BATCH/ASYNC/LOC-*`)

Протокольные — идентичны. FastAPI: `R-FILE-*` — `UploadFile` + `multipart/form-data`, скачивание —
`StreamingResponse`/`FileResponse` + `Content-Disposition`. `R-ASYNC-*` — `202` + `taskId`/`statusUrl`, опрос
`GET /api/v1/tasks/{id}`. `R-LOC-*` — `Accept-Language`, дефолт `ru`, не локализовать enum/URI (`R-LOC-X1`).

## OpenAPI-метаданные (`R-OAS-*`)

`R-OAS-1` — `operation_id` в `camelCase` на каждом маршруте (`@router.post(..., operation_id="createOrder")`) —
FastAPI иначе генерирует длинные авто-id. `R-OAS-2` — `tags=["Orders"]`, action к тегу родителя. `R-OAS-4` —
`summary`/`description` в декораторе. Контракт = Pydantic-модели (не голый `dict`, cross-ref `R-VLD-OAS-X5`).

**Contract-first pipeline (командный binding, concern `codegen` / `PYGEN-SC-*`).** Источник истины — фрагмент
`doc/openapi.yaml`:

```yaml
# doc/openapi.yaml — источник истины (PYGEN-SC-1). camelCase поля, enum UPPER_SNAKE, деньги — number/Decimal.
OrderResponse:
  type: object
  required: [orderId, status, totalAmount, createdAt, items]   # R-RSP-8: required только всегда-присутствующие
  properties:
    orderId:     { type: string, format: uuid }
    status:      { $ref: '#/components/schemas/OrderStatus' }
    totalAmount: { type: number }                              # → Decimal, не float (PYGEN-SC-X4)
    createdAt:   { type: string, format: date-time }
    items:
      type: array
      items: { $ref: '#/components/schemas/OrderItemResponse' }
    discount:    { type: number, description: 'Отсутствует если скидки нет' }  # не в required → exclude_none
OrderStatus:
  type: string
  enum: [CREATED, CONFIRMED]                                   # → StrEnum (PYGEN-SC-4)
```

Из него генерируются Pydantic v2-схемы (не пишутся руками, `PYGEN-SC-X1`):

```bash
datamodel-codegen \
  --input doc/openapi.yaml --input-file-type openapi \
  --output <pkg>/schemas/order_api.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-subclass-enum --snake-case-field --allow-population-by-field-name \  # snake поле + camelCase alias (PYGEN-SC-2/3)
  --use-annotated --use-standard-collections --use-union-operator \
  --field-constraints --target-python-version 3.12
```

Сгенерированный артефакт (соответствует разделу JSON выше; ручная база `ApiBaseModel` — `PYGEN-SC-5`):

```python
# <pkg>/schemas/order_api.py — СГЕНЕРИРОВАНО datamodel-codegen, не править руками (PYGEN-SC-X2)
class OrderStatus(StrEnum):                                    # PYGEN-SC-4 (НЕ class X(str, Enum))
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"

class OrderResponse(ApiBaseModel):                             # ApiBaseModel: populate_by_name + exclude_none
    order_id: UUID = Field(alias="orderId")                    # PYGEN-SC-3: snake поле + camelCase alias
    status: OrderStatus
    total_amount: Decimal = Field(alias="totalAmount")         # PYGEN-SC-6: Decimal, не float
    created_at: datetime = Field(alias="createdAt")
    items: list[OrderItemResponse] = []
    discount: Decimal | None = Field(default=None, alias="discount")
```

## Чеклист подключения к новому сервису (Python)

1. Contract-first: DTO генерируются из `doc/openapi.yaml` (`datamodel-codegen`, `PYGEN-SC-*`); ручные правки — только в `ApiBaseModel`, не в сгенерированном; нет дублирования правил. (Code-first — только если codegen-трек не используется.)
2. URL kebab-case без trailing-slash; `/api/v1`-префикс; методы/статусы по семантике; action = POST.
3. Query camelCase, page 1-based, массивы повтором (не CSV); сложный поиск — POST /search.
4. JSON camelCase, enum UPPER_SNAKE, нет `null` в 2xx (`exclude_none`), коллекция `content`+метаданные.
5. problem+json (RFC 9457), `400 VALIDATION_ERROR`+`violations` (переопределён 422→400), нет stack/SQL в 500.
6. Кастомные заголовки без `X-`; `Idempotency-Key`/`traceparent`; `429`+`Retry-After`.
7. `operation_id` camelCase, `tags`, `summary` на каждом маршруте.
