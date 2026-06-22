# DDD Tactical Patterns — Node Style Guide (чистый TypeScript в `core/`)

Реализация язык-нейтрального контракта `../ddd-tactical-rules.md` (`R-ENT/VO/AGG/EVT/REP/DS/FAC/SPEC/MOD-*`)
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

`R-ENT-1` — сущность наследует `Entity<ID>` (или живёт внутри агрегата). `R-ENT-2`/`R-ENT-3` — идентификатор
задаётся в конструкторе и неизменяем (`readonly id`, без сеттера). `R-ENT-4` — equality по id через базовый
`equals()`, **не переопределять** в наследниках; сравнение `a === b` для сущностей из разных загрузок всегда
false — использовать `a.equals(b)`. `R-ENT-5` — конструктор валидирует инварианты; невалидная сущность не
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

`R-ENT-X1` ❌ переопределять `equals` в наследниках. `R-ENT-X2` ❌ сравнивать сущности по полям
(`JSON.stringify(a) === JSON.stringify(b)` / lodash `isEqual` — это VO-семантика). `R-ENT-X3` ❌ публичные
мутабельные поля / сеттеры на всё (`order.status = ...`) — состояние меняется бизнес-методами
(`order.confirm()`), поля `private`. `R-ENT-X4` ❌ ссылка на другой агрегат объектом — только по id
(`customerId: CustomerId`). `R-ENT-X5` ❌ анемичная модель (interface с полями + логика в сервисах).

> Не делай Entity plain-интерфейсом/type — TypeScript структурно типизирован, два разных «Entity» с одинаковой
> формой взаимозаменяемы для компилятора. Класс + identity-equality из базового `Entity` фиксируют семантику.

---

## 2. Value Object — `R-VO-*`

`R-VO-1`/`R-VO-2` — VO — класс, наследующий `ValueObject`, все поля `readonly` (для защиты в runtime —
`Object.freeze(this)` в конструкторе). `R-VO-3` — `equals()` сравнивает **все** значимые поля — базовый класс
делает это через `components()`. `R-VO-4` — инварианты в конструкторе. `R-VO-5` — мутирующая операция
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

`R-VO-X1` ❌ id или жизненный цикл у VO. `R-VO-X2` ❌ primitive obsession: `string email` → `Email`,
`number amount` → `Money` (деньги — **Big.js/decimal.js поверх string из БД, никогда `number`**, cross-ref
`R-TYPEORM-ENT-2`). `R-VO-X3` ❌ мутабельный массив в VO — `ReadonlyArray` + копия в конструкторе
(`readonly`-модификатор TS не защищает в runtime; `Object.freeze` — защищает сам объект, но не вложенные).

---

## 3. Aggregate Root — `R-AGG-*`

`R-AGG-1` — корень наследует `AggregateRoot<ID>`. `R-AGG-2` — внешние операции только через методы корня;
внутренние Entity наружу — копией (`[...this.lines]`) или `ReadonlyArray`. `R-AGG-3` — события регистрируются
в момент изменения состояния через `this.registerEvent(...)`, не в репозитории. `R-AGG-4` — один use case
меняет один агрегат; на другие влияем событиями. `R-AGG-5` — ссылки на другие агрегаты по id.

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

`R-AGG-X1` ❌ «God aggregate». `R-AGG-X2` ❌ `return this.orderLines` без копии — `ReadonlyArray` в сигнатуре
не мешает вызвавшему сделать `(lines as OrderLine[]).push(...)`; отдавать копию. `R-AGG-X3` ❌ менять чужой
агрегат напрямую. `R-AGG-X4` ❌ регистрировать события вне корня (в Handler/репозитории/контроллере).

---

## 4. Domain Event — `R-EVT-*`

`R-EVT-1` — событие наследует `DomainEvent` (несёт `eventId`/`occurredAt`/`aggregateId`). `R-EVT-2` — имя
глаголом в прошедшем времени (`OrderConfirmed`, не `ConfirmOrder`/`OrderEvent`). `R-EVT-3` — иммутабельно:
все поля `readonly`, `Object.freeze(this)` в конструкторе. `R-EVT-4` — несёт бизнес-контекст значениями
(id, `total`, `confirmedAt`), не сам агрегат. `R-EVT-5` — события собираются в агрегате и публикуются после
`repository.save(...)` — в Outbox **в той же транзакции**; затем `aggregate.pullEvents()` очищает накопленное
(cross-ref `R-TX-3`, `usecase-pattern/node`).

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

`R-EVT-X1` ❌ менять поля события после создания. `R-EVT-X2` ❌ ссылка на агрегат/Entity в событии — только
примитивы и VO. `R-EVT-X3` ❌ публиковать из контроллера/Handler — только корень регистрирует. `R-EVT-X4` ❌
критичные эффекты «после commit» фоном (`EventEmitter2`-listener после ответа — теряется при падении
процесса) — Outbox в той же транзакции (cross-ref `R-TYPEORM-TX-*`).

---

## 5. Repository — `R-REP-*`

`R-REP-1` — порт репозитория — интерфейс + Symbol-токен в `core/<bc>/port/`, типизирован агрегатом.
`R-REP-2` — реализация в `adapters/out/persistence/` (cross-ref `R-TYPEORM-REPO-1`); домен не знает про
TypeORM. `R-REP-3` — один репозиторий = один корень. `R-REP-4` — `save` сохраняет агрегат целиком в одной
транзакции; публикация событий + `pullEvents()` — на границе транзакции Handler-а. `R-REP-5` — методы в
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

`R-REP-X1` ❌ возвращать TypeORM-Entity/raw row наружу (cross-ref `R-TYPEORM-REPO-X1`); маппинг Entity ↔
domain — явный маппер (`R-TYPEORM-MAP-1`). `R-REP-X2` ❌ методы под одну таблицу (`updateStatusInDb`).
`R-REP-X3` ❌ Specification, генерирующая SQL, в репозитории — для чтений отдельный ViewRepository
(cross-ref `R-CQRS-4`, `R-TYPEORM-QRY-4`).

---

## 6. Domain Service — `R-DS-*`

`R-DS-1` — Domain Service только если логика касается ≥ 2 агрегатов и не лезет в один корень. `R-DS-2` —
stateless plain class (без `@Injectable` — он в `core/`), принимает доменные объекты (не DTO/репозитории).
`R-DS-3` — имя — доменная операция.

```ts
// core/transfer/service/transfer.service.ts
export class TransferService {
  transfer(src: Account, dst: Account, amount: Money): void {
    src.withdraw(amount);
    dst.deposit(amount);
  }
}
```

`R-DS-X1` ❌ оркестрация (загрузка из репозитория, транзакции, публикация) в Domain Service — это Handler.
`R-DS-X2` ❌ Domain Service как свалка, оставляющая агрегаты анемичными.

---

## 7. Factory — `R-FAC-*`

`R-FAC-1` — фабрика (static-метод / отдельная функция) только когда конструктор не справляется (сборка из
частей, валидация по другому агрегату, выбор подтипа). `R-FAC-2` — возвращает уже валидный агрегат с
начальными событиями.

```ts
// core/order/aggregate/order.ts
static create(customerId: CustomerId, now: Date, ids: IdGenerator): Order {
  const order = new Order(OrderId(ids.next()), customerId);
  order.registerEvent(new OrderCreated(uuidv7(), now, order.id, customerId));
  return order;
}
```

`R-FAC-X1` ❌ Factory ради Factory — если хватает `new Order(...)`, не плодить слой.

---

## 8. Specification — `R-SPEC-*`

`R-SPEC-1` — спецификация — класс с `isSatisfiedBy(candidate): boolean` (или предикат-функция). `R-SPEC-2` —
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

`R-SPEC-X1` ❌ Specification для генерации SQL (это query-side). `R-SPEC-X2` ❌ Specification ради одного
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

`R-MOD-1` — запрещено `entity/`, `service/`, `repository/` на верхнем уровне `core/` — только по Bounded
Context. `R-MOD-2` — домен (`core/<bc>/`) не импортирует `adapters/*`, `@nestjs/*`, `typeorm`,
`class-validator`. Enforce — dependency-cruiser (`depcruise --validate`) или eslint-boundaries в CI,
cross-ref `R-HEX-2`, `NESTBOOT-15`.

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
