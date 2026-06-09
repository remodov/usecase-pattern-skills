# DDD Tactical Patterns — Python Style Guide (чистый Python в `core/`)

Реализация язык-нейтрального контракта `../ddd-tactical-rules.md` (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`)
на Python. Коды правил — общие с Java; здесь — как они выглядят в FastAPI-сервисе. Домен живёт в `core/`
**без фреймворка** (ни FastAPI, ни SQLAlchemy, ни Pydantic) — чистый Python + stdlib; enforce через `import-linter`.

В Python нет библиотеки `ddd-building-blocks` — базовые типы тонкие, ручные (ниже). Идиомы: **VO и событие —
`@dataclass(frozen=True)`** (value-equality + hashable + иммутабельность бесплатно); **Entity** — обычный класс
с identity-equality; **Aggregate Root** — Entity + список событий.

```python
# core/shared/building_blocks.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

ID = TypeVar("ID")


class Entity(Generic[ID]):
    def __init__(self, id_: ID) -> None:
        self._id = id_

    @property
    def id(self) -> ID:
        return self._id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id))


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID
    occurred_at: datetime
    aggregate_id: UUID


class AggregateRoot(Entity[ID]):
    def __init__(self, id_: ID) -> None:
        super().__init__(id_)
        self._events: list[DomainEvent] = []

    def _register_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events
```

---

## 1. Entity — `R-ENT-*`

`R-ENT-1` — сущность наследует `Entity[ID]` (или живёт внутри агрегата как обычный объект). `R-ENT-2`/`R-ENT-3` —
идентификатор задаётся в конструкторе и неизменяем (`_id` приватный, только `@property id`, без сеттера).
`R-ENT-4` — equality по id наследуется из базового `Entity`, **не переопределять** `__eq__`/`__hash__` в наследниках.
`R-ENT-5` — конструктор валидирует инварианты; невалидная сущность не должна существовать.

```python
# core/order/entity/order_line.py
class OrderLine(Entity[UUID]):
    def __init__(self, id_: UUID, product_id: ProductId, qty: int, price: Money) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        super().__init__(id_)
        self._product_id = product_id
        self._qty = qty
        self._price = price

    def subtotal(self) -> Money:
        return self._price.multiply(self._qty)
```

`R-ENT-X1` ❌ переопределять `__eq__`/`__hash__` в наследниках. `R-ENT-X2` ❌ сравнивать сущности по полям
(`dataclass`-сущность с `eq=True` по всем полям — это VO-семантика, не Entity). `R-ENT-X3` ❌ публичные сеттеры
на всё (`order.status = ...`) — состояние меняется бизнес-методами (`order.confirm()`). `R-ENT-X4` ❌ ссылка на
другой агрегат объектом — только по id (`customer_id: CustomerId`). `R-ENT-X5` ❌ анемичная модель (одни
геттеры/сеттеры, логика в сервисах).

> Не делай Entity через `@dataclass` без оглядки: дефолтный `@dataclass(eq=True)` генерирует equality по всем
> полям — это нарушает `R-ENT-X2`. Для Entity — обычный класс с identity-equality из базового `Entity`.

---

## 2. Value Object — `R-VO-*`

`R-VO-1`/`R-VO-2` — VO = `@dataclass(frozen=True)`: иммутабелен, hashable, equality по значениям (`R-VO-3`) — всё
из коробки. `R-VO-4` — инварианты в `__post_init__`. `R-VO-5` — мутирующая операция возвращает новый экземпляр
(`dataclasses.replace` / явная фабрика), не меняет текущий.

```python
# core/order/value_object/money.py
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("amount must be non-negative")
        if len(self.currency) != 3:
            raise ValueError("currency must be ISO-4217")

    def multiply(self, factor: int) -> "Money":
        return Money(self.amount * factor, self.currency)
```

`R-VO-X1` ❌ id или жизненный цикл у VO. `R-VO-X2` ❌ primitive obsession: `str email` → `Email`, `Decimal amount`
→ `Money`. `R-VO-X3` ❌ мутабельная коллекция в VO — `tuple`/`frozenset`, не `list`/`set` (иначе `frozen=True`
не спасает от мутации содержимого, а ещё VO становится unhashable).

> Деньги — **`Decimal`**, никогда `float` (cross-ref `pg-types` `PG-T-011`, `R-SQLA-MODEL-2`).

---

## 3. Aggregate Root — `R-AGG-*`

`R-AGG-1` — корень наследует `AggregateRoot[ID]`. `R-AGG-2` — внешние операции только через методы корня;
внутренние Entity наружу — копией/view (`tuple(self._lines)`). `R-AGG-3` — события регистрируются в момент
изменения состояния через `self._register_event(...)`, не в репозитории. `R-AGG-4` — один use case меняет один
агрегат; на другие влияем событиями. `R-AGG-5` — ссылки на другие агрегаты по id.

```python
# core/order/aggregate/order.py
class Order(AggregateRoot[OrderId]):
    def __init__(self, id_: OrderId, customer_id: CustomerId) -> None:
        super().__init__(id_)
        self._customer_id = customer_id
        self._status = OrderStatus.NEW
        self._lines: list[OrderLine] = []

    @property
    def lines(self) -> tuple[OrderLine, ...]:
        return tuple(self._lines)

    def confirm(self, clock: Clock) -> None:
        if not self._lines:
            raise DomainError("cannot confirm empty order")
        self._status = OrderStatus.CONFIRMED
        self._register_event(OrderConfirmed(uuid7(), clock.now(), self.id.value))
```

`R-AGG-X1` ❌ «God aggregate». `R-AGG-X2` ❌ `return self._lines` без обёртки (клиент мутирует внутреннее
состояние). `R-AGG-X3` ❌ менять чужой агрегат напрямую. `R-AGG-X4` ❌ регистрировать события вне корня
(в Handler/репозитории/контроллере).

---

## 4. Domain Event — `R-EVT-*`

`R-EVT-1` — событие наследует `DomainEvent` (несёт `event_id`/`occurred_at`/`aggregate_id`). `R-EVT-2` — имя
глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderEvent`). `R-EVT-3` — иммутабельно
(`@dataclass(frozen=True)`). `R-EVT-4` — несёт бизнес-контекст значениями (id, `amount`, `confirmed_at`), не сам
агрегат. `R-EVT-5` — публикуются после сохранения (репозиторием/UoW), затем `aggregate.pull_events()` очищает
их (cross-ref `R-TX-3`, `ucp-py-pattern-*`).

```python
# core/order/event/order_confirmed.py
@dataclass(frozen=True)
class OrderConfirmed(DomainEvent):
    customer_id: UUID
    total: Decimal
    currency: str
```

`R-EVT-X1` ❌ менять поля события после создания. `R-EVT-X2` ❌ ссылка на агрегат/Entity в событии — только
примитивы и VO. `R-EVT-X3` ❌ публиковать из контроллера/Handler — только корень регистрирует. `R-EVT-X4` ❌
доставлять критичные эффекты «after commit» фоном (теряется при падении) — Outbox в той же транзакции
(cross-ref `R-SQLA-*`, `ucp-py-sqlalchemy-*`).

---

## 5. Repository — `R-REP-*`

`R-REP-1` — порт репозитория — `Protocol` в `core/<bc>/port/`, типизирован агрегатом. `R-REP-2` — реализация в
`adapters/out/persistence/` (cross-ref `R-SQLA-REPO-1`); домен не знает про SQLAlchemy. `R-REP-3` — один
репозиторий = один корень. `R-REP-4` — `save` сохраняет агрегат целиком; публикация событий + `pull_events()` —
на границе UoW. `R-REP-5` — методы в терминах домена.

```python
# core/order/port/order_repository.py
from typing import Protocol

class OrderRepository(Protocol):
    async def by_id(self, order_id: OrderId) -> Order | None: ...
    async def save(self, order: Order) -> None: ...
    async def active_by_customer(self, customer_id: CustomerId) -> list[Order]: ...
```

`R-REP-X1` ❌ возвращать ORM-модель/`Row` наружу (cross-ref `R-SQLA-REPO-X1`). `R-REP-X2` ❌ методы под одну
таблицу (`update_status_in_db`). `R-REP-X3` ❌ Specification, генерирующая SQL, в репозитории — для чтений
отдельный ViewRepository (cross-ref `R-CQRS-4`, `R-SQLA-QRY-5`).

---

## 6. Domain Service — `R-DS-*`

`R-DS-1` — Domain Service только если логика касается ≥ 2 агрегатов и не лезет в один корень. `R-DS-2` —
stateless, принимает доменные объекты (не DTO/репозитории). `R-DS-3` — имя — доменная операция.

```python
# core/transfer/service/transfer_service.py
class TransferService:
    def transfer(self, src: Account, dst: Account, amount: Money) -> None:
        src.withdraw(amount)
        dst.deposit(amount)
```

`R-DS-X1` ❌ оркестрация (загрузка из репозитория, транзакции, публикация) в Domain Service — это Application
layer (Handler). `R-DS-X2` ❌ Domain Service как свалка, оставляющая агрегаты анемичными.

---

## 7. Factory — `R-FAC-*`

`R-FAC-1` — фабрика (модульная функция / classmethod) только когда конструктор не справляется (сборка из частей,
валидация по другому агрегату, выбор подтипа). `R-FAC-2` — возвращает уже валидный агрегат с начальными событиями.

```python
# core/order/aggregate/order.py
@classmethod
def create(cls, customer_id: CustomerId, clock: Clock, ids: IdGenerator) -> "Order":
    order = cls(OrderId(ids.next()), customer_id)
    order._register_event(OrderCreated(uuid7(), clock.now(), order.id.value))
    return order
```

`R-FAC-X1` ❌ Factory ради Factory — если хватает `Order(...)`, не плодить слой.

---

## 8. Specification — `R-SPEC-*`

`R-SPEC-1` — спецификация — класс с `is_satisfied_by(candidate) -> bool` (или предикат-callable). `R-SPEC-2` —
вводится, только когда правило применяется в ≥ 2 местах или нужна комбинация and/or/not.

```python
# core/order/specification/eligible_for_discount.py
class EligibleForDiscount:
    def __init__(self, threshold: Money) -> None:
        self._threshold = threshold

    def is_satisfied_by(self, order: Order) -> bool:
        return order.total().amount >= self._threshold.amount
```

`R-SPEC-X1` ❌ Specification для генерации SQL (это query-side). `R-SPEC-X2` ❌ Specification ради одного `if` в
одном месте — преждевременная абстракция.

---

## 9. Module (структура пакетов) — `R-MOD-*`

Группировка по домену, не по типу:

```
core/
  shared/
    building_blocks.py      # Entity, AggregateRoot, DomainEvent, ValueObject-helpers
  <bounded-context>/
    aggregate/              # AggregateRoot
    entity/                 # внутренние Entity
    value_object/           # frozen dataclass VO
    event/                  # DomainEvent
    port/                   # Protocol-порты (repository, внешние системы)
    service/                # Domain Service (опционально)
    specification/          # Specification (опционально)
    usecase/                # UseCase + Handler (command/query)
adapters/
  in/http/
  out/persistence/
app/                        # DI-композиция, dispatcher
```

`R-MOD-1` — запрещено `entity/`, `service/`, `repository/` на верхнем уровне `core/` — только по Bounded Context.
`R-MOD-2` — домен (`core/<bc>/`) не импортирует `adapters/*`, FastAPI, SQLAlchemy, Pydantic. Enforce контрактом
`import-linter` (layers: `core` < `adapters` < `app`), cross-ref `R-HEX-2`.

---

## 10. Чеклист подключения к новому сервису (Python)

1. Entity → `Entity[ID]`, id неизменяем, `__eq__`/`__hash__` не переопределены в наследнике.
2. VO → `@dataclass(frozen=True)`, инварианты в `__post_init__`, коллекции — `tuple`/`frozenset`.
3. Корни → `AggregateRoot[ID]`, события регистрируются в корне, наружу — копии/view.
4. События → наследуют `DomainEvent`, frozen, имя в прошедшем времени, только примитивы/VO.
5. Репозитории → `Protocol` в `core/<bc>/port/`, возвращают домен, реализация в `adapters/out/`.
6. Ссылки между агрегатами — по id.
7. `core/` не импортирует фреймворк (проверка `import-linter`).
8. Структура пакетов — по домену; деньги — `Decimal`.
