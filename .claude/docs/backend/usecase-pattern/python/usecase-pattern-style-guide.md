# Use Case Pattern — Python Style Guide (FastAPI)

Реализация язык-нейтрального контракта `../usecase-pattern-rules.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`) на Python/FastAPI. Коды — общие с Java; здесь — как они выглядят без библиотеки `usecase-pattern` (её роль играют лёгкие протоколы + dispatcher-реестр).

Структура UCP: `core/` (UseCase + Domain + порты-Protocol, без FastAPI/SQLAlchemy), `adapters/in/http/` (FastAPI-роутеры), `adapters/out/` (SQLAlchemy-репозитории, HTTP-клиенты), `app/` (DI-композиция, dispatcher).

---

## 1. UseCase — `R-UC-*`

`R-UC-1` / `R-UC-2` — UseCase = `@dataclass(frozen=True)`, immutable data carrier без логики. Маркеры команды/запроса — базовые дженерик-протоколы:

```python
# core/usecase.py
from typing import Protocol, TypeVar
R = TypeVar("R", covariant=True)

class Command(Protocol[R]): ...      # меняет состояние
class Query(Protocol[R]): ...        # только читает

# core/order/usecases.py
@dataclass(frozen=True)
class CreateOrder:                    # Command[OrderId]
    customer_id: str
    items: tuple[OrderItemInput, ...]
```

`R-UC-3` — имя по бизнес-операции (`CreateOrder`, `FindOrderById`), один UseCase = одна операция.
`R-UC-4` — `R` — тип результата для контроллера (read-DTO / VO / `None`-эквивалент). Для «ничего» — отдельный тип-маркер или `OrderId`, не «голый» `None` без типа (`R-UC-X4`).

`R-UC-X1` ❌ логика в UseCase. `R-UC-X2` ❌ один dataclass на create+update. `R-UC-X3` ❌ `@dataclass` без `frozen=True` / сеттеры.

---

## 2. Handler — `R-HND-*`

`R-HND-1` — Handler реализует протокол `Handler[UC, R]` с `async def handle(uc) -> R`:

```python
# core/usecase.py
UC = TypeVar("UC")
class Handler(Protocol[UC, R]):
    async def handle(self, use_case: UC) -> R: ...

# core/order/handlers.py
class CreateOrderHandler:
    def __init__(self, orders: OrderRepository, uow: UnitOfWork, clock: Clock) -> None:  # R-HND-5
        self._orders = orders
        self._uow = uow
        self._clock = clock

    async def handle(self, uc: CreateOrder) -> OrderId:       # R-HND-3 граница транзакции — здесь
        async with self._uow:                                  # read-write для команды
            order = Order.create(uc.customer_id, uc.items, self._clock.now())
            await self._orders.add(order)
            await self._uow.commit()
            return order.id
```

`R-HND-2` — Handler регистрируется в DI-контейнере (dependency-injector / punq), чтобы dispatcher нашёл его (см. §3). `R-HND-4` — один Handler — один UseCase. `R-HND-5` — зависимости через `__init__`, поля приватные неизменяемые.

`R-HND-X1` ❌ Handler зовёт другой Handler напрямую — через dispatcher / Step. `R-HND-X2` ❌ наружу летит `sqlalchemy.exc.*` / `httpx`-ошибка — мапить в доменную (cross-ref `R-ERR-WHERE-2b`, `ucp-py-error-handling-*`). `R-HND-X3` ❌ изменяемое состояние между вызовами — Handler stateless (контейнер может отдавать per-request, но без накопления state).

---

## 3. Dispatcher и контроллер — `R-DSP-*`

`R-DSP-1` / `R-DSP-2` — контроллер не зовёт Handler напрямую, только через `Dispatcher`. Лёгкий реестр type→handler:

```python
# app/dispatcher.py
class Dispatcher:
    def __init__(self, registry: dict[type, Handler]) -> None:
        self._registry = registry

    async def dispatch(self, use_case: object) -> object:
        handler = self._registry.get(type(use_case))
        if handler is None:
            raise TechnicalError(f"no handler for {type(use_case).__name__}")
        return await handler.handle(use_case)
```

Реестр собирается в DI-композиции (`app/`), один dispatcher на приложение; второй — только при физическом разделении пулов команд/запросов.

`R-DSP-3` — endpoint делает только маппинг Request→UseCase, dispatch, маппинг Result→Response, HTTP-код:

```python
# adapters/in/http/order_router.py
@router.post("/v1/orders", status_code=201)
async def create_order(req: CreateOrderRequest, dispatcher: Dispatcher = Depends(get_dispatcher),
                       principal: Principal = Depends(get_principal)) -> CreateOrderResponse:
    order_id = await dispatcher.dispatch(
        CreateOrder(customer_id=principal.user_id, items=req.to_domain_items()))   # R-DSP-X2: userId из principal, не Request
    return CreateOrderResponse(id=str(order_id))
```

`R-DSP-X1` ❌ бизнес-логика/обращение к БД в endpoint. `R-DSP-X2` ❌ передавать `Request`/`Principal` в UseCase — извлекать `user_id`/`tenant_id` в контроллере.

---

## 4. CQRS — `R-CQRS-*`

`R-CQRS-1`/`-3` — команда реализует `Command[R]` (имя-глагол `CreateOrder`), запрос — `Query[R]` (`FindOrderById`/`SearchOrders`).
`R-CQRS-2` — команда: `async with uow` (read-write); запрос: read-only сессия (`session.begin()` не нужен, или `AsyncSession` без commit), через ViewRepository.
`R-CQRS-4` — чтения возвращают read-DTO/view (`OrderView`), запись — через `OrderRepository` с агрегатом.

`R-CQRS-X1` ❌ команда возвращает тяжёлый read-DTO со связями — только id/summary. `R-CQRS-X2` ❌ запрос пишет (last-seen/counter) — это команда.

---

## 5. Слои моделей — `R-LAY-*`

`R-LAY-1` — на входе UseCase — поля из Pydantic-DTO (или явные VO), не SQLAlchemy-модель. `R-LAY-2` — на выходе — read-DTO/VO, не SQLAlchemy-модель.
`R-LAY-3` — маппинг — явными функциями/методами (`CreateOrderRequest.to_domain_items()`, `OrderView.model_validate(row)`); не один класс на все слои.

`R-LAY-X1` ❌ один класс для API и БД (SQLAlchemy-модель уходит в JSON-ответ). `R-LAY-X3` ❌ «универсальный» маппинг через `dict(**vars(obj))` / `__dict__`-копирование. `R-LAY-DDD` — доменные объекты (Aggregate/Entity/VO из `core/`) не утекают в API-слой (cross-ref `ucp-py-ddd-tactical-*`).

---

## 6. Hexagonal (Уровень 3) — `R-HEX-*`

`R-HEX-1` — `core/<bc>/` (usecases + domain + `port/`), `adapters/in/http`, `adapters/out/{persistence,payment}`.
`R-HEX-2` — `core/` импортирует только stdlib + доменные типы; **не** FastAPI/SQLAlchemy/httpx. (ArchUnit-аналог: тест на импорты, напр. `import-linter` с контрактом layers.)
`R-HEX-3` — внешнее — за портами-`Protocol` в `core/<bc>/port/`; реализация в `adapters/out/`:

```python
# core/order/port/order_repository.py
class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...
    async def get(self, id: OrderId) -> Order | None: ...
```

`R-HEX-4` — один UseCase из нескольких входных адаптеров (HTTP-роутер, Kafka-consumer, scheduler) — Handler не дублировать.

`R-HEX-X1` ❌ `AsyncSession`/SQL в `core/`. `R-HEX-X2` ❌ `from fastapi import ...` / `import sqlalchemy` в `core/`. Enforce — `import-linter`.

---

## 7. Step — `R-STEP-*`

`R-STEP-1` — Step — класс/коллабл с `async def execute(i: I) -> O`, stateless `@`-инъектируемый. `R-STEP-2` — вводить, когда логика в ≥ 2 Handler-ах.
`R-STEP-X1` ❌ Step внутри Step. `R-STEP-X2` ❌ Step с состоянием.

---

## 8. Транзакции и события — `R-TX-*`

`R-TX-1` — граница транзакции — на Handler через Unit of Work (`async with self._uow: ... await uow.commit()`), не на репозитории. UoW оборачивает `AsyncSession`:

```python
# adapters/out/persistence/uow.py
class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None: ...
    async def __aenter__(self): self._session = self._session_factory(); return self
    async def __aexit__(self, *exc): await self._session.rollback(); await self._session.close()
    async def commit(self): await self._session.commit()
```

`R-TX-2` — один UseCase = одна транзакция; Saga — оркестратор в Handler, шаги — отдельные UseCase / внешние вызовы с Outbox (cross-ref `ucp-py-distributed-*`).
`R-TX-3` — доменные события (Уровень 3) — после `repository.add/save`, затем `aggregate.clear_events()` (cross-ref `ucp-py-ddd-tactical-*`).

---

## Чеклист подключения к новому сервису (Python/FastAPI)

- [ ] `core/usecase.py`: протоколы `Command`/`Query`/`Handler`
- [ ] UseCase — `@dataclass(frozen=True)`, имя-операция, без логики
- [ ] Handler — класс с `async def handle`, deps через `__init__`, граница TX через UoW
- [ ] `Dispatcher` (реестр type→handler), контроллер зовёт только его
- [ ] Endpoint тонкий: Pydantic-Request → UseCase → dispatch → Pydantic-Response; `user_id` из principal, не из Request
- [ ] Pydantic-DTO на edge, домен в `core/`, SQLAlchemy-модели в persistence; явный маппинг
- [ ] Порты — `Protocol` в `core/<bc>/port/`; `core/` без FastAPI/SQLAlchemy (enforce `import-linter`)
- [ ] CQRS: команда read-write UoW + id/summary; запрос read-only + ViewRepository + read-DTO
- [ ] Инфра-ошибки (SQLAlchemy/httpx) мапятся в доменные в адаптере (cross-ref `ucp-py-error-handling-*`)
- [ ] DI-контейнер (dependency-injector/punq) собирает handlers + dispatcher
```
