# Validation — Python Style Guide (Pydantic v2 / FastAPI)

Реализация язык-нейтрального контракта `../validation-rules.md` (`R-VLD-*`) на Pydantic v2 / FastAPI.
Коды — общие с Java; здесь — Pydantic-идиомы.

> **Парадигма — contract-first (как в Java).** Источник правды валидации входа — OpenAPI-контракт
> (`doc/openapi.yaml`); из него генерируются Pydantic-схемы, и правило «не править generated руками»
> (`R-VLD-OAS-X1`) действует. *Альтернатива (code-first, без codegen):* Pydantic-модель сама источник — тогда
> актуально «модель = контракт, без дублей» (`R-VLD-OAS-X4`).

> **Командный binding — contract-first через codegen.** На UCP-сервисах input-DTO **генерируются** из
> `doc/openapi.yaml` через `datamodel-codegen` (concern `codegen`, `PYGEN-SC-1..6`): источник истины — контракт,
> constraints живут в OpenAPI (`minLength`/`maximum`/`pattern`), `datamodel-codegen --field-constraints` переносит их
> в Pydantic `Field(...)`. То есть «без дублей» (`R-VLD-OAS-X4`) обеспечивается генерацией: правило в YAML → один
> `Field` в коде. Custom/cross-field-логика, которую OpenAPI не выражает, добавляется поверх (разделы 3 и 5).

---

## 1. Где валидируем — `R-VLD-WHERE-*`

`R-VLD-WHERE-1` — входной DTO — Pydantic-модель в сигнатуре FastAPI-эндпоинта; невалидное → `RequestValidationError` → 400 problem+json (cross-ref `R-ERR-MAP-2`, `ucp-py-error-handling-*`):

```python
class CreateOrderRequest(BaseModel):
    customer_id: UUID
    items: list[OrderItemRequest] = Field(min_length=1)   # nested валидируется рекурсивно (R-VLD-WHERE-4)

@router.post("/v1/orders", responses=get_error_responses(400))   # 400 VALIDATION_ERROR + violations
async def create_order(req: CreateOrderRequest, ...): ...   # FastAPI валидирует до тела хендлера
```

Невалидный вход FastAPI собирает в `RequestValidationError`; маппим его в `400 VALIDATION_ERROR` + `violations`
(не дефолтный 422 FastAPI — `R-ERR-X3`), с dot-path вложенных полей и индексами массивов (`R-ERR-6`):

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
            parts[-1] = f"{parts[-1]}[{p}]"                     # items[0] (R-ERR-6: индексы массивов)
        else:
            parts.append(str(p))
    return ".".join(parts)                                      # deliveryAddress.zipCode (R-ERR-6: dot-path)

@app.exception_handler(RequestValidationError)
async def on_request_validation_error(request: Request, exc: RequestValidationError) -> Response:
    violations = [{"field": _field_path(e["loc"]), "message": e["msg"]} for e in exc.errors()]  # ВСЕ ошибки
    body = {
        "type": "urn:problem:order-service:validation-error",
        "status": 400, "title": "Bad Request",                 # R-ERR-X3: 400, НЕ 422
        "detail": "Ошибка валидации входных данных",
        "traceId": get_trace_id(),
        "code": "VALIDATION_ERROR",
        "violations": violations,
    }
    return JSONResponse(status_code=400, content=body, media_type="application/problem+json")  # R-ERR-3
```

`R-VLD-WHERE-2` — конфиг через `pydantic-settings BaseSettings` — валидируется по типам на старте (fail-fast).
`R-VLD-WHERE-3` — доменные инварианты — в агрегате (`Order.create(...)` бросает `DomainError`), не в Pydantic (cross-ref `R-AGG-*`).
`R-VLD-WHERE-4` — nested — вложенные Pydantic-модели (автоматически).

`R-VLD-WHERE-X1` ❌ ручная `if req.amount < 0: raise ...` в Handler — правило DTO → в модель (`Field(ge=0)`), инвариант → агрегат.
`R-VLD-WHERE-X2` ❌ повторная Pydantic-валидация UseCase-команды (она `@dataclass`, уже из чистого DTO).
`R-VLD-WHERE-X4` ❌ Pydantic-`Field`-constraints на доменном агрегате — домен не Pydantic-модель; инвариант в конструкторе.

---

## 2. Стандартные constraints — `R-VLD-STD-*`

`R-VLD-STD-1` — required vs optional через тип: `name: str` (required) vs `note: str | None = None`; пустая строка — `min_length=1`.
`R-VLD-STD-2` — размеры — `Field(min_length=, max_length=)`, числа — `Field(ge=, le=, gt=, lt=)`.
`R-VLD-STD-3` — формат — спец-типы Pydantic (`EmailStr`, `AnyUrl`, `UUID`), не самописный regex для известных форматов.
`R-VLD-STD-4` — время — `datetime`/`date` + при нужде `@field_validator` на «не в прошлом».
`R-VLD-STD-5` — валидация на правильном типе (число — `int`/`Decimal` с числовыми constraints, деньги — `Decimal`/`condecimal`, не `float`).

`R-VLD-STD-X1` ❌ `@field_validator` «не None» на non-Optional поле — тип уже гарантирует. `R-VLD-STD-X2` ❌ `Field(pattern=email-regex)` вместо `EmailStr`. `R-VLD-STD-X3` ❌ «всё-в-одном» валидатор вместо комбинации стандартных constraints.

Маппинг OpenAPI-constraint → Pydantic v2 (`datamodel-codegen --field-constraints` генерирует это автоматически):

| OpenAPI (`doc/openapi.yaml`) | Pydantic v2 `Field(...)` | Правило |
|---|---|---|
| `minLength` / `maxLength` | `Field(min_length=, max_length=)` | `R-VLD-STD-2` |
| `minimum` / `maximum` | `Field(ge=, le=)` | `R-VLD-STD-2` |
| `exclusiveMinimum` / `exclusiveMaximum` | `Field(gt=, lt=)` | `R-VLD-STD-2` |
| `minItems` / `maxItems` (array) | `Field(min_length=, max_length=)` | `R-VLD-WHERE-4` |
| `pattern` | `Field(pattern=...)` (но известный формат → спец-тип) | `R-VLD-STD-3` |
| `format: email` / `uuid` / `uri` | `EmailStr` / `UUID` / `AnyUrl` | `R-VLD-STD-3` |
| `format: date-time` | `datetime` (aware) | `R-VLD-STD-4` |
| `type: number` (деньги) | `Decimal` + `Field(max_digits=, decimal_places=)` | `R-VLD-STD-5` |
| не в `required` | `X | None = None` | `R-VLD-STD-1` |

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

`R-VLD-CC-1` — переиспользуемый constraint — `Annotated`-тип с `AfterValidator` (или reusable `field_validator`):

```python
# backend/validation/types.py
def _russian_phone(v: str) -> str:
    if not RU_PHONE.match(v): raise ValueError("неверный формат телефона")
    return v
RussianPhone = Annotated[str, AfterValidator(_russian_phone)]
```

`R-VLD-CC-2` — в общем модуле `backend/validation/types.py`, не inline в DTO. `R-VLD-CC-3` — имя по домену (`RussianPhone`, `VatNumber`), без `Valid`/`Check`. `R-VLD-CC-4` — на не-None значении; None — через optional-тип. `R-VLD-CC-5` — валидатор — чистая функция.

`R-VLD-CC-X2` ❌ валидатор inline в файле DTO. `R-VLD-CC-X3` ❌ невыносимая логика в `@model_validator` вместо переиспользуемого типа.

---

## 4. Сценарии (groups) — `R-VLD-GRP-*`

`R-VLD-GRP-1` — разные required в разных сценариях — **отдельные модели** (`CreateOrderRequest` vs `UpdateOrderRequest`) либо `@model_validator(mode="after")` по контексту; Python не имеет Java validation-groups — идиома в Python это разные типы.
`R-VLD-GRP-X1` ❌ один тип с «строгий/мягкий» режимом — два разных типа. `R-VLD-GRP-X2` ❌ модель, обслуживающая 3+ сценария — разбить.

---

## 5. Cross-field — `R-VLD-XF-*`

`R-VLD-XF-1` — правило с 2+ полями — `@model_validator(mode="after")`:

```python
class DateRangeRequest(BaseModel):
    start: date
    end: date
    @model_validator(mode="after")
    def _range(self) -> "DateRangeRequest":
        if self.end < self.start: raise ValueError("end раньше start")
        return self
```

`R-VLD-XF-2` — имя метода/правила описывает правило. `R-VLD-XF-X2` ❌ cross-field-проверка в Handler перед dispatch — место на модели.

---

## 6. Контракт-схема — `R-VLD-OAS-*`

`R-VLD-OAS-1` — **contract-first**: источник — `doc/openapi.yaml`, Pydantic-схемы генерируются (`datamodel-codegen`, `PYGEN-SC-*`); правило живёт в контракте, в одном месте. *Code-first* (без codegen): Pydantic-модель — источник, OpenAPI генерируется FastAPI (`/openapi.json`).
`R-VLD-OAS-4` — контракт = типизированная Pydantic-модель в сигнатуре эндпоинта (не `dict`/`Request.json()`).
`R-VLD-OAS-6` — после маппинга в UseCase-команду повторной валидации нет; домен-инварианты — на агрегате.

`R-VLD-OAS-X4` ❌ дублирование правила: Pydantic-constraint **и** ручной чек того же. `R-VLD-OAS-X5` ❌ inbound-DTO как голый `dict`/нетипизированный — это Pydantic-модель.

---

## 7. Конфигурация — `R-VLD-CFG-*`

`R-VLD-CFG-1` — `pydantic-settings BaseSettings` — валидируется по типам на старте:

```python
class Settings(BaseSettings):
    database_url: PostgresDsn                       # required, типобезопасно (R-VLD-CFG-2)
    http_timeout: timedelta = timedelta(seconds=5)
    payment: PaymentSettings                        # nested валидируется (R-VLD-CFG-4)
    model_config = SettingsConfigDict(env_prefix="APP_")
```

`R-VLD-CFG-X2` ❌ `os.environ["X"]` / `os.getenv` для required-конфига напрямую — без валидации; через `BaseSettings`.

---

## 8. Сообщения и i18n — `R-VLD-MSG-*`

`R-VLD-MSG-1` — текст ошибки валидатора — на русском, для UI (`raise ValueError("Сумма должна быть положительной")`).
`R-VLD-MSG-2` — интерполяция значений в текст.
`R-VLD-MSG-X1` ❌ английский в пользовательском сообщении. `R-VLD-MSG-X2` ❌ технические термины («Field amount...») вместо человекочитаемого.

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
