# Validation — реализация на Python (Pydantic v2 / FastAPI)

Реализация язык-нейтрального контракта `../spec.md` (`R-VLD-*`) на Pydantic v2 / FastAPI.
Коды — общие с Java; здесь — Pydantic-идиомы.

> **Парадигма — contract-first (как в Java).** Источник правды валидации входа — OpenAPI-контракт
> (`doc/openapi.yaml`); из него генерируются Pydantic-схемы, и правило «не править generated руками»
> (`validation/generated-artifacts-immutable`) действует. *Альтернатива (code-first, без codegen):* Pydantic-модель сама источник — тогда
> актуально «модель = контракт, без дублей» (`validation/single-source-of-truth`).

> **Командный binding — contract-first через codegen.** На UCP-сервисах input-DTO **генерируются** из
> `doc/openapi.yaml` через `datamodel-codegen` (concern `codegen`, `PYGEN-SC-1..6`): источник истины — контракт,
> constraints живут в OpenAPI (`minLength`/`maximum`/`pattern`), `datamodel-codegen --field-constraints` переносит их
> в Pydantic `Field(...)`. То есть «без дублей» (`validation/single-source-of-truth`) обеспечивается генерацией: правило в YAML → один
> `Field` в коде. Custom/cross-field-логика, которую OpenAPI не выражает, добавляется поверх (разделы 3 и 5).

---

## 1. Где валидируем — `R-VLD-WHERE-*`

`validation/input-validated-at-edge` — входной DTO — Pydantic-модель в сигнатуре FastAPI-эндпоинта; невалидное → `RequestValidationError` → 400 problem+json (cross-ref `error-handling/domain-and-validation-mapping`, `ucp-py-error-handling-*`):

```python
class CreateOrderRequest(BaseModel):
    customer_id: UUID
    items: list[OrderItemRequest] = Field(min_length=1)   # nested валидируется рекурсивно (R-VLD-WHERE-4)

@router.post("/v1/orders", responses=get_error_responses(400))   # 400 VALIDATION_ERROR + violations
async def create_order(req: CreateOrderRequest, ...): ...   # FastAPI валидирует до тела хендлера
```

Невалидный вход FastAPI собирает в `RequestValidationError`; маппим его в `400 VALIDATION_ERROR` + `violations`
(не дефолтный 422 FastAPI — `rest-api/error-status-codes-limited`), с dot-path вложенных полей и индексами массивов (`rest-api/validation-errors-list-violations`):

```python
# app/error_handlers.py — единый handler для входной валидации (cross-ref R-ERR-MAP-2, backend/error-handling/python)
from fastapi.exceptions import RequestValidationError

def _field_path(loc: tuple) -> str:
    # loc вида ("body", "deliveryAddress", "zipCode") / ("body", "items", 0, "quantity")
    parts: list[str] = []
    for p in loc:
        if p in ("body", "query", "path"):
            continue                                            # служебный префикс не показываем
        if isinstance(p, int):
            parts[-1] = f"{parts[-1]}[{p}]"                     # items[0] (rest-api/validation-errors-list-violations: индексы массивов)
        else:
            parts.append(str(p))
    return ".".join(parts)                                      # deliveryAddress.zipCode (rest-api/validation-errors-list-violations: dot-path)

@app.exception_handler(RequestValidationError)
async def on_request_validation_error(request: Request, exc: RequestValidationError) -> Response:
    violations = [{"field": _field_path(e["loc"]), "message": e["msg"]} for e in exc.errors()]  # ВСЕ ошибки
    body = {
        "type": "urn:problem:order-service:validation-error",
        "status": 400, "title": "Bad Request",                 # rest-api/error-status-codes-limited: 400, НЕ 422
        "detail": "Ошибка валидации входных данных",
        "traceId": get_trace_id(),
        "code": "VALIDATION_ERROR",
        "violations": violations,
    }
    return JSONResponse(status_code=400, content=body, media_type="application/problem+json")  # rest-api/error-body-follows-standard
```

`validation/config-validated-at-startup` — конфиг через `pydantic-settings BaseSettings` — валидируется по типам на старте (fail-fast).
`validation/domain-invariants-in-aggregate` — доменные инварианты — в агрегате (`Order.create(...)` бросает `DomainError`), не в Pydantic (cross-ref `R-AGG-*`).
`validation/nested-validated-recursively` — nested — вложенные Pydantic-модели (автоматически).

`validation/input-validated-at-edge` ❌ ручная `if req.amount < 0: raise ...` в Handler — правило DTO → в модель (`Field(ge=0)`), инвариант → агрегат.
`validation/no-revalidation-after-edge` ❌ повторная Pydantic-валидация UseCase-команды (она `@dataclass`, уже из чистого DTO).
`validation/domain-invariants-in-aggregate` ❌ Pydantic-`Field`-constraints на доменном агрегате — домен не Pydantic-модель; инвариант в конструкторе.

---

## 2. Стандартные constraints — `R-VLD-STD-*`

`validation/standard-constraints-preferred` — required vs optional через тип: `name: str` (required) vs `note: str | None = None`; пустая строка — `min_length=1`.
`validation/standard-constraints-preferred` — размеры — `Field(min_length=, max_length=)`, числа — `Field(ge=, le=, gt=, lt=)`.
`validation/standard-constraints-preferred` — формат — спец-типы Pydantic (`EmailStr`, `AnyUrl`, `UUID`), не самописный regex для известных форматов.
`validation/standard-constraints-preferred` — время — `datetime`/`date` + при нужде `@field_validator` на «не в прошлом».
`validation/standard-constraints-preferred` — валидация на правильном типе (число — `int`/`Decimal` с числовыми constraints, деньги — `Decimal`/`condecimal`, не `float`).

`validation/no-false-or-composite-constraints` ❌ `@field_validator` «не None» на non-Optional поле — тип уже гарантирует. `validation/standard-constraints-preferred` ❌ `Field(pattern=email-regex)` вместо `EmailStr`. `validation/no-false-or-composite-constraints` ❌ «всё-в-одном» валидатор вместо комбинации стандартных constraints.

Маппинг OpenAPI-constraint → Pydantic v2 (`datamodel-codegen --field-constraints` генерирует это автоматически):

| OpenAPI (`doc/openapi.yaml`) | Pydantic v2 `Field(...)` | Правило |
|---|---|---|
| `minLength` / `maxLength` | `Field(min_length=, max_length=)` | `validation/standard-constraints-preferred` |
| `minimum` / `maximum` | `Field(ge=, le=)` | `validation/standard-constraints-preferred` |
| `exclusiveMinimum` / `exclusiveMaximum` | `Field(gt=, lt=)` | `validation/standard-constraints-preferred` |
| `minItems` / `maxItems` (array) | `Field(min_length=, max_length=)` | `validation/nested-validated-recursively` |
| `pattern` | `Field(pattern=...)` (но известный формат → спец-тип) | `validation/standard-constraints-preferred` |
| `format: email` / `uuid` / `uri` | `EmailStr` / `UUID` / `AnyUrl` | `validation/standard-constraints-preferred` |
| `format: date-time` | `datetime` (aware) | `validation/standard-constraints-preferred` |
| `type: number` (деньги) | `Decimal` + `Field(max_digits=, decimal_places=)` | `validation/standard-constraints-preferred` |
| не в `required` | `X | None = None` | `validation/standard-constraints-preferred` |

```python
class CreateOrderRequest(BaseModel):
    customer_id: UUID                                            # format: uuid → UUID (R-VLD-STD-3)
    email: EmailStr                                              # format: email → EmailStr, не regex (R-VLD-STD-X2)
    comment: str | None = Field(default=None, max_length=500)    # maxLength=500, optional (R-VLD-STD-1)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)  # exclusiveMinimum + деньги Decimal (R-VLD-STD-5)
    items: list[OrderItemRequest] = Field(min_length=1)          # minItems=1 (R-VLD-WHERE-4)
```

---

## 3. Custom constraints — `R-VLD-CC-*`

`validation/custom-constraint-is-reusable` — переиспользуемый constraint — `Annotated`-тип с `AfterValidator` (или reusable `field_validator`):

```python
# backend/validation/types.py
def _russian_phone(v: str) -> str:
    if not RU_PHONE.match(v): raise ValueError("неверный формат телефона")
    return v
RussianPhone = Annotated[str, AfterValidator(_russian_phone)]
```

`validation/custom-constraint-is-reusable` — в общем модуле `backend/validation/types.py`, не inline в DTO. `validation/custom-constraint-named-by-domain` — имя по домену (`RussianPhone`, `VatNumber`), без `Valid`/`Check`. `validation/custom-constraint-null-safe` — на не-None значении; None — через optional-тип. `validation/constraint-is-stateless` — валидатор — чистая функция.

`validation/custom-constraint-is-reusable` ❌ валидатор inline в файле DTO. `validation/custom-constraint-is-reusable` ❌ невыносимая логика в `@model_validator` вместо переиспользуемого типа.

---

## 4. Сценарии (groups) — `R-VLD-GRP-*`

`validation/scenario-groups-are-narrow` — разные required в разных сценариях — **отдельные модели** (`CreateOrderRequest` vs `UpdateOrderRequest`) либо `@model_validator(mode="after")` по контексту; Python не имеет Java validation-groups — идиома в Python это разные типы.
`validation/scenario-groups-are-narrow` ❌ один тип с «строгий/мягкий» режимом — два разных типа. `validation/scenario-groups-are-narrow` ❌ модель, обслуживающая 3+ сценария — разбить.

---

## 5. Cross-field — `R-VLD-XF-*`

`validation/cross-field-rules-on-object` — правило с 2+ полями — `@model_validator(mode="after")`:

```python
class DateRangeRequest(BaseModel):
    start: date
    end: date
    @model_validator(mode="after")
    def _range(self) -> "DateRangeRequest":
        if self.end < self.start: raise ValueError("end раньше start")
        return self
```

`validation/cross-field-rules-on-object` — имя метода/правила описывает правило. `validation/cross-field-rules-on-object` ❌ cross-field-проверка в Handler перед dispatch — место на модели.

---

## 6. Контракт-схема — `R-VLD-OAS-*`

`validation/single-source-of-truth` — **contract-first**: источник — `doc/openapi.yaml`, Pydantic-схемы генерируются (`datamodel-codegen`, `PYGEN-SC-*`); правило живёт в контракте, в одном месте. *Code-first* (без codegen): Pydantic-модель — источник, OpenAPI генерируется FastAPI (`/openapi.json`).
`validation/controller-implements-generated-contract` — контракт = типизированная Pydantic-модель в сигнатуре эндпоинта (не `dict`/`Request.json()`).
`validation/no-revalidation-after-edge` — после маппинга в UseCase-команду повторной валидации нет; домен-инварианты — на агрегате.

`validation/single-source-of-truth` ❌ дублирование правила: Pydantic-constraint **и** ручной чек того же. `validation/controller-implements-generated-contract` ❌ inbound-DTO как голый `dict`/нетипизированный — это Pydantic-модель.

---

## 7. Конфигурация — `R-VLD-CFG-*`

`validation/config-validated-at-startup` — `pydantic-settings BaseSettings` — валидируется по типам на старте:

```python
class Settings(BaseSettings):
    database_url: PostgresDsn                       # required, типобезопасно (R-VLD-CFG-2)
    http_timeout: timedelta = timedelta(seconds=5)
    payment: PaymentSettings                        # nested валидируется (R-VLD-CFG-4)
    model_config = SettingsConfigDict(env_prefix="APP_")
```

`validation/config-validated-at-startup` ❌ `os.environ["X"]` / `os.getenv` для required-конфига напрямую — без валидации; через `BaseSettings`.

---

## 8. Сообщения и i18n — `R-VLD-MSG-*`

`validation/message-in-user-language` — текст ошибки валидатора — на русском, для UI (`raise ValueError("Сумма должна быть положительной")`).
`validation/message-in-user-language` — интерполяция значений в текст.
`validation/message-in-user-language` ❌ английский в пользовательском сообщении. `validation/message-in-user-language` ❌ технические термины («Field amount...») вместо человекочитаемого.

---

## Чеклист подключения (Python/Pydantic)

- [ ] Входные DTO — Pydantic-модели в сигнатурах эндпоинтов; nested — вложенные модели
- [ ] `RequestValidationError` → 400 problem+json (через `ucp-py-error-handling`)
- [ ] Конфиг — `pydantic-settings BaseSettings`, required без default, nested валидируется
- [ ] Стандартные constraints через `Field(...)`/спец-типы (`EmailStr`/`UUID`); деньги — `Decimal`, не `float`
- [ ] Custom — `Annotated[T, AfterValidator(...)]` в `backend/validation/types.py`, имя по домену, на не-None
- [ ] Cross-field — `@model_validator(mode="after")` с говорящим именем
- [ ] Нет ручной input-валидации в Handler; нет дублей правил; нет `os.environ` для required
- [ ] Доменные инварианты — в агрегате (не Pydantic); сообщения — на русском
