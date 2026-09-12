# DDD Tactical Patterns — реализация на Node (чистый TypeScript в `core/`)

Реализация язык-нейтрального контракта `../spec.md` (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`)
на Node/TypeScript. Коды правил — общие с Java и Python; здесь — как они выглядят в NestJS-сервисе. Домен живёт
в `core/` **без фреймворка** (ни NestJS-декораторов, ни TypeORM, ни class-validator) — чистый TypeScript;
enforce через dependency-cruiser / eslint-boundaries.

В Node нет библиотеки `ddd-building-blocks` — базовые типы тонкие, ручные (ниже). Идиомы: **Entity** — класс
с identity-equality через `equals()` (в JS нет перегрузки `===` — структурного равенства по умолчанию тоже нет,
сравнение объектов всегда по ссылке, поэтому `equals()` обязателен явно); **VO** — иммутабельный класс с
value-equality, для одно-полевых идентификаторов — branded type; **Aggregate Root** — Entity + список событий.

```ts
// core/shared/building-blocks.ts
export abstract class Entity<ID> {
  protected constructor(readonly id: ID) {}

  equals(other: Entity<ID>): boolean {
    return other instanceof this.constructor && this.idEquals(other.id);
  }

  private idEquals(otherId: ID): boolean {
    return this.id instanceof ValueObject ? this.id.equals(otherId as ValueObject) : this.id === otherId;
  }
}

export abstract class ValueObject {
  equals(other: ValueObject): boolean {
    return other instanceof this.constructor
      && JSON.stringify(this.components()) === JSON.stringify(other.components());
  }
  protected abstract components(): ReadonlyArray<unknown>;   // ВСЕ значимые поля (R-VO-3)
}

export abstract class DomainEvent {
  protected constructor(
    readonly eventId: string,
    readonly occurredAt: Date,
    readonly aggregateId: string,
  ) {}
}

export abstract class AggregateRoot<ID> extends Entity<ID> {
  private readonly events: DomainEvent[] = [];

  protected registerEvent(event: DomainEvent): void {
    this.events.push(event);
  }

  pullEvents(): DomainEvent[] {
    return this.events.splice(0, this.events.length);
  }
}
```

---

## 1. Entity — `R-ENT-*`

`ddd-tactical/entity-equality-by-identity` — сущность наследует `Entity<ID>` (или живёт внутри агрегата). `ddd-tactical/identity-is-immutable`/`ddd-tactical/identity-is-immutable` — идентификатор
задаётся в конструкторе и неизменяем (`readonly id`, без сеттера). `ddd-tactical/entity-equality-by-identity` — equality по id через базовый
`equals()`, **не переопределять** в наследниках; сравнение `a === b` для сущностей из разных загрузок всегда
false — использовать `a.equals(b)`. `ddd-tactical/entity-constructor-validates` — конструктор валидирует инварианты; невалидная сущность не
должна существовать.

```ts
// core/order/entity/order-line.ts
export class OrderLine extends Entity<string> {
  constructor(id: string, readonly productId: ProductId, private qty: number, private readonly price: Money) {
    if (qty <= 0) throw new DomainError('qty must be positive');
    super(id);
  }

  subtotal(): Money {
    return this.price.multiply(this.qty);
  }
}
```

`ddd-tactical/entity-equality-by-identity` ❌ переопределять `equals` в наследниках. `ddd-tactical/entity-equality-by-identity` ❌ сравнивать сущности по полям
(`JSON.stringify(a) === JSON.stringify(b)` / lodash `isEqual` — это VO-семантика). `ddd-tactical/entity-constructor-validates` ❌ публичные
мутабельные поля / сеттеры на всё (`order.status = ...`) — состояние меняется бизнес-методами
(`order.confirm()`), поля `private`. `ddd-tactical/no-object-references-across-aggregates` ❌ ссылка на другой агрегат объектом — только по id
(`customerId: CustomerId`). `ddd-tactical/model-is-not-anemic` ❌ анемичная модель (interface с полями + логика в сервисах).

> Не делай Entity plain-интерфейсом/type — TypeScript структурно типизирован, два разных «Entity» с одинаковой
> формой взаимозаменяемы для компилятора. Класс + identity-equality из базового `Entity` фиксируют семантику.

---

## 2. Value Object — `R-VO-*`

`ddd-tactical/value-object-is-immutable`/`ddd-tactical/value-object-is-immutable` — VO — класс, наследующий `ValueObject`, все поля `readonly` (для защиты в runtime —
`Object.freeze(this)` в конструкторе). `ddd-tactical/value-equality-by-all-fields` — `equals()` сравнивает **все** значимые поля — базовый класс
делает это через `components()`. `ddd-tactical/value-validates-on-creation` — инварианты в конструкторе. `ddd-tactical/value-object-is-immutable` — мутирующая операция
возвращает новый экземпляр.

```ts
// core/order/value-object/money.ts
import Big from 'big.js';

export class Money extends ValueObject {
  constructor(readonly amount: Big, readonly currency: string) {
    super();
    if (amount.lt(0)) throw new DomainError('amount must be non-negative');
    if (currency.length !== 3) throw new DomainError('currency must be ISO-4217');
    Object.freeze(this);
  }

  multiply(factor: number): Money {
    return new Money(this.amount.times(factor), this.currency);
  }

  protected components(): ReadonlyArray<unknown> {
    return [this.amount.toString(), this.currency];
  }
}
```

Для одно-полевых идентификаторов класс — overkill; допустим **branded type** (compile-time-различимость без
runtime-стоимости):

```ts
// core/order/value-object/ids.ts
export type OrderId = string & { readonly __brand: 'OrderId' };
export const OrderId = (value: string): OrderId => {
  if (!isUuid(value)) throw new DomainError('OrderId must be uuid');
  return value as OrderId;
};
```

`ddd-tactical/value-has-no-identity` ❌ id или жизненный цикл у VO. `ddd-tactical/no-primitive-obsession` ❌ primitive obsession: `string email` → `Email`,
`number amount` → `Money` (деньги — **Big.js/decimal.js поверх string из БД, никогда `number`**, cross-ref
`typeorm/precise-column-types`). `ddd-tactical/collections-in-values-are-protected` ❌ мутабельный массив в VO — `ReadonlyArray` + копия в конструкторе
(`readonly`-модификатор TS не защищает в runtime; `Object.freeze` — защищает сам объект, но не вложенные).

---

## 3. Aggregate Root — `R-AGG-*`

`ddd-tactical/aggregate-root-is-single-entry` — корень наследует `AggregateRoot<ID>`. `ddd-tactical/aggregate-root-is-single-entry` — внешние операции только через методы корня;
внутренние Entity наружу — копией (`[...this.lines]`) или `ReadonlyArray`. `ddd-tactical/events-registered-by-root` — события регистрируются
в момент изменения состояния через `this.registerEvent(...)`, не в репозитории. `ddd-tactical/transaction-boundary-equals-aggregate` — один use case
меняет один агрегат; на другие влияем событиями. `ddd-tactical/no-object-references-across-aggregates` — ссылки на другие агрегаты по id.

```ts
// core/order/aggregate/order.ts
export class Order extends AggregateRoot<OrderId> {
  private status: OrderStatus = OrderStatus.NEW;
  private readonly orderLines: OrderLine[] = [];

  constructor(id: OrderId, readonly customerId: CustomerId) {
    super(id);
  }

  get lines(): ReadonlyArray<OrderLine> {
    return [...this.orderLines];
  }

  confirm(now: Date): void {
    if (this.orderLines.length === 0) throw new DomainError('cannot confirm empty order');
    this.status = OrderStatus.CONFIRMED;
    this.registerEvent(new OrderConfirmed(uuidv7(), now, this.id, this.customerId, this.total()));
  }
}
```

`ddd-tactical/aggregate-stays-small` ❌ «God aggregate». `ddd-tactical/aggregate-root-is-single-entry` ❌ `return this.orderLines` без копии — `ReadonlyArray` в сигнатуре
не мешает вызвавшему сделать `(lines as OrderLine[]).push(...)`; отдавать копию. `ddd-tactical/transaction-boundary-equals-aggregate` ❌ менять чужой
агрегат напрямую. `ddd-tactical/events-registered-by-root` ❌ регистрировать события вне корня (в Handler/репозитории/контроллере).

---

## 4. Domain Event — `R-EVT-*`

`ddd-tactical/event-is-immutable-record` — событие наследует `DomainEvent` (несёт `eventId`/`occurredAt`/`aggregateId`). `ddd-tactical/event-named-in-past-tense` — имя
глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderEvent`). `ddd-tactical/event-is-immutable-record` — иммутабельно:
все поля `readonly`, `Object.freeze(this)` в конструкторе. `ddd-tactical/event-carries-business-context` — несёт бизнес-контекст значениями
(id, `total`, `confirmedAt`), не сам агрегат. `ddd-tactical/events-published-after-save` — события собираются в агрегате и публикуются после
`repository.save(...)` — в Outbox **в той же транзакции**; затем `aggregate.pullEvents()` очищает накопленное
(cross-ref `usecase-pattern/publish-events-after-save`, `usecase-pattern/node`).

```ts
// core/order/event/order-confirmed.ts
export class OrderConfirmed extends DomainEvent {
  constructor(eventId: string, occurredAt: Date, orderId: OrderId,
              readonly customerId: CustomerId, readonly total: Money) {
    super(eventId, occurredAt, orderId);
    Object.freeze(this);
  }
}
```

`ddd-tactical/event-is-immutable-record` ❌ менять поля события после создания. `ddd-tactical/event-carries-business-context` ❌ ссылка на агрегат/Entity в событии — только
примитивы и VO. `ddd-tactical/events-published-after-save` ❌ публиковать из контроллера/Handler — только корень регистрирует. `ddd-tactical/no-after-commit-for-critical-effects` ❌
критичные эффекты «после commit» фоном (`EventEmitter2`-listener после ответа — теряется при падении
процесса) — Outbox в той же транзакции (cross-ref `R-TYPEORM-TX-*`).

---

## 5. Repository — `R-REP-*`

`ddd-tactical/repository-port-in-domain` — порт репозитория — интерфейс + Symbol-токен в `core/<bc>/port/`, типизирован агрегатом.
`ddd-tactical/repository-port-in-domain` — реализация в `adapters/out/persistence/` (cross-ref `typeorm/port-in-core-implementation-in-adapter`); домен не знает про
TypeORM. `ddd-tactical/repository-per-aggregate-root` — один репозиторий = один корень. `ddd-tactical/repository-per-aggregate-root` — `save` сохраняет агрегат целиком в одной
транзакции; публикация событий + `pullEvents()` — на границе транзакции Handler-а. `ddd-tactical/repository-speaks-domain` — методы в
терминах домена.

```ts
// core/order/port/order-repository.ts
export const ORDER_REPOSITORY = Symbol('OrderRepository');

export interface OrderRepository {
  byId(orderId: OrderId): Promise<Order | null>;
  save(order: Order): Promise<void>;
  activeByCustomer(customerId: CustomerId): Promise<Order[]>;
}
```

`ddd-tactical/repository-speaks-domain` ❌ возвращать TypeORM-Entity/raw row наружу (cross-ref `typeorm/repository-speaks-domain-types`); маппинг Entity ↔
domain — явный маппер (`typeorm/explicit-mapper`). `ddd-tactical/repository-speaks-domain` ❌ методы под одну таблицу (`updateStatusInDb`).
`ddd-tactical/specification-is-not-a-query-builder` ❌ Specification, генерирующая SQL, в репозитории — для чтений отдельный ViewRepository
(cross-ref `usecase-pattern/reads-via-read-model`, `typeorm/view-repository-for-projections`).

---

## 6. Domain Service — `R-DS-*`

`ddd-tactical/domain-service-only-across-aggregates` — Domain Service только если логика касается ≥ 2 агрегатов и не лезет в один корень. `ddd-tactical/domain-service-only-across-aggregates` —
stateless plain class (без `@Injectable` — он в `core/`), принимает доменные объекты (не DTO/репозитории).
`ddd-tactical/domain-service-only-across-aggregates` — имя — доменная операция.

```ts
// core/transfer/service/transfer.service.ts
export class TransferService {
  transfer(src: Account, dst: Account, amount: Money): void {
    src.withdraw(amount);
    dst.deposit(amount);
  }
}
```

`ddd-tactical/domain-service-only-across-aggregates` ❌ оркестрация (загрузка из репозитория, транзакции, публикация) в Domain Service — это Handler.
`ddd-tactical/domain-service-only-across-aggregates` ❌ Domain Service как свалка, оставляющая агрегаты анемичными.

---

## 7. Factory — `R-FAC-*`

`ddd-tactical/factory-only-when-needed` — фабрика (static-метод / отдельная функция) только когда конструктор не справляется (сборка из
частей, валидация по другому агрегату, выбор подтипа). `ddd-tactical/factory-only-when-needed` — возвращает уже валидный агрегат с
начальными событиями.

```ts
// core/order/aggregate/order.ts
static create(customerId: CustomerId, now: Date, ids: IdGenerator): Order {
  const order = new Order(OrderId(ids.next()), customerId);
  order.registerEvent(new OrderCreated(uuidv7(), now, order.id, customerId));
  return order;
}
```

`ddd-tactical/factory-only-when-needed` ❌ Factory ради Factory — если хватает `new Order(...)`, не плодить слой.

---

## 8. Specification — `R-SPEC-*`

`ddd-tactical/specification-for-reuse` — спецификация — класс с `isSatisfiedBy(candidate): boolean` (или предикат-функция). `ddd-tactical/specification-for-reuse` —
вводится, только когда правило применяется в ≥ 2 местах или нужна комбинация and/or/not.

```ts
// core/order/specification/eligible-for-discount.ts
export class EligibleForDiscount {
  constructor(private readonly threshold: Money) {}

  isSatisfiedBy(order: Order): boolean {
    return order.total().amount.gte(this.threshold.amount);
  }
}
```

`ddd-tactical/specification-is-not-a-query-builder` ❌ Specification для генерации SQL (это query-side). `ddd-tactical/specification-for-reuse` ❌ Specification ради одного
`if` в одном месте.

---

## 9. Module (структура папок) — `R-MOD-*`

Группировка по домену, не по типу:

```
src/
  core/
    shared/
      building-blocks.ts    # Entity, ValueObject, AggregateRoot, DomainEvent
    <bounded-context>/
      aggregate/            # AggregateRoot
      entity/               # внутренние Entity
      value-object/         # VO-классы + branded ids
      event/                # DomainEvent
      port/                 # интерфейсы + Symbol-токены (repository, внешние системы)
      service/              # Domain Service (опционально)
      specification/        # Specification (опционально)
      usecases/             # UseCase + Handler (command/query)
  adapters/
    in/http/
    out/persistence/
  app/                      # AppModule, dispatcher, конфиг
```

`ddd-tactical/packages-grouped-by-domain` — запрещено `entity/`, `service/`, `repository/` на верхнем уровне `core/` — только по Bounded
Context. `ddd-tactical/packages-grouped-by-domain` — домен (`core/<bc>/`) не импортирует `adapters/*`, `@nestjs/*`, `typeorm`,
`class-validator`. Enforce — dependency-cruiser (`depcruise --validate`) или eslint-boundaries в CI,
cross-ref `hexagonal/core-free-of-framework`, `nest-bootstrap/layout-directs-dependencies-inward`.

---

## 10. Чеклист подключения к новому сервису (Node/NestJS)

1. Entity → `Entity<ID>`, id `readonly`, `equals()` не переопределён; сравнение — `a.equals(b)`, не `===`.
2. VO → класс с `ValueObject.components()` + `Object.freeze`, инварианты в конструкторе; одно-полевые id — branded types; коллекции — копии.
3. Корни → `AggregateRoot<ID>`, события регистрируются в корне, наружу — копии.
4. События → наследуют `DomainEvent`, frozen, имя в прошедшем времени, только примитивы/VO; публикация после save через Outbox, затем `pullEvents()`.
5. Репозитории → интерфейс + Symbol-токен в `core/<bc>/port/`, возвращают домен, реализация в `adapters/out/persistence/`.
6. Ссылки между агрегатами — по id.
7. `core/` без NestJS/TypeORM-импортов (проверка dependency-cruiser/eslint-boundaries в CI).
8. Структура папок — по домену; деньги — Big.js/decimal.js, не `number`.
