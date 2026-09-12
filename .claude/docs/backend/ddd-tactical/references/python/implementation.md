# DDD Tactical Patterns — реализация на Python (чистый Python в `core/`)

Реализация язык-нейтрального контракта `../spec.md` (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`)
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

`ddd-tactical/entity-equality-by-identity` — сущность наследует `Entity[ID]` (или живёт внутри агрегата как обычный объект). `ddd-tactical/identity-is-immutable`/`ddd-tactical/identity-is-immutable` —
идентификатор задаётся в конструкторе и неизменяем (`_id` приватный, только `@property id`, без сеттера).
`ddd-tactical/entity-equality-by-identity` — equality по id наследуется из базового `Entity`, **не переопределять** `__eq__`/`__hash__` в наследниках.
`ddd-tactical/entity-constructor-validates` — конструктор валидирует инварианты; невалидная сущность не должна существовать.

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

`ddd-tactical/entity-equality-by-identity` ❌ переопределять `__eq__`/`__hash__` в наследниках. `ddd-tactical/entity-equality-by-identity` ❌ сравнивать сущности по полям
(`dataclass`-сущность с `eq=True` по всем полям — это VO-семантика, не Entity). `ddd-tactical/entity-constructor-validates` ❌ публичные сеттеры
на всё (`order.status = ...`) — состояние меняется бизнес-методами (`order.confirm()`). `ddd-tactical/no-object-references-across-aggregates` ❌ ссылка на
другой агрегат объектом — только по id (`customer_id: CustomerId`). `ddd-tactical/model-is-not-anemic` ❌ анемичная модель (одни
геттеры/сеттеры, логика в сервисах).

> Не делай Entity через `@dataclass` без оглядки: дефолтный `@dataclass(eq=True)` генерирует equality по всем
> полям — это нарушает `ddd-tactical/entity-equality-by-identity`. Для Entity — обычный класс с identity-equality из базового `Entity`.

---

## 2. Value Object — `R-VO-*`

`ddd-tactical/value-object-is-immutable`/`ddd-tactical/value-object-is-immutable` — VO = `@dataclass(frozen=True)`: иммутабелен, hashable, equality по значениям (`ddd-tactical/value-equality-by-all-fields`) — всё
из коробки. `ddd-tactical/value-validates-on-creation` — инварианты в `__post_init__`. `ddd-tactical/value-object-is-immutable` — мутирующая операция возвращает новый экземпляр
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

`ddd-tactical/value-has-no-identity` ❌ id или жизненный цикл у VO. `ddd-tactical/no-primitive-obsession` ❌ primitive obsession: `str email` → `Email`, `Decimal amount`
→ `Money`. `ddd-tactical/collections-in-values-are-protected` ❌ мутабельная коллекция в VO — `tuple`/`frozenset`, не `list`/`set` (иначе `frozen=True`
не спасает от мутации содержимого, а ещё VO становится unhashable).

> Деньги — **`Decimal`**, никогда `float` (cross-ref `pg-types` `pg-types/smallint-only-for-short-scale`, `sqlalchemy/precise-column-types`).

Против primitive obsession (`ddd-tactical/no-primitive-obsession`): `str` email → VO `Email` с валидацией в `__post_init__` (`ddd-tactical/value-validates-on-creation`),
коллекция внутри VO — `tuple`, не `list` (`ddd-tactical/collections-in-values-are-protected`):

```python
# core/order/value_object/email.py
@dataclass(frozen=True)                       # R-VO-1/-2: иммутабелен, hashable, equality по значению
class Email:
    value: str

    def __post_init__(self) -> None:          # R-VO-4: инварианты в __post_init__
        if "@" not in self.value:
            raise ValueError("invalid email")

@dataclass(frozen=True)
class ShippingAddress:
    lines: tuple[str, ...]                     # R-VO-X3: tuple, не list — иначе frozen не спасает от мутации
    postcode: str
```

---

## 3. Aggregate Root — `R-AGG-*`

`ddd-tactical/aggregate-root-is-single-entry` — корень наследует `AggregateRoot[ID]`. `ddd-tactical/aggregate-root-is-single-entry` — внешние операции только через методы корня;
внутренние Entity наружу — копией/view (`tuple(self._lines)`). `ddd-tactical/events-registered-by-root` — события регистрируются в момент
изменения состояния через `self._register_event(...)`, не в репозитории. `ddd-tactical/transaction-boundary-equals-aggregate` — один use case меняет один
агрегат; на другие влияем событиями. `ddd-tactical/no-object-references-across-aggregates` — ссылки на другие агрегаты по id.

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

`ddd-tactical/aggregate-stays-small` ❌ «God aggregate». `ddd-tactical/aggregate-root-is-single-entry` ❌ `return self._lines` без обёртки (клиент мутирует внутреннее
состояние). `ddd-tactical/transaction-boundary-equals-aggregate` ❌ менять чужой агрегат напрямую. `ddd-tactical/events-registered-by-root` ❌ регистрировать события вне корня
(в Handler/репозитории/контроллере).

---

## 4. Domain Event — `R-EVT-*`

`ddd-tactical/event-is-immutable-record` — событие наследует `DomainEvent` (несёт `event_id`/`occurred_at`/`aggregate_id`). `ddd-tactical/event-named-in-past-tense` — имя
глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderEvent`). `ddd-tactical/event-is-immutable-record` — иммутабельно
(`@dataclass(frozen=True)`). `ddd-tactical/event-carries-business-context` — несёт бизнес-контекст значениями (id, `amount`, `confirmed_at`), не сам
агрегат. `ddd-tactical/events-published-after-save` — публикуются после сохранения (репозиторием/UoW), затем `aggregate.pull_events()` очищает
их (cross-ref `usecase-pattern/publish-events-after-save`, `ucp-py-pattern-*`).

```python
# core/order/event/order_confirmed.py
@dataclass(frozen=True)
class OrderConfirmed(DomainEvent):
    customer_id: UUID
    total: Decimal
    currency: str
```

`ddd-tactical/event-is-immutable-record` ❌ менять поля события после создания. `ddd-tactical/event-carries-business-context` ❌ ссылка на агрегат/Entity в событии — только
примитивы и VO. `ddd-tactical/events-published-after-save` ❌ публиковать из контроллера/Handler — только корень регистрирует. `ddd-tactical/no-after-commit-for-critical-effects` ❌
доставлять критичные эффекты «after commit» фоном (теряется при падении) — Outbox в той же транзакции
(cross-ref `R-SQLA-*`, `ucp-py-sqlalchemy-*`).

---

## 5. Repository — `R-REP-*`

`ddd-tactical/repository-port-in-domain` — порт репозитория — `Protocol` в `core/<bc>/port/`, типизирован агрегатом. `ddd-tactical/repository-port-in-domain` — реализация в
`adapters/out/persistence/` (cross-ref `sqlalchemy/port-in-core-implementation-in-adapter`); домен не знает про SQLAlchemy. `ddd-tactical/repository-per-aggregate-root` — один
репозиторий = один корень. `ddd-tactical/repository-per-aggregate-root` — `save` сохраняет агрегат целиком; публикация событий + `pull_events()` —
на границе UoW. `ddd-tactical/repository-speaks-domain` — методы в терминах домена.

```python
# core/order/port/order_repository.py
from typing import Protocol

class OrderRepository(Protocol):
    async def by_id(self, order_id: OrderId) -> Order | None: ...
    async def save(self, order: Order) -> None: ...
    async def active_by_customer(self, customer_id: CustomerId) -> list[Order]: ...
```

`ddd-tactical/repository-speaks-domain` ❌ возвращать ORM-модель/`Row` наружу (cross-ref `sqlalchemy/repository-speaks-domain-types`). `ddd-tactical/repository-speaks-domain` ❌ методы под одну
таблицу (`update_status_in_db`). `ddd-tactical/specification-is-not-a-query-builder` ❌ Specification, генерирующая SQL, в репозитории — для чтений
отдельный ViewRepository (cross-ref `usecase-pattern/reads-via-read-model`, `sqlalchemy/view-repository-for-projections`).

---

## 6. Domain Service — `R-DS-*`

`ddd-tactical/domain-service-only-across-aggregates` — Domain Service только если логика касается ≥ 2 агрегатов и не лезет в один корень. `ddd-tactical/domain-service-only-across-aggregates` —
stateless, принимает доменные объекты (не DTO/репозитории). `ddd-tactical/domain-service-only-across-aggregates` — имя — доменная операция.

```python
# core/transfer/service/transfer_service.py
class TransferService:
    def transfer(self, src: Account, dst: Account, amount: Money) -> None:
        src.withdraw(amount)
        dst.deposit(amount)
```

`ddd-tactical/domain-service-only-across-aggregates` ❌ оркестрация (загрузка из репозитория, транзакции, публикация) в Domain Service — это Application
layer (Handler). `ddd-tactical/domain-service-only-across-aggregates` ❌ Domain Service как свалка, оставляющая агрегаты анемичными.

---

## 7. Factory — `R-FAC-*`

`ddd-tactical/factory-only-when-needed` — фабрика (модульная функция / classmethod) только когда конструктор не справляется (сборка из частей,
валидация по другому агрегату, выбор подтипа). `ddd-tactical/factory-only-when-needed` — возвращает уже валидный агрегат с начальными событиями.

```python
# core/order/aggregate/order.py
@classmethod
def create(cls, customer_id: CustomerId, clock: Clock, ids: IdGenerator) -> "Order":
    order = cls(OrderId(ids.next()), customer_id)
    order._register_event(OrderCreated(uuid7(), clock.now(), order.id.value))
    return order
```

`ddd-tactical/factory-only-when-needed` ❌ Factory ради Factory — если хватает `Order(...)`, не плодить слой.

---

## 8. Specification — `R-SPEC-*`

`ddd-tactical/specification-for-reuse` — спецификация — класс с `is_satisfied_by(candidate) -> bool` (или предикат-callable). `ddd-tactical/specification-for-reuse` —
вводится, только когда правило применяется в ≥ 2 местах или нужна комбинация and/or/not.

```python
# core/order/specification/eligible_for_discount.py
class EligibleForDiscount:
    def __init__(self, threshold: Money) -> None:
        self._threshold = threshold

    def is_satisfied_by(self, order: Order) -> bool:
        return order.total().amount >= self._threshold.amount
```

`ddd-tactical/specification-is-not-a-query-builder` ❌ Specification для генерации SQL (это query-side). `ddd-tactical/specification-for-reuse` ❌ Specification ради одного `if` в
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

`ddd-tactical/packages-grouped-by-domain` — запрещено `entity/`, `service/`, `repository/` на верхнем уровне `core/` — только по Bounded Context.
`ddd-tactical/packages-grouped-by-domain` — домен (`core/<bc>/`) не импортирует `adapters/*`, FastAPI, SQLAlchemy, Pydantic. Enforce контрактом
`import-linter` (layers: `core` < `adapters` < `app`), cross-ref `hexagonal/core-free-of-framework`.

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
