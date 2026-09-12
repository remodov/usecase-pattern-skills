# Use Case Pattern — реализация на Python (FastAPI)

Реализация язык-нейтрального контракта `../spec.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`) на Python/FastAPI. Коды — общие с Java; здесь — как они выглядят без библиотеки `usecase-pattern` (её роль играют лёгкие протоколы + dispatcher-реестр).

Структура UCP: `core/` (UseCase + Domain + порты-Protocol, без FastAPI/SQLAlchemy), `adapters/in/http/` (FastAPI-роутеры), `adapters/out/` (SQLAlchemy-репозитории, HTTP-клиенты), `app/` (DI-композиция, dispatcher).

---

## 1. UseCase — `R-UC-*`

`usecase-pattern/usecase-implements-marker` / `usecase-pattern/usecase-is-immutable-carrier` — UseCase = `@dataclass(frozen=True)`, immutable data carrier без логики. Маркеры команды/запроса — базовые дженерик-протоколы:

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

`usecase-pattern/one-usecase-one-operation` — имя по бизнес-операции (`CreateOrder`, `FindOrderById`), один UseCase = одна операция.
`usecase-pattern/explicit-result-type` — `R` — тип результата для контроллера (read-DTO / VO / `None`-эквивалент). Для «ничего» — отдельный тип-маркер или `OrderId`, не «голый» `None` без типа (`usecase-pattern/explicit-result-type`).

`usecase-pattern/usecase-is-immutable-carrier` ❌ логика в UseCase. `usecase-pattern/one-usecase-one-operation` ❌ один dataclass на create+update. `usecase-pattern/usecase-is-immutable-carrier` ❌ `@dataclass` без `frozen=True` / сеттеры.

---

## 2. Handler — `R-HND-*`

`usecase-pattern/one-handler-one-usecase` — Handler реализует протокол `Handler[UC, R]` с `async def handle(uc) -> R`:

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

Полный handler с зависимостями через `__init__` и границей TX через `session.begin()`. Доступ к БД — **только через
репозиторий** (никакого SQLAlchemy в хендлере); handler оркеструет load → доменный метод → save → outbox в одной
TX. Зависимости — порты-`Protocol`, реализация инжектится DI-контейнером:

```python
# core/order/handlers.py
class CreateOrderHandler:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession],   # R-HND-5: deps через __init__
                 orders: OrderRepository, outbox: OutboxRepository,         # порты из core/<bc>/port/
                 clock: Clock) -> None:
        self._session_factory = session_factory
        self._orders = orders
        self._outbox = outbox
        self._clock = clock

    async def handle(self, uc: CreateOrder) -> OrderId:          # R-HND-1: единственный метод handle
        structlog.contextvars.bind_contextvars(use_case="CreateOrder")     # R-SQLA-SESS-4: ошибка+шаг в edge-лог
        async with self._session_factory() as session, session.begin():    # R-TX-1: граница TX на handler
            order = Order.create(uc.customer_id, uc.items, self._clock.now())   # доменная фабрика
            await self._orders.add(session, order)                          # запись — через репозиторий
            for event in order.pull_events():                               # R-TX-3: события после save
                self._outbox.add(session, event)                           # outbox в той же TX
            return order.id                                                 # R-CQRS-X1: минимум (id), не read-DTO
```

`usecase-pattern/handler-registered-in-container` — Handler регистрируется в DI-контейнере (dependency-injector / punq), чтобы dispatcher нашёл его (см. §3). `usecase-pattern/one-handler-one-usecase` — один Handler — один UseCase. `usecase-pattern/handler-is-stateless` — зависимости через `__init__`, поля приватные неизменяемые.

`usecase-pattern/handlers-do-not-call-handlers` ❌ Handler зовёт другой Handler напрямую — через dispatcher / Step. `usecase-pattern/infrastructure-errors-become-domain` ❌ наружу летит `sqlalchemy.exc.*` / `httpx`-ошибка — мапить в доменную (cross-ref `R-ERR-WHERE-2b`, `ucp-py-error-handling-*`). `usecase-pattern/handler-is-stateless` ❌ изменяемое состояние между вызовами — Handler stateless (контейнер может отдавать per-request, но без накопления state).

---

## 3. Dispatcher и контроллер — `R-DSP-*`

`usecase-pattern/entry-calls-dispatcher` / `usecase-pattern/single-dispatcher` — контроллер не зовёт Handler напрямую, только через `Dispatcher`. Лёгкий реестр type→handler:

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

Регистрация handler'ов в DI-контейнере (`dependency-injector`/`punq`) и построение `Dispatcher` из реестра
`type[UseCase] → Handler` (`usecase-pattern/handler-registered-in-container`). Контейнер инжектит порты в handler'ы; FastAPI получает dispatcher через
`Depends`:

```python
# app/container.py — DI-композиция: провайдеры + реестр UseCase→Handler (R-HND-2)
class Container(containers.DeclarativeContainer):
    session_factory = providers.Singleton(build_session_factory, dsn=settings.db.dsn)
    clock = providers.Singleton(SystemClock)
    orders = providers.Factory(SqlAlchemyOrderRepository)         # реализация порта из adapters/out
    outbox = providers.Factory(SqlAlchemyOutboxRepository)
    views = providers.Factory(SqlAlchemyOrderViewRepository)

    create_order_handler = providers.Factory(
        CreateOrderHandler, session_factory=session_factory, orders=orders,
        outbox=outbox, clock=clock)
    find_order_handler = providers.Factory(
        FindOrderByIdHandler, session_factory=session_factory, views=views)

    dispatcher = providers.Singleton(
        Dispatcher,
        registry=providers.Dict({                                # реестр type→handler (R-DSP-1)
            CreateOrder: create_order_handler,
            FindOrderById: find_order_handler,
        }))

# app/deps.py — FastAPI-зависимость отдаёт собранный dispatcher
def get_dispatcher() -> Dispatcher:
    return container.dispatcher()
```

`usecase-pattern/controller-maps-and-dispatches` — endpoint делает только маппинг Request→UseCase, dispatch, маппинг Result→Response, HTTP-код:

```python
# adapters/in/http/order_router.py
@router.post("/v1/orders", status_code=201, responses=get_error_responses(401, 409))
async def create_order(req: CreateOrderRequest, dispatcher: Dispatcher = Depends(get_dispatcher),
                       principal: Principal = Depends(get_principal)) -> CreateOrderResponse:
    order_id = await dispatcher.dispatch(
        CreateOrder(customer_id=principal.user_id, items=req.to_domain_items()))   # R-DSP-X2: userId из principal, не Request
    return CreateOrderResponse(id_=str(order_id))           # PY-2.X2: поле без затенения builtin id
```

`usecase-pattern/controller-maps-and-dispatches` ❌ бизнес-логика/обращение к БД в endpoint. `usecase-pattern/no-transport-objects-in-usecase` ❌ передавать `Request`/`Principal` в UseCase — извлекать `user_id`/`tenant_id` в контроллере.

---

## 4. CQRS — `R-CQRS-*`

`usecase-pattern/command-versus-query`/`-3` — команда реализует `Command[R]` (имя-глагол `CreateOrder`), запрос — `Query[R]` (`FindOrderById`/`SearchOrders`).
`usecase-pattern/transaction-boundary-on-handler` — команда: `async with uow` (read-write); запрос: read-only сессия (`session.begin()` не нужен, или `AsyncSession` без commit), через ViewRepository.
`usecase-pattern/reads-via-read-model` — чтения возвращают read-DTO/view (`OrderView`), запись — через `OrderRepository` с агрегатом.

`usecase-pattern/command-returns-minimum` ❌ команда возвращает тяжёлый read-DTO со связями — только id/summary. `usecase-pattern/query-does-not-mutate` ❌ запрос пишет (last-seen/counter) — это команда.

---

## 5. Слои моделей — `R-LAY-*`

`usecase-pattern/layer-models-do-not-leak` — на входе UseCase — поля из Pydantic-DTO (или явные VO), не SQLAlchemy-модель. `usecase-pattern/layer-models-do-not-leak` — на выходе — read-DTO/VO, не SQLAlchemy-модель.
`usecase-pattern/explicit-mapper-between-layers` — маппинг — явными функциями/методами (`CreateOrderRequest.to_domain_items()`, `OrderView.model_validate(row)`); не один класс на все слои.

`usecase-pattern/layer-models-do-not-leak` ❌ один класс для API и БД (SQLAlchemy-модель уходит в JSON-ответ). `usecase-pattern/explicit-mapper-between-layers` ❌ «универсальный» маппинг через `dict(**vars(obj))` / `__dict__`-копирование. `usecase-pattern/layer-models-do-not-leak` — доменные объекты (Aggregate/Entity/VO из `core/`) не утекают в API-слой (cross-ref `ucp-py-ddd-tactical-*`).

---

## 6. Hexagonal (Уровень 3) — `R-HEX-*`

`hexagonal/module-per-part` — `core/<bc>/` (usecases + domain + `port/`), `adapters/in/http`, `adapters/out/{persistence,payment}`.
`hexagonal/core-free-of-framework` — `core/` импортирует только stdlib + доменные типы; **не** FastAPI/SQLAlchemy/httpx. (ArchUnit-аналог: тест на импорты, напр. `import-linter` с контрактом layers.)
`hexagonal/outbound-port-interface-in-core` — внешнее — за портами-`Protocol` в `core/<bc>/port/`; реализация в `adapters/out/`:

```python
# core/order/port/order_repository.py
class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...
    async def get(self, id: OrderId) -> Order | None: ...
```

`usecase-pattern/one-usecase-many-inbound-adapters` — один UseCase из нескольких входных адаптеров (HTTP-роутер, Kafka-consumer, scheduler) — Handler не дублировать.

`hexagonal/outbound-port-interface-in-core` ❌ `AsyncSession`/SQL в `core/`. `hexagonal/core-free-of-framework` ❌ `from fastapi import ...` / `import sqlalchemy` в `core/`. Enforce — `import-linter`.

---

## 7. Step — `R-STEP-*`

`usecase-pattern/step-for-reuse-only` — Step — класс/коллабл с `async def execute(i: I) -> O`, stateless `@`-инъектируемый. `usecase-pattern/step-for-reuse-only` — вводить, когда логика в ≥ 2 Handler-ах.
`usecase-pattern/steps-flat-and-stateless` ❌ Step внутри Step. `usecase-pattern/steps-flat-and-stateless` ❌ Step с состоянием.

---

## 8. Транзакции и события — `R-TX-*`

`usecase-pattern/transaction-boundary-on-handler` — граница транзакции — на Handler через Unit of Work (`async with self._uow: ... await uow.commit()`), не на репозитории. UoW оборачивает `AsyncSession`:

```python
# adapters/out/persistence/uow.py
class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None: ...
    async def __aenter__(self): self._session = self._session_factory(); return self
    async def __aexit__(self, *exc): await self._session.rollback(); await self._session.close()
    async def commit(self): await self._session.commit()
```

`usecase-pattern/one-usecase-one-transaction` — один UseCase = одна транзакция; Saga — оркестратор в Handler, шаги — отдельные UseCase / внешние вызовы с Outbox (cross-ref `ucp-py-distributed-*`).
`usecase-pattern/publish-events-after-save` — доменные события (Уровень 3) — после `repository.add/save`, затем `aggregate.clear_events()` (cross-ref `ucp-py-ddd-tactical-*`).

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
