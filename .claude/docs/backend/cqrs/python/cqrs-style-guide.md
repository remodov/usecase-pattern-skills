# CQRS — Python Style Guide (FastAPI / SQLAlchemy)

Реализация язык-нейтрального контракта `../cqrs-rules.md` (`R-CQRS-*`) на Python. Коды общие с Java; меняется
реализация: маркеры `Command`/`Query` — `Protocol` (см. `backend/usecase-pattern/python`), read-only сторона — read-only
`AsyncSession` без commit, read-проекции — `<X>ViewRepository`-Protocol → read-DTO (frozen dataclass / Pydantic).

## 1. Когда CQRS оправдан (`R-CQRS-WHEN-*`)

`R-CQRS-WHEN-1` — lightweight CQRS на маркерах (`Command`/`Query` Protocol) — обязателен на Уровне 2+: один
интерфейс Handler, два маркера, read через read-only сессию. `R-CQRS-WHEN-2`/`R-CQRS-WHEN-3` — полный split
(read-DB/Redis/ES) или денормализованная read-таблица — при доказанной read-нагрузке. `R-CQRS-WHEN-X1`/`X2` —
полный CQRS / разделение БД «just in case» без боли; стартуем lightweight, эволюционируем по метрикам.

## 2. Command side (`R-CQRS-CMD-*`)

`R-CQRS-CMD-1` — Command = `@dataclass(frozen=True)`, реализует `Command[R]` (`R-UC-1`). `R-CQRS-CMD-2` — меняет
state **одного** агрегата (несколько → saga `R-DIST-SAGA-*` или неверные границы `R-AGG-*`). `R-CQRS-CMD-3` —
handler: загрузить агрегат → доменный метод → `save` → commit через UoW. `R-CQRS-CMD-4` — возвращает минимум
(id/статус/`None`), не read-DTO. `R-CQRS-CMD-5` — валидация входа на Pydantic-DTO (`R-VLD-WHERE-1`), инварианты в
агрегате (`R-VLD-WHERE-3`).

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

`R-CQRS-CMD-X1` — SELECT «для чтения и потом обновления» в command (read идёт через query; load-aggregate —
одно действие, не отдельный read). `R-CQRS-CMD-X2` — возврат полного read-DTO из command (контроллер сам
дёрнет query). `R-CQRS-CMD-X3` — несколько агрегатов в одном UoW без саги.

## 3. Query side (`R-CQRS-QRY-*`)

`R-CQRS-QRY-1` — Query = `@dataclass(frozen=True)`, реализует `Query[R]`. `R-CQRS-QRY-2` — handler читает через
`<X>ViewRepository`, read-only сессия, без commit. `R-CQRS-QRY-3` — read-DTO в `core/<bc>/port/` (или `.../view/`),
структура под UI/API, не агрегат. `R-CQRS-QRY-4` — query-handler не зовёт доменные методы агрегата.

`R-CQRS-QRY-X1` — write (UPDATE/INSERT/DELETE) в query-handler → это command. `R-CQRS-QRY-X2` — грузит агрегат
целиком основным `<X>Repository` (с eager-load/`FOR UPDATE`) и мапит в read-DTO — используй/создай
`<X>ViewRepository` (`R-SQLA-QRY-5`). `R-CQRS-QRY-X3` — возвращает агрегат/Entity наружу (потребитель вызовет
доменный метод на read-объекте).

## 4. Read-model (`R-CQRS-RM-*`)

`R-CQRS-RM-1` — read-model в месте, оптимальном под чтение (PG-таблица / Redis / ES). `R-CQRS-RM-2` —
денормализована, независима от write-схемы. `R-CQRS-RM-3` — обновляется **через события** (`R-CQRS-SYNC-*`), не
синхронно в command-handler. `R-CQRS-RM-4` — восстановима из write-side (rebuild-скрипт по агрегатам).

`R-CQRS-RM-X1` — бизнес-логика в read-model (триггеры/CHECK бизнес-правил) — логика в write-side. `R-CQRS-RM-X2` —
read-model как source-of-truth (невосстановима из write) — это две системы. `R-CQRS-RM-X3` — bidirectional sync
(read → write); eventual consistency в одну сторону: write → events → read.

## 5. Синхронизация через события (`R-CQRS-SYNC-*`)

`R-CQRS-SYNC-1` — sync через outbox + Kafka (`R-KFK-OBX-1`, см. `ucp-py-kafka-*`). `R-CQRS-SYNC-2` — idempotent
consumer обязателен (`processed_event` / version-проверка, `R-KFK-IDEM-1`). `R-CQRS-SYNC-3` — синхронный rebuild
при бутстрапе/потере read-model. `R-CQRS-SYNC-4` — eventual consistency декларируется в OpenAPI (FastAPI code-first:
описание в docstring/response-модели эндпоинта). `R-CQRS-SYNC-5` — read-your-writes при необходимости (читать из
write-side для того же клиента / version-токен).

`R-CQRS-SYNC-X1` — синхронный INSERT в read-таблицу внутри command-UoW (теряется decoupling, откатывается с TX) —
через outbox. `R-CQRS-SYNC-X2` — sync через PG-триггеры (магия, ломается на bulk, не cross-DB). `R-CQRS-SYNC-X3` —
schema-coupled events (payload = ORM-модель write-схемы; ALTER ломает consumer'ов, `R-KFK-EVT-X4`).

## 6. Уровень и эволюция (`R-CQRS-TIER-*`)

`R-CQRS-TIER-1` — Уровень 1 (плоский): CQRS нет. `R-CQRS-TIER-2` — Уровень 2: lightweight, маркеры обязательны,
read и write через один `<X>Repository`, read-методы — read-only сессия. `R-CQRS-TIER-3` — Уровень 3: появляется
`<X>ViewRepository` с read-DTO; write — `<X>Repository` с агрегатом и `FOR UPDATE`. `R-CQRS-TIER-4` — Уровень 3
event-driven: read-model в отдельной таблице/Redis/ES, sync через outbox+Kafka. `R-CQRS-TIER-5` — эволюция в одну
сторону.

`R-CQRS-TIER-X1` — маркеры без enforcement (read-only сессия, отдельный repository) — карго-культ. `R-CQRS-TIER-X2` —
event-driven read-model с одним `<X>Repository` для read и write (есть отдельная инфра → отдельный интерфейс).

## 7. Чеклист подключения к новому сервису (Python)

1. Команды/запросы помечены `Command`/`Query`-протоколом; есть enforcement (read-only сессия для query).
2. Command меняет один агрегат, возвращает минимум; query не зовёт доменные методы и не пишет.
3. Read через `<X>ViewRepository` → read-DTO, не агрегат наружу.
4. Read-model денормализована, восстановима, sync через outbox+Kafka в одну сторону.
5. Нет sync UPDATE read-model в command-UoW, нет PG-триггеров, нет schema-coupled events.
6. Уровень соответствует зрелости; eventual consistency задекларирована в API.
