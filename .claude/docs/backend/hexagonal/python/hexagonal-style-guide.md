# Hexagonal Architecture — Python Style Guide (пакеты + import-linter)

Реализация язык-нейтрального контракта `../hexagonal-rules.md` (`R-HEX-*`) на Python. Коды общие с Java; меняется
**механизм изоляции**: вместо multi-module Gradle + ArchUnit — единое дерево пакетов с **layered-контрактом
`import-linter`**, проверяемым в CI. В Python нет compile-time изоляции модулей, поэтому import-linter — не
украшение, а единственный enforcement границ.

## 1. Когда переходить (`R-HEX-WHEN-*`)

`R-HEX-WHEN-1` — Hexagonal = Уровень 3 (DDD + ports/adapters + import-linter). Уровень 1–2 — overkill: плоский
`app/` без слоёв. `R-HEX-WHEN-X1` — cargo-cult (сервис из 3 эндпоинтов в полной раскладке) — ceremony.
`R-HEX-WHEN-X2` — частичный Hexagonal (есть `core/`, но роутеры мешают бизнес-логику с HTTP) — либо полностью, либо никак.

## 2. Структура (`R-HEX-MOD-*`)

Вместо gradle-модулей — пакеты с контрактом import-linter. `R-HEX-MOD-1`/`R-HEX-MOD-2` — `core/` не импортирует
ничего инфраструктурного (ни FastAPI, ни SQLAlchemy, ни Pydantic):

```
src/<service>/
  core/<bc>/{aggregate,entity,value_object,event,port,usecase,service}/
  adapters/in/http/            # FastAPI-роутеры (R-HEX-AIN)
  adapters/out/persistence/    # SQLAlchemy (R-HEX-AOUT)
  adapters/out/<system>/       # httpx-клиент к внешней системе (per-system)
  app/                         # composition root: main, container, lifespan, settings
```

```toml
# pyproject.toml — контракт зависимостей слоёв
[tool.importlinter]
root_package = "service"

[[tool.importlinter.contracts]]
name = "layers"
type = "layers"
layers = ["service.app", "service.adapters", "service.core"]
```

`R-HEX-MOD-X1` — отсутствие import-linter-контракта (полагаться на дисциплину) — кто-нибудь импортнёт SQLAlchemy в
`core/` и никто не заметит. `R-HEX-MOD-X2` — `core/` импортирует `adapters/*` — стрелка всегда `app → adapters → core`.
`R-HEX-MOD-X3` — user- и admin-роутеры в одном модуле без разделения — теряется изоляция security (отдельные пакеты
`adapters/in/http/{user,admin}/` + contract).

## 3. Core (`R-HEX-CORE-*`)

`R-HEX-CORE-1` — `core/` зависит только от stdlib + доменных типов. `R-HEX-CORE-4` — rich domain: логика в
агрегате (`order.confirm()`), не в `*Service` (cross-ref `R-AGG-2`, `ucp-py-ddd-tactical-*`).

`R-HEX-CORE-X1` — FastAPI-импорт в `core/` (enforce import-linter). `R-HEX-CORE-X2` — SQLAlchemy-импорт в `core/`
(ORM — деталь persistence; маппинг в `adapters/out/persistence/<x>_mapper.py`, cross-ref `R-SQLA-MAP-1`).
`R-HEX-CORE-X3` — анемичная модель. `R-HEX-CORE-X4` — ORM-модель как доменный тип в `core/`. `R-HEX-CORE-X5` —
Pydantic REST-DTO (`CreateOrderRequest`) в `core/` — деталь in-adapter.

```python
# core/order/aggregate/order.py — только stdlib + доменные типы (R-HEX-CORE-1).
# Никаких import fastapi / sqlalchemy / pydantic здесь (R-HEX-CORE-X1/X2/X5) — enforce import-linter.
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

class OrderStatus(StrEnum):
    NEW = "NEW"
    CONFIRMED = "CONFIRMED"

@dataclass
class Order:
    id: UUID
    customer_id: UUID
    total_amount: Decimal                                   # Decimal для денег, не float
    status: OrderStatus = OrderStatus.NEW
    confirmed_at: datetime | None = None

    # R-HEX-CORE-4: rich domain — инвариант живёт в агрегате, не в *Service (R-HEX-CORE-X3 — анемичность).
    def confirm(self) -> None:
        if self.status is not OrderStatus.NEW:
            raise OrderAlreadyConfirmedError(self.id)       # доменное исключение в core/
        self.status = OrderStatus.CONFIRMED
        self.confirmed_at = datetime.now(timezone.utc)      # aware datetime
```

## 4. Ports (`R-HEX-PORT-*`)

`R-HEX-PORT-1` — outbound-порт = `Protocol` в `core/<bc>/port/out/`, описывает что нужно core (cross-ref
`R-REP-1`, `R-HEX-3`). `R-HEX-PORT-2` — методы порта оперируют domain-типами, не DTO внешней системы.
`R-HEX-PORT-3` — port-исключения объявлены в `core/` (`PaymentPortError`); подклассы (`SberError`) — в out-adapter;
handler ловит базовый. `R-HEX-PORT-4` — inbound-порт = UseCase + Handler (вход через `Dispatcher`), отдельный
«InboundPort» не нужен.

`R-HEX-PORT-X1` — порт объявлен в out-adapter (порт — контракт core). `R-HEX-PORT-X2` — DTO внешней системы в
сигнатуре порта (адаптер мапит внутри). `R-HEX-PORT-X3` — `X | None` из порта, где отсутствие = ошибка (брось
доменное `OrderNotFoundError`). `R-HEX-PORT-X4` — порт как класс, не `Protocol`/ABC — убивает подмену в тестах.

```python
# core/order/port/out/order_repository.py — порт = Protocol в core/ (R-HEX-PORT-1/X4), не в out-adapter (R-HEX-PORT-X1).
from typing import Protocol
from uuid import UUID
from core.order.aggregate.order import Order

class OrderRepository(Protocol):                            # описывает что нужно core, не как persistence это делает
    async def get(self, order_id: UUID) -> Order: ...       # R-HEX-PORT-X3: не Order|None — отсутствие = доменная ошибка
    async def save(self, order: Order) -> None: ...         # R-HEX-PORT-2: domain-тип Order, не ORM/DTO (R-HEX-PORT-X2)

# core/order/port/out/payment_port.py — порт к внешней платёжной системе.
from core.order.value_object.charge import ChargeResult

class PaymentPort(Protocol):
    async def charge(self, order: Order) -> ChargeResult: ...   # domain-типы в сигнатуре, не Sber-DTO

# core/order/port/out/payment_errors.py — базовое port-исключение объявлено в core/ (R-HEX-PORT-3);
# подклассы (SberError) — в out-adapter; handler ловит базовый PaymentPortError.
class PaymentPortError(Exception): ...
```

## 5. Adapters in (`R-HEX-AIN-*`)

`R-HEX-AIN-1` — пакет `adapters/in/http/` на HTTP-вход (+ отдельные пакеты на другие типы входа: kafka-consumer).
`R-HEX-AIN-2`/`R-HEX-AIN-3` — роутер маппит Pydantic request-DTO → UseCase command, зовёт `Dispatcher`; отдельный
маппер (`order_request_mapper.py`), не возвращай domain-агрегат как HTTP-ответ. `R-HEX-AIN-4` — in-adapter знает
FastAPI/Pydantic, не знает про `adapters/out/*`.

`R-HEX-AIN-X1` — бизнес-логика в роутере (`if req.amount > 100`). `R-HEX-AIN-X2` — роутер зовёт репозиторий
напрямую (только через `Dispatcher` → Handler, cross-ref `R-DSP-1`). `R-HEX-AIN-X3` — роутер возвращает domain-агрегат
наружу (маппи в response-DTO). `R-HEX-AIN-X4` — `adapters/in/*` импортирует `adapters/out/*` — адаптеры зависят от
`core/`, не друг от друга.

```python
# adapters/in/http/order_dto.py — Pydantic REST-DTO живут в in-adapter (R-HEX-CORE-X5), не в core/.
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class ConfirmOrderRequest(BaseModel):
    payment_method: str

class OrderResponse(BaseModel):                             # отдельный response-DTO, не domain-агрегат (R-HEX-AIN-X3)
    model_config = ConfigDict(populate_by_name=True)        # PY-2.X2: alias + конструкция по имени поля
    id_: UUID = Field(alias="id")                           # PY-2.X2: поле без затенения builtin id
    status: str
    total_amount: Decimal

# adapters/in/http/order_mapper.py — маппер REST-DTO ↔ command/response (R-HEX-AIN-3), отдельно от роутера.
def to_command(order_id: UUID, req: ConfirmOrderRequest) -> ConfirmOrderCommand:
    return ConfirmOrderCommand(order_id=order_id, payment_method=PaymentMethod(req.payment_method))

def to_response(order: Order) -> OrderResponse:
    return OrderResponse(id_=order.id, status=order.status.value, total_amount=order.total_amount)

# adapters/in/http/order_router.py — роутер ТОЛЬКО мапит и зовёт Dispatcher (R-HEX-AIN-2).
@router.post("/orders/{order_id}/confirm", response_model=OrderResponse,
             responses=get_error_responses(404, 409, 503))
async def confirm_order(
    order_id: UUID,
    req: ConfirmOrderRequest,
    dispatcher: Dispatcher = Depends(get_dispatcher),       # R-HEX-AIN-X2: НЕ репозиторий напрямую
) -> OrderResponse:
    # R-HEX-AIN-X1: никакой бизнес-логики (if req.amount > 100) здесь — это инвариант агрегата.
    order: Order = await dispatcher.dispatch(to_command(order_id, req))
    return to_response(order)                               # маппинг наружу, не возврат domain-агрегата
# import adapters.out.* здесь запрещён (R-HEX-AIN-X4) — in-adapter знает только core/ + FastAPI/Pydantic.
```

## 6. Adapters out (`R-HEX-AOUT-*`)

`R-HEX-AOUT-1` — пакет `adapters/out/<system>/` на каждую внешнюю систему (per-system isolation, cross-ref
`R-RES-ISO-1`). `R-HEX-AOUT-2` — адаптер реализует порт-`Protocol` из `core/`. `R-HEX-AOUT-3` — маппер domain ↔ DTO
внешней системы в адаптере. `R-HEX-AOUT-4` — адаптер знает свою инфраструктуру (`persistence/` — SQLAlchemy;
`sber/` — httpx + Sber-DTO), не знает другие адаптеры.

`R-HEX-AOUT-X1` — адаптер возвращает DTO внешней системы из порт-метода (только domain). `R-HEX-AOUT-X2` —
бизнес-логика в out-adapter (`if sber_response.code == 1`); адаптер мапит, решает handler. `R-HEX-AOUT-X3` — один
адаптер реализует порты разных доменов. `R-HEX-AOUT-X4` — out-adapter инжектит другой out-adapter (координация двух —
это use case в `core/`, handler инжектит оба порта).

```python
# adapters/out/persistence/order_repository.py — реализует порт-Protocol из core/ (R-HEX-AOUT-2).
# ВЕСЬ доступ к БД (select/get/execute) — здесь, в репозитории; handler/service лишь оркестрируют.
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.order.port.out.order_repository import OrderRepository   # implements; не объявляет порт (R-HEX-PORT-X1)
from core.order.aggregate.order import Order

class SqlAlchemyOrderRepository(OrderRepository):          # duck-typing на Protocol
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, order_id: UUID) -> Order:
        model = await self._session.get(OrderModel, order_id)      # select/get — только тут (R-SQLA-REPO-1)
        if model is None:
            raise OrderNotFoundError(order_id)             # R-HEX-PORT-X3: доменная ошибка, не None
        return to_domain(model)                            # R-HEX-AOUT-1/X1: domain наружу, не ORM-модель

    async def save(self, order: Order) -> None:
        self._session.add(to_model(order))                 # mapper domain → ORM (R-HEX-AOUT-3)

# adapters/out/sber/sber_payment_adapter.py — per-system пакет (R-HEX-AOUT-1); httpx + Sber-DTO внутри.
class SberPaymentAdapter(PaymentPort):                     # реализует PaymentPort из core/
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def charge(self, order: Order) -> ChargeResult:
        dto = to_sber_request(order)                       # mapper domain → Sber-DTO (R-HEX-AOUT-3)
        try:
            resp = await self._client.post("/charge", json=dto.model_dump())
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise SberError(str(e)) from e                 # подкласс PaymentPortError — в out-adapter (R-HEX-PORT-3)
        return to_charge_result(resp.json())               # Sber-DTO → domain; решение (if code==1) — в handler (R-HEX-AOUT-X2)
# Этот адаптер НЕ инжектит OrderRepository (R-HEX-AOUT-X4) — координацию двух портов делает handler в core-usecase.
```

## 7. Composition root (`R-HEX-BOOT-*`)

`R-HEX-BOOT-1`/`R-HEX-BOOT-3` — `app/` = composition root: `create_app()` factory, `container` (DI-wiring портов на
адаптеры), `lifespan`, `settings`, `Dockerfile` (cross-ref `PYBOOT-5/8`). Зависит от `core/` + всех адаптеров; от
`app/` не зависит никто.

`R-HEX-BOOT-X1` — бизнес-логика/роутеры в `app/` (только композиция и конфиг). `R-HEX-BOOT-X2` — создание FastAPI-app
или wiring в `core/`/`adapters/*` — только в `app/`.

```python
# app/container.py — DI-контейнер: wiring портов на конкретные адаптеры (R-HEX-BOOT-1). Только здесь.
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(AppSettings)
    engine = providers.Singleton(create_async_engine, settings.provided.db.url)
    session_factory = providers.Singleton(async_sessionmaker, bind=engine, expire_on_commit=False)
    http_client = providers.Singleton(httpx.AsyncClient, base_url=settings.provided.sber.url)

    # порт core/ → конкретная реализация из adapters/out (R-HEX-AOUT-2). Подмена в тестах = override.
    order_repository = providers.Factory(SqlAlchemyOrderRepository, session=...)
    payment_port = providers.Factory(SberPaymentAdapter, client=http_client)

    # inbound: Dispatcher маппит Command → Handler; handler инжектит порты (R-HEX-PORT-4).
    dispatcher = providers.Singleton(build_dispatcher, order_repository, payment_port)

# app/main.py — composition root: create_app() factory (R-HEX-BOOT-1). Бизнес-логики нет (R-HEX-BOOT-X1).
def create_app() -> FastAPI:
    container = Container()
    app = FastAPI(lifespan=lifespan)                       # создание app — только в app/ (R-HEX-BOOT-X2)
    app.include_router(order_router)                       # роутеры из adapters/in, не определяются здесь
    app.container = container
    return app
```

```toml
# pyproject.toml — расширенный контракт (доп. к layers): independence адаптеров (R-HEX-AIN-X4/R-HEX-AOUT-4).
[[tool.importlinter.contracts]]
name = "core is pure"
type = "forbidden"
source_modules = ["service.core"]
forbidden_modules = ["fastapi", "sqlalchemy", "pydantic"]   # R-HEX-CORE-X1/X2/X5 — enforce в CI

[[tool.importlinter.contracts]]
name = "adapters independent"
type = "independence"
modules = ["service.adapters.in", "service.adapters.out"]   # адаптеры не импортируют друг друга
```

## 8. Архитектурные тесты (`R-HEX-TEST-*`)

`R-HEX-TEST-1`/`R-HEX-TEST-2` — `import-linter` (контракт layers + при необходимости forbidden/independence) запускается
в CI как required check; PR не мерджится при падении. Это аналог ArchUnit — compile-time-подобный guard на
импортах. `R-HEX-TEST-3` — единый `root_package` в контракте.

`R-HEX-TEST-X1` — только code-review для enforcement границ — человек пропустит импорт; нужен `lint-imports` в CI.

## 9. Чеклист подключения к новому сервису (Python)

1. `core/` без FastAPI/SQLAlchemy/Pydantic (контракт import-linter зелёный).
2. Стрелка зависимостей `app → adapters → core`; адаптеры не зависят друг от друга.
3. Порты — `Protocol` в `core/<bc>/port/out/`, оперируют domain-типами.
4. Роутеры через `Dispatcher`, не репозиторий напрямую; маппинг REST-DTO ↔ command/response.
5. out-adapter реализует порт, мапит domain ↔ DTO, без бизнес-логики; per-system пакеты.
6. `app/` — только композиция; `create_app()`/container/lifespan.
7. `import-linter` в CI как required check.
