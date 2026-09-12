# Use Case Pattern — реализация на Node (NestJS / TypeScript)

Реализация язык-нейтрального контракта `../spec.md` (`R-UC-*`/`R-HND-*`/`R-DSP-*`/`R-CQRS-*`/`R-LAY-*`/`R-HEX-*`/`R-STEP-*`/`R-TX-*`) на Node/NestJS. Коды — общие с Java и Python; здесь — как они выглядят без библиотеки `usecase-pattern` (её роль играют лёгкие интерфейсы + dispatcher-реестр на DI NestJS).

Структура UCP: `core/` (UseCase + Domain + порты-интерфейсы, без NestJS/TypeORM), `adapters/in/http/` (NestJS-контроллеры), `adapters/out/` (TypeORM-репозитории, HTTP-клиенты), `app/` (AppModule, dispatcher, конфиг) — cross-ref `nest-bootstrap/layout-directs-dependencies-inward`.

---

## 1. UseCase — `R-UC-*`

`usecase-pattern/usecase-implements-marker` / `usecase-pattern/usecase-is-immutable-carrier` — UseCase = класс (или `Readonly`-объект) с `readonly`-полями, immutable data carrier без логики. Маркеры команды/запроса — базовые дженерик-интерфейсы:

```ts
// core/usecase.ts
export interface Command<R> { readonly __result?: R }   // меняет состояние
export interface Query<R> { readonly __result?: R }     // только читает

// core/order/usecases/create-order.ts
export class CreateOrder implements Command<OrderId> {
  constructor(
    readonly customerId: string,
    readonly items: ReadonlyArray<OrderItemInput>,
  ) {}
}
```

Фантомное поле `__result?` фиксирует `R` в типе (TypeScript стирает дженерики в runtime); диспатч в runtime идёт по конструктору класса.

`usecase-pattern/one-usecase-one-operation` — имя по бизнес-операции (`CreateOrder`, `FindOrderById`), один UseCase = одна операция.
`usecase-pattern/explicit-result-type` — `R` — тип результата для контроллера (read-DTO / id / явный empty-маркер). Для «ничего» — `EmptyResult`-тип, не голый `void` (`usecase-pattern/explicit-result-type`).

`usecase-pattern/usecase-is-immutable-carrier` ❌ логика в UseCase (вычисления, запросы к БД). `usecase-pattern/one-usecase-one-operation` ❌ один класс на create+update. `usecase-pattern/usecase-is-immutable-carrier` ❌ мутабельные поля/сеттеры — все поля `readonly`, коллекции `ReadonlyArray`.

---

## 2. Handler — `R-HND-*`

`usecase-pattern/one-handler-one-usecase` — Handler реализует интерфейс `Handler<UC, R>` с единственным `execute(uc): Promise<R>`:

```ts
// core/usecase.ts
export interface Handler<UC, R> {
  execute(useCase: UC): Promise<R>;
}

// core/order/handlers/create-order.handler.ts
@Injectable()
export class CreateOrderHandler implements Handler<CreateOrder, OrderId> {
  constructor(
    @Inject(ORDER_REPOSITORY) private readonly orders: OrderRepository,   // R-HND-5
    @Inject(TX_RUNNER) private readonly tx: TransactionRunner,
    @Inject(CLOCK) private readonly clock: Clock,
  ) {}

  async execute(uc: CreateOrder): Promise<OrderId> {        // R-HND-3: граница TX — здесь
    return this.tx.run(async () => {
      const order = Order.create(uc.customerId, uc.items, this.clock.now());
      await this.orders.save(order);
      return order.id;
    });
  }
}
```

`usecase-pattern/handler-registered-in-container` — Handler — провайдер NestJS (`@Injectable` + регистрация в feature-модуле), чтобы dispatcher нашёл его. На Уровне 3 (Hexagonal) `core/` без NestJS-декораторов — Handler остаётся plain class и регистрируется `useFactory` в `app/` (см. `hexagonal/di-annotations-in-core` в `../../hexagonal/references/node/implementation.md`).
`usecase-pattern/transaction-boundary-on-handler` — граница транзакции на Handler: команда — `dataSource.transaction(...)` / transactional-обёртка, запрос — без транзакции (cross-ref `R-TYPEORM-TX-1/3`). `usecase-pattern/one-handler-one-usecase` — один Handler — один UseCase. `usecase-pattern/handler-is-stateless` — зависимости через конструктор по DI-токенам портов (`nest-bootstrap/inject-by-port-tokens`), поля `private readonly`.

`usecase-pattern/handlers-do-not-call-handlers` ❌ Handler инжектит и зовёт другой Handler — через Dispatcher / Step. `usecase-pattern/infrastructure-errors-become-domain` ❌ наружу летит `QueryFailedError`/axios-ошибка — мапить в доменную (cross-ref `R-ERR-WHERE-2b`, `error-handling/node`). `usecase-pattern/handler-is-stateless` ❌ поля, накапливающие состояние между `execute` — Handler stateless (singleton-scope по умолчанию это подразумевает).

---

## 3. Dispatcher и контроллер — `R-DSP-*`

`usecase-pattern/entry-calls-dispatcher` / `usecase-pattern/single-dispatcher` — контроллер не зовёт Handler напрямую, только через `Dispatcher`. Лёгкий реестр «конструктор UseCase → Handler»:

```ts
// app/dispatcher.ts
export class Dispatcher {
  constructor(private readonly registry: Map<Function, Handler<unknown, unknown>>) {}

  async dispatch<R>(useCase: Command<R> | Query<R>): Promise<R> {
    const handler = this.registry.get(useCase.constructor);
    if (!handler) throw new TechnicalError(`no handler for ${useCase.constructor.name}`);
    return handler.execute(useCase) as Promise<R>;
  }
}
```

Реестр собирается в композиции (`app/` — провайдер-фабрика, перечисляющая пары `[CreateOrder, CreateOrderHandler]`; вариант — `DiscoveryService` по metadata-декоратору). Один dispatcher на приложение; второй — только при физическом разделении пулов команд/запросов.

`usecase-pattern/controller-maps-and-dispatches` — контроллер делает только маппинг Request→UseCase, dispatch, маппинг Result→Response, HTTP-код:

```ts
// adapters/in/http/order.controller.ts
@Controller('v1/orders')
export class OrderController {
  constructor(private readonly dispatcher: Dispatcher) {}

  @Post()
  @HttpCode(201)
  async create(@Body() req: CreateOrderRequest, @Principal() principal: AuthPrincipal): Promise<CreateOrderResponse> {
    const orderId = await this.dispatcher.dispatch(
      new CreateOrder(principal.userId, toDomainItems(req.items)));   // R-DSP-X2: userId из principal, не из Request
    return { id: String(orderId) };
  }
}
```

`usecase-pattern/controller-maps-and-dispatches` ❌ бизнес-логика/обращение к БД в контроллере. `usecase-pattern/no-transport-objects-in-usecase` ❌ передавать `Request`/`ExecutionContext`/principal-объект в UseCase — извлекать `userId`/`tenantId` в контроллере и класть обычными полями.

---

## 4. CQRS — `R-CQRS-*`

`usecase-pattern/command-versus-query`/`usecase-pattern/command-versus-query` — команда реализует `Command<R>` (имя-глагол `CreateOrder`), запрос — `Query<R>` (`FindOrderById`/`SearchOrders`).
`usecase-pattern/transaction-boundary-on-handler` — команда: внутри `tx.run(...)` (read-write); запрос: без транзакции, через ViewRepository (cross-ref `typeorm/transaction-on-handler`).
`usecase-pattern/reads-via-read-model` — чтения возвращают read-DTO/view (`OrderView`), запись — через `OrderRepository` с агрегатом. Углубление — `../../cqrs/references/node/implementation.md`.

`usecase-pattern/command-returns-minimum` ❌ команда возвращает тяжёлый read-DTO со связями — только id/summary. `usecase-pattern/query-does-not-mutate` ❌ запрос пишет (last-seen/counter) — это команда.

---

## 5. Слои моделей — `R-LAY-*`

`usecase-pattern/layer-models-do-not-leak` — на входе UseCase — поля из request-DTO (class-validator) или явные VO, не TypeORM-Entity. `usecase-pattern/layer-models-do-not-leak` — на выходе — read-DTO/VO, не Entity (`typeorm/repository-speaks-domain-types`).
`usecase-pattern/explicit-mapper-between-layers` — маппинг — явные функции/мапперы (`toDomainItems(req.items)`, `OrderViewMapper.fromRow(row)`); не один класс на все слои.

```ts
// adapters/in/http/dto/create-order.request.ts — DTO API-слоя, class-validator
export class CreateOrderRequest {
  @IsArray() @ValidateNested({ each: true }) @Type(() => OrderItemDto)
  items!: OrderItemDto[];
}
```

`usecase-pattern/layer-models-do-not-leak` ❌ один класс для API и БД (`@Entity` с `@IsString` уходит в JSON-ответ). `usecase-pattern/no-cyclic-mappers` ❌ циклические зависимости мапперов. `usecase-pattern/explicit-mapper-between-layers` ❌ «универсальный» маппинг через `Object.assign`/spread/`plainToInstance` Entity→domain (cross-ref `typeorm/explicit-mapper`). `usecase-pattern/layer-models-do-not-leak` — доменные объекты (Aggregate/Entity/VO из `core/`) не утекают в API-слой (cross-ref `../../ddd-tactical/references/node/implementation.md`).

---

## 6. Hexagonal (Уровень 3) — `R-HEX-*`

`hexagonal/module-per-part` — `core/<bc>/` (usecases + domain + `port/`), `adapters/in/http`, `adapters/out/{persistence,payment}`, `app/`.
`hexagonal/core-free-of-framework` — `core/` импортирует только TS/stdlib + доменные типы; **не** `@nestjs/*`/`typeorm`/`axios`. Enforce — dependency-cruiser или eslint-boundaries (ArchUnit-аналог).
`hexagonal/outbound-port-interface-in-core` — внешнее — за портами-интерфейсами в `core/<bc>/port/` + DI-токен:

```ts
// core/order/port/order-repository.ts
export const ORDER_REPOSITORY = Symbol('OrderRepository');
export interface OrderRepository {
  save(order: Order): Promise<void>;
  byId(id: OrderId): Promise<Order | null>;
}
```

`usecase-pattern/one-usecase-many-inbound-adapters` — один UseCase из нескольких входных адаптеров (HTTP-контроллер, Kafka-consumer, scheduler) — Handler не дублировать.

`hexagonal/outbound-port-interface-in-core` ❌ `DataSource`/`createQueryBuilder` в `core/` (`typeorm/port-in-core-implementation-in-adapter`). `hexagonal/core-free-of-framework` ❌ `import { ... } from '@nestjs/common'` / `'typeorm'` в `core/`. Полный гайд — `../../hexagonal/references/node/implementation.md`.

---

## 7. Step — `R-STEP-*`

`usecase-pattern/step-for-reuse-only` — Step — stateless класс с `execute(input: I): Promise<O>`, инжектится в Handler-ы как провайдер. `usecase-pattern/step-for-reuse-only` — вводить, когда логика в ≥ 2 Handler-ах; один Handler — не повод.
`usecase-pattern/steps-flat-and-stateless` ❌ Step внутри Step. `usecase-pattern/steps-flat-and-stateless` ❌ Step с состоянием.

---

## 8. Транзакции и события — `R-TX-*`

`usecase-pattern/transaction-boundary-on-handler` — граница транзакции — на Handler через `TransactionRunner`-порт (обёртка `dataSource.transaction` или `typeorm-transactional` CLS-hooked), не на репозитории; репозитории внутри работают через транзакционный `EntityManager` (cross-ref `R-TYPEORM-TX-1/2`):

```ts
// adapters/out/persistence/typeorm-transaction.runner.ts
@Injectable()
export class TypeOrmTransactionRunner implements TransactionRunner {
  constructor(private readonly dataSource: DataSource) {}
  run<T>(work: () => Promise<T>): Promise<T> {
    return this.dataSource.transaction(() => work());   // em — в CLS-контекст для репозиториев
  }
}
```

`usecase-pattern/one-usecase-one-transaction` — один UseCase = одна транзакция; Saga — оркестратор в Handler, шаги — отдельные UseCase / внешние вызовы с Outbox (cross-ref `distributed`).
`usecase-pattern/publish-events-after-save` — доменные события (Уровень 3) — публикация после `repository.save(...)` внутри той же транзакции (Outbox), затем `aggregate.pullEvents()` очищает их (cross-ref `../../ddd-tactical/references/node/implementation.md` `ddd-tactical/events-published-after-save`).

---

## Чеклист подключения к новому сервису (Node/NestJS)

- [ ] `core/usecase.ts`: интерфейсы `Command<R>`/`Query<R>`/`Handler<UC, R>`
- [ ] UseCase — класс с `readonly`-полями (`ReadonlyArray` для коллекций), имя-операция, без логики
- [ ] Handler — один `execute()`, deps через конструктор по DI-токенам портов, граница TX через `TransactionRunner`
- [ ] `Dispatcher` (Map конструктор→handler), контроллер зовёт только его
- [ ] Контроллер тонкий: class-validator Request → UseCase → dispatch → Response; `userId` из principal, не из Request
- [ ] DTO на edge, домен в `core/`, TypeORM-Entity в `adapters/out/persistence/`; явный маппинг, без `plainToInstance`-as-mapper
- [ ] Порты — интерфейсы + Symbol-токены в `core/<bc>/port/`; `core/` без `@nestjs/*`/`typeorm` (enforce dependency-cruiser/eslint-boundaries)
- [ ] CQRS: команда в транзакции + id/summary; запрос без транзакции + ViewRepository + read-DTO
- [ ] Инфра-ошибки (TypeORM/axios) мапятся в доменные в адаптере (cross-ref `error-handling/node`)
- [ ] Feature-модуль регистрирует handlers, `app/` собирает dispatcher (`NESTBOOT-5/6`)
