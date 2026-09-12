# CQRS — реализация на Python (FastAPI / SQLAlchemy)

Реализация язык-нейтрального контракта `../spec.md` (`R-CQRS-*`) на Python. Коды общие с Java; меняется
реализация: маркеры `Command`/`Query` — `Protocol` (см. `backend/usecase-pattern/python`), read-only сторона — read-only
`AsyncSession` без commit, read-проекции — `<X>ViewRepository`-Protocol → read-DTO (frozen dataclass / Pydantic).

## 1. Когда CQRS оправдан (`R-CQRS-WHEN-*`)

`cqrs/lightweight-first-full-on-evidence` — lightweight CQRS на маркерах (`Command`/`Query` Protocol) — обязателен на Уровне 2+: один
интерфейс Handler, два маркера, read через read-only сессию. `cqrs/lightweight-first-full-on-evidence`/`cqrs/lightweight-first-full-on-evidence` — полный split
(read-DB/Redis/ES) или денормализованная read-таблица — при доказанной read-нагрузке. `cqrs/lightweight-first-full-on-evidence`/`X2` —
полный CQRS / разделение БД «just in case» без боли; стартуем lightweight, эволюционируем по метрикам.

## 2. Command side (`R-CQRS-CMD-*`)

`cqrs/command-returns-minimum` — Command = `@dataclass(frozen=True)`, реализует `Command[R]` (`usecase-pattern/usecase-implements-marker`). `cqrs/command-changes-one-aggregate` — меняет
state **одного** агрегата (несколько → saga `R-DIST-SAGA-*` или неверные границы `R-AGG-*`). `cqrs/command-handler-does-not-query` —
handler: загрузить агрегат → доменный метод → `save` → commit через UoW. `cqrs/command-returns-minimum` — возвращает минимум
(id/статус/`None`), не read-DTO. `cqrs/validation-split-edge-and-aggregate` — валидация входа на Pydantic-DTO (`validation/input-validated-at-edge`), инварианты в
агрегате (`validation/domain-invariants-in-aggregate`).

```python
@dataclass(frozen=True)
class ConfirmOrder:                       # Command[OrderId]
    order_id: OrderId

class ConfirmOrderHandler:
    def __init__(self, orders: OrderRepository, uow: UnitOfWork, clock: Clock) -> None: ...
    async def handle(self, cmd: ConfirmOrder) -> OrderId:
        async with self._uow:
            order = await self._orders.by_id(cmd.order_id)
            order.confirm(self._clock)
            await self._orders.save(order)
            await self._uow.commit()
        return order.id
```

Полный command-handler: load агрегат через **репозиторий** (никакого SQL в хендлере) → доменный метод → save →
**outbox в той же транзакции** (`cqrs/command-handler-does-not-query`, `cqrs/read-model-synced-by-events`). Хендлер только оркестрирует и держит границу UoW
(`async with ... session.begin()`); весь доступ к БД — в репозиториях:

```python
# core/order/usecases.py
@dataclass(frozen=True)
class ConfirmOrder:                                  # Command[OrderId] (R-CQRS-CMD-1: frozen dataclass)
    order_id: OrderId

# core/order/handlers.py — оркестрация; SQLAlchemy сюда не импортируется (R-CQRS-CMD-X1)
class ConfirmOrderHandler:
    def __init__(self, session_factory, orders: OrderRepository,    # порты-Protocol; реализация в adapters/out
                 outbox: OutboxRepository, clock: Clock) -> None:
        self._session_factory = session_factory
        self._orders = orders
        self._outbox = outbox
        self._clock = clock

    async def handle(self, cmd: ConfirmOrder) -> OrderId:           # R-HND-3: граница TX — здесь
        async with self._session_factory() as session, session.begin():   # один UoW, read-write
            order = await self._orders.by_id(session, cmd.order_id)       # load-aggregate = одно действие (R-CQRS-CMD-X1)
            order.confirm(self._clock.now())                              # доменный метод; инвариант — в агрегате
            await self._orders.save(session, order)
            for event in order.pull_events():                            # R-CQRS-RM-3: обновление read-model — через события
                self._outbox.add(session, event)                        # outbox в той же TX (R-CQRS-SYNC-1, R-CQRS-SYNC-X1)
        return order.id                                                  # R-CQRS-CMD-4: минимум (id), не read-DTO
```

`cqrs/command-handler-does-not-query` — SELECT «для чтения и потом обновления» в command (read идёт через query; load-aggregate —
одно действие, не отдельный read). `cqrs/command-returns-minimum` — возврат полного read-DTO из command (контроллер сам
дёрнет query). `cqrs/command-changes-one-aggregate` — несколько агрегатов в одном UoW без саги.

## 3. Query side (`R-CQRS-QRY-*`)

`cqrs/query-is-read-only` — Query = `@dataclass(frozen=True)`, реализует `Query[R]`. `cqrs/query-is-read-only` — handler читает через
`<X>ViewRepository`, read-only сессия, без commit. `cqrs/query-returns-read-model` — read-DTO в `core/<bc>/port/` (или `.../view/`),
структура под UI/API, не агрегат. `cqrs/query-is-read-only` — query-handler не зовёт доменные методы агрегата.

`cqrs/query-is-read-only` — write (UPDATE/INSERT/DELETE) в query-handler → это command. `cqrs/read-via-projection-not-aggregate` — грузит агрегат
целиком основным `<X>Repository` (с eager-load/`FOR UPDATE`) и мапит в read-DTO — используй/создай
`<X>ViewRepository` (`sqlalchemy/view-repository-for-projections`). `cqrs/query-returns-read-model` — возвращает агрегат/Entity наружу (потребитель вызовет
доменный метод на read-объекте).

Query-side читает через `<X>ViewRepository` (отдельный порт), а не основной агрегат-репозиторий. ViewRepository
делает узкий `SELECT` нужных колонок и собирает **read-DTO (Pydantic `model_validate`)** — не агрегат
(`cqrs/query-is-read-only`, `cqrs/query-returns-read-model`). Сессия read-only: без `session.begin()`, без commit:

```python
# core/order/view.py — read-DTO под нужды UI/API, не агрегат (R-CQRS-QRY-3)
class OrderSummaryView(BaseModel):
    order_id: UUID
    status: str
    customer_name: str                  # денормализовано: без join к customer (R-CQRS-RM-2)
    total_amount: Decimal               # деньги — Decimal; pre-computed
    item_count: int                     # не list[OrderItem] — число
    created_at: datetime                # aware datetime

# core/order/port/order_view_repository.py
class OrderViewRepository(Protocol):
    async def summary_by_id(self, session: AsyncSession, order_id: UUID) -> OrderSummaryView | None: ...

# adapters/out/persistence/order_view_repository.py — SQL живёт ТОЛЬКО здесь (R-CQRS-QRY-X2)
class SqlAlchemyOrderViewRepository:
    async def summary_by_id(self, session, order_id):
        row = (await session.execute(
            select(                                       # узкий select из read-таблицы/проекции, не агрегат целиком
                OrderSummaryModel.order_id, OrderSummaryModel.status,
                OrderSummaryModel.customer_name, OrderSummaryModel.total_amount,
                OrderSummaryModel.item_count, OrderSummaryModel.created_at,
            ).where(OrderSummaryModel.order_id == order_id)
        )).mappings().one_or_none()
        return OrderSummaryView.model_validate(row) if row else None    # read-DTO, не ORM/агрегат (R-CQRS-QRY-X3)

# core/order/handlers.py — query-handler: read-only сессия, без begin/commit (R-CQRS-QRY-2)
@dataclass(frozen=True)
class GetOrderSummary:                                  # Query[OrderSummaryView]
    order_id: UUID

class GetOrderSummaryHandler:
    def __init__(self, session_factory, views: OrderViewRepository) -> None:
        self._session_factory = session_factory
        self._views = views

    async def handle(self, q: GetOrderSummary) -> OrderSummaryView:
        async with self._session_factory() as session:                 # read-only: НЕТ session.begin() (R-CQRS-QRY-X1)
            view = await self._views.summary_by_id(session, q.order_id)
            if view is None:
                raise NotFoundError(f"order {q.order_id} not found")
            return view                                                 # доменные методы не зовём (R-CQRS-QRY-4)
```

## 4. Read-model (`R-CQRS-RM-*`)

`cqrs/read-model-storage-and-schema` — read-model в месте, оптимальном под чтение (PG-таблица / Redis / ES). `cqrs/read-model-storage-and-schema` —
денормализована, независима от write-схемы. `cqrs/read-model-synced-by-events` — обновляется **через события** (`R-CQRS-SYNC-*`), не
синхронно в command-handler. `cqrs/read-model-is-rebuildable` — восстановима из write-side (rebuild-скрипт по агрегатам).

`cqrs/projection-has-no-logic-or-backflow` — бизнес-логика в read-model (триггеры/CHECK бизнес-правил) — логика в write-side. `cqrs/read-model-is-rebuildable` —
read-model как source-of-truth (невосстановима из write) — это две системы. `cqrs/projection-has-no-logic-or-backflow` — bidirectional sync
(read → write); eventual consistency в одну сторону: write → events → read.

## 5. Синхронизация через события (`R-CQRS-SYNC-*`)

`cqrs/read-model-synced-by-events` — sync через outbox + Kafka (`kafka/publish-via-outbox`, см. `ucp-py-kafka-*`). `cqrs/read-model-consumer-is-idempotent` — idempotent
consumer обязателен (`processed_event` / version-проверка, `kafka/consumer-is-idempotent`). `cqrs/read-model-is-rebuildable` — синхронный rebuild
при бутстрапе/потере read-model. `cqrs/eventual-consistency-declared` — eventual consistency декларируется в OpenAPI (FastAPI code-first:
описание в docstring/response-модели эндпоинта). `cqrs/eventual-consistency-declared` — read-your-writes при необходимости (читать из
write-side для того же клиента / version-токен).

`cqrs/read-model-synced-by-events` — синхронный INSERT в read-таблицу внутри command-UoW (теряется decoupling, откатывается с TX) —
через outbox. `cqrs/read-model-synced-by-events` — sync через PG-триггеры (магия, ломается на bulk, не cross-DB). `cqrs/events-not-coupled-to-write-schema` —
schema-coupled events (payload = ORM-модель write-схемы; ALTER ломает consumer'ов, `kafka/event-schema-forward-compatible`).

Read-side consumer обновляет read-model **идемпотентно**: дедуп по `event_id` через `processed_event` в той же TX,
что и UPSERT проекции (`cqrs/read-model-consumer-is-idempotent`, cross-ref `kafka/processed-record-in-same-transaction`). Доступ к read-таблице — через `ViewRepository`;
consumer лишь оркестрирует и держит границу UoW:

```python
# adapters/in/messaging/order_summary_consumer.py — read-side; обновляет read-model по событию (R-CQRS-RM-3)
class OrderSummaryProjector:
    def __init__(self, session_factory, processed: ProcessedEventRepository,
                 summaries: OrderSummaryWriteRepository) -> None:
        self._session_factory = session_factory
        self._processed = processed       # дедуп-репозиторий
        self._summaries = summaries       # write-сторона read-модели (UPSERT проекции)

    async def on_order_confirmed(self, event: OrderConfirmedSchema) -> None:
        async with self._session_factory() as session, session.begin():    # одна TX (R-CQRS-SYNC-2)
            if await self._processed.exists(session, event.event_id):
                return                                                      # дубль → skip (идемпотентность)
            await self._summaries.upsert(                                   # денормализованный UPSERT, без бизнес-логики (R-CQRS-RM-X1)
                session, order_id=event.order_id, status="CONFIRMED",
                total_amount=event.total_amount)                           # Decimal; read-model восстановима из write (R-CQRS-RM-4)
            await self._processed.mark(session, event.event_id, consumer_group="order-summary-projector")
```

## 6. Уровень и эволюция (`R-CQRS-TIER-*`)

`cqrs/split-matches-maturity-level` — Уровень 1 (плоский): CQRS нет. `cqrs/split-matches-maturity-level` — Уровень 2: lightweight, маркеры обязательны,
read и write через один `<X>Repository`, read-методы — read-only сессия. `cqrs/split-matches-maturity-level` — Уровень 3: появляется
`<X>ViewRepository` с read-DTO; write — `<X>Repository` с агрегатом и `FOR UPDATE`. `cqrs/split-matches-maturity-level` — Уровень 3
event-driven: read-model в отдельной таблице/Redis/ES, sync через outbox+Kafka. `cqrs/evolution-is-one-way` — эволюция в одну
сторону.

`cqrs/split-matches-maturity-level` — маркеры без enforcement (read-only сессия, отдельный repository) — карго-культ. `cqrs/split-matches-maturity-level` —
event-driven read-model с одним `<X>Repository` для read и write (есть отдельная инфра → отдельный интерфейс).

## 7. Чеклист подключения к новому сервису (Python)

1. Команды/запросы помечены `Command`/`Query`-протоколом; есть enforcement (read-only сессия для query).
2. Command меняет один агрегат, возвращает минимум; query не зовёт доменные методы и не пишет.
3. Read через `<X>ViewRepository` → read-DTO, не агрегат наружу.
4. Read-model денормализована, восстановима, sync через outbox+Kafka в одну сторону.
5. Нет sync UPDATE read-model в command-UoW, нет PG-триггеров, нет schema-coupled events.
6. Уровень соответствует зрелости; eventual consistency задекларирована в API.
