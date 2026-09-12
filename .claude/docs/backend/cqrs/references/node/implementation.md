# CQRS — реализация на Node (NestJS / TypeORM)

Реализация язык-нейтрального контракта `../spec.md` (`R-CQRS-*`) на Node. Коды общие с Java и Python;
меняется реализация: маркеры `Command`/`Query` — интерфейсы из `core/usecase.ts` (см.
`backend/usecase-pattern/node`), read-сторона — без транзакции через `<X>ViewRepository` с raw select
(cross-ref `typeorm/view-repository-for-projections`) → read-DTO (frozen plain object / readonly-класс).

## 1. Когда CQRS оправдан (`R-CQRS-WHEN-*`)

`cqrs/lightweight-first-full-on-evidence` — lightweight CQRS на маркерах (`Command<R>`/`Query<R>`) — обязателен на Уровне 2+: один
интерфейс Handler, два маркера, read без транзакции. `cqrs/lightweight-first-full-on-evidence`/`cqrs/lightweight-first-full-on-evidence` — полный split
(read-DB/Redis/ES) или денормализованная read-таблица — при доказанной read-нагрузке. `cqrs/lightweight-first-full-on-evidence`/`cqrs/lightweight-first-full-on-evidence` —
полный CQRS / разделение БД «just in case» без боли; стартуем lightweight, эволюционируем по метрикам.

## 2. Command side (`R-CQRS-CMD-*`)

`cqrs/command-returns-minimum` — Command — класс с `readonly`-полями, реализует `Command<R>` (`usecase-pattern/usecase-implements-marker`). `cqrs/command-changes-one-aggregate` —
меняет state **одного** агрегата (несколько → saga `R-DIST-SAGA-*` или неверные границы `R-AGG-*`).
`cqrs/command-handler-does-not-query` — handler: загрузить агрегат → доменный метод → `save` → commit на границе Handler
(`typeorm/transaction-on-handler`). `cqrs/command-returns-minimum` — возвращает минимум (id/статус/empty), не read-DTO. `cqrs/validation-split-edge-and-aggregate` —
валидация входа на request-DTO через class-validator (`validation/input-validated-at-edge`), инварианты в агрегате (`validation/domain-invariants-in-aggregate`).

```ts
export class ConfirmOrder implements Command<OrderId> {
  constructor(readonly orderId: OrderId) {}
}

@Injectable()
export class ConfirmOrderHandler implements Handler<ConfirmOrder, OrderId> {
  constructor(@Inject(ORDER_REPOSITORY) private readonly orders: OrderRepository,
              @Inject(TX_RUNNER) private readonly tx: TransactionRunner,
              @Inject(CLOCK) private readonly clock: Clock) {}

  async execute(cmd: ConfirmOrder): Promise<OrderId> {
    return this.tx.run(async () => {
      const order = await this.orders.byId(cmd.orderId);
      if (!order) throw new OrderNotFoundError(cmd.orderId);
      order.confirm(this.clock.now());
      await this.orders.save(order);
      return order.id;
    });
  }
}
```

`cqrs/command-handler-does-not-query` — SELECT «для чтения и потом обновления» в command (read идёт через query; load-aggregate —
одно действие, не отдельный read). `cqrs/command-returns-minimum` — возврат полного read-DTO из command (контроллер сам
дёрнет query). `cqrs/command-changes-one-aggregate` — несколько агрегатов в одной транзакции без саги.

## 3. Query side (`R-CQRS-QRY-*`)

`cqrs/query-is-read-only` — Query — класс с `readonly`-полями, реализует `Query<R>`. `cqrs/query-is-read-only` — handler читает
через `<X>ViewRepository`, без транзакции и без записи (`typeorm/transaction-on-handler`). `cqrs/query-returns-read-model` — read-DTO в
`core/<bc>/port/` (или `.../view/`), структура под UI/API, не агрегат. `cqrs/query-is-read-only` — query-handler не зовёт
доменные методы агрегата.

```ts
// adapters/out/persistence/typeorm-order-view.repository.ts — R-TYPEORM-QRY-4: raw select, не агрегат
@Injectable()
export class TypeOrmOrderViewRepository implements OrderViewRepository {
  constructor(private readonly dataSource: DataSource) {}

  async summary(orderId: OrderId): Promise<OrderSummary | null> {
    const rows = await this.dataSource.query(
      `SELECT o.id, o.status, o.customer_name, o.total_amount, o.created_at
         FROM order_summary o WHERE o.id = $1`, [orderId]);
    return rows[0] ? toOrderSummary(rows[0]) : null;
  }
}
```

`cqrs/query-is-read-only` — write (UPDATE/INSERT/DELETE) в query-handler → это command. `cqrs/read-via-projection-not-aggregate` — грузит агрегат
целиком основным `<X>Repository` (с `relations`/lock) и мапит в read-DTO — используй/создай `<X>ViewRepository`.
`cqrs/query-returns-read-model` — возвращает агрегат/Entity наружу (потребитель вызовет доменный метод на read-объекте).

## 4. Read-model (`R-CQRS-RM-*`)

`cqrs/read-model-storage-and-schema` — read-model в месте, оптимальном под чтение (PG-таблица / Redis / ES). `cqrs/read-model-storage-and-schema` —
денормализована, независима от write-схемы. `cqrs/read-model-synced-by-events` — обновляется **через события** (`R-CQRS-SYNC-*`),
не синхронно в command-handler. `cqrs/read-model-is-rebuildable` — восстановима из write-side (rebuild-скрипт по агрегатам).

`cqrs/projection-has-no-logic-or-backflow` — бизнес-логика в read-model (триггеры/CHECK бизнес-правил) — логика в write-side.
`cqrs/read-model-is-rebuildable` — read-model как source-of-truth (невосстановима из write) — это две системы. `cqrs/projection-has-no-logic-or-backflow` —
bidirectional sync (read → write); eventual consistency в одну сторону: write → events → read.

## 5. Синхронизация через события (`R-CQRS-SYNC-*`)

`cqrs/read-model-synced-by-events` — sync через outbox + Kafka (`kafka/publish-via-outbox`): outbox-строка в той же транзакции, relay
публикует, read-side consumer обновляет проекцию. `cqrs/read-model-consumer-is-idempotent` — idempotent consumer обязателен
(`processed_event` / version-проверка, `kafka/consumer-is-idempotent`). `cqrs/read-model-is-rebuildable` — синхронный rebuild при
бутстрапе/потере read-model. `cqrs/eventual-consistency-declared` — eventual consistency декларируется в OpenAPI (`@nestjs/swagger`:
`@ApiOperation({ description })` у эндпоинта проекции). `cqrs/eventual-consistency-declared` — read-your-writes при необходимости
(чтение из write-side для того же клиента / version-токен).

`cqrs/read-model-synced-by-events` — синхронный INSERT в read-таблицу внутри command-транзакции (теряется decoupling,
откатывается с TX) — через outbox. `cqrs/read-model-synced-by-events` — sync через PG-триггеры (магия, ломается на bulk, не
cross-DB). `cqrs/events-not-coupled-to-write-schema` — schema-coupled events (payload = TypeORM-Entity write-схемы; ALTER ломает
consumer'ов, `kafka/event-schema-forward-compatible`).

## 6. Уровень и эволюция (`R-CQRS-TIER-*`)

`cqrs/split-matches-maturity-level` — Уровень 1 (плоский): CQRS нет. `cqrs/split-matches-maturity-level` — Уровень 2: lightweight, маркеры
обязательны, read и write через один `<X>Repository`, read-методы — без транзакции/без lock.
`cqrs/split-matches-maturity-level` — Уровень 3: появляется `<X>ViewRepository` (raw select → read-DTO, `typeorm/view-repository-for-projections`);
write — `<X>Repository` с агрегатом и pessimistic lock. `cqrs/split-matches-maturity-level` — Уровень 3 event-driven: read-model
в отдельной таблице/Redis/ES, sync через outbox+Kafka. `cqrs/evolution-is-one-way` — эволюция в одну сторону.

`cqrs/split-matches-maturity-level` — маркеры без enforcement (read без транзакции, отдельный repository) — карго-культ.
`cqrs/split-matches-maturity-level` — event-driven read-model с одним `<X>Repository` для read и write (есть отдельная инфра →
отдельный интерфейс).

## 7. Чеклист подключения к новому сервису (Node/NestJS)

1. Команды/запросы помечены `Command<R>`/`Query<R>`; есть enforcement (query-handler без транзакции и записи).
2. Command меняет один агрегат, возвращает минимум; query не зовёт доменные методы и не пишет.
3. Read через `<X>ViewRepository` (raw select с bind-параметрами) → read-DTO, не агрегат наружу.
4. Read-model денормализована, восстановима, sync через outbox+Kafka в одну сторону.
5. Нет sync UPDATE read-model в command-транзакции, нет PG-триггеров, нет schema-coupled events.
6. Уровень соответствует зрелости; eventual consistency задекларирована в API.
