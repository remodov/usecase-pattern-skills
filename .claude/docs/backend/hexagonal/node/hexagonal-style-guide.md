# Hexagonal Architecture — Node Style Guide (папки + dependency-cruiser)

Реализация язык-нейтрального контракта `../hexagonal-rules.md` (`R-HEX-*`) на Node/NestJS. Коды общие с Java и
Python; меняется **механизм изоляции**: вместо multi-module Gradle + ArchUnit — единое дерево папок со строгими
границами импортов, enforce'ится **dependency-cruiser** (или eslint-plugin-boundaries) в CI. В Node нет
compile-time изоляции модулей (npm workspaces возможны, но для одного сервиса — overkill), поэтому
import-правила в CI — не украшение, а единственный enforcement границ.

## 1. Когда переходить (`R-HEX-WHEN-*`)

`R-HEX-WHEN-1` — Hexagonal = Уровень 3 (DDD + ports/adapters + import-контроль). На Уровне 1–2 — overkill.
`R-HEX-WHEN-2` — пора: 2+ внешних системы, сложные инварианты/агрегаты, 3+ типа входа (REST + consumer +
scheduler), тесты требуют половину Nest-контекста. `R-HEX-WHEN-3` — рано: один сервис с PG, 1-2 разработчика,
форма домена не устаканилась. `R-HEX-WHEN-X1` — cargo-cult (сервис из 3 эндпоинтов в полной раскладке).
`R-HEX-WHEN-X2` — частичный Hexagonal (есть `core/`, но контроллеры мешают бизнес-логику с HTTP) — либо
полностью, либо никак.

## 2. Структура (`R-HEX-MOD-*`)

Вместо gradle-модулей — папки с контрактом dependency-cruiser. `R-HEX-MOD-1` — раскладка (cross-ref
`NESTBOOT-15`); `R-HEX-MOD-2` — `core/` не импортирует ничего инфраструктурного (ни `@nestjs/*`, ни `typeorm`,
ни `class-validator`) — даёт быстрые unit-тесты без Nest-контекста и переносимость core. `R-HEX-MOD-3` —
папка `adapters/out/<system>/` на каждую внешнюю систему; `R-HEX-MOD-4` — папка на каждый тип входа
(`adapters/in/{http,http-admin,kafka}/` — admin отдельно от user: свой Guard/security-конфиг);
`R-HEX-MOD-5` — `app/` — composition root, от него не зависит никто.

```
src/
  core/<bc>/{aggregate,entity,value-object,event,port,usecases,service}/
  adapters/in/http/            # NestJS-контроллеры user (R-HEX-AIN)
  adapters/in/http-admin/      # admin-контроллеры (отдельный Guard)
  adapters/out/persistence/    # TypeORM (R-HEX-AOUT)
  adapters/out/<system>/       # axios/undici-клиент внешней системы (per-system)
  app/                         # composition root: main.ts, AppModule, конфиг
```

```js
// .dependency-cruiser.cjs — контракт границ
module.exports = {
  forbidden: [
    { name: 'core-pure', severity: 'error',
      from: { path: '^src/core' },
      to: { path: '^(src/(adapters|app)|node_modules/(@nestjs|typeorm|class-validator))' } },
    { name: 'adapters-independent', severity: 'error',
      from: { path: '^src/adapters/in' }, to: { path: '^src/adapters/out' } },
    { name: 'nobody-depends-on-app', severity: 'error',
      from: { path: '^src/(core|adapters)' }, to: { path: '^src/app' } },
  ],
};
```

`R-HEX-MOD-X1` — отсутствие контракта (полагаться на дисциплину) — кто-нибудь импортнёт `typeorm` в `core/` и
никто не заметит. `R-HEX-MOD-X2` — `core/` импортирует `adapters/*` — стрелка всегда `app → adapters → core`.
`R-HEX-MOD-X3` — user- и admin-контроллеры в одной папке без разделения — теряется изоляция security.

## 3. Core (`R-HEX-CORE-*`)

`R-HEX-CORE-1` — `core/` зависит только от TS/stdlib + доменных утилит (Big.js, uuid) — без `@nestjs/*`,
`typeorm`, `axios`, `kafkajs`. `R-HEX-CORE-2` — структура `core/<bc>/`: `aggregate/`, `entity/`,
`value-object/`, `event/`, `port/` (out-порты), `usecases/` (command/query + handlers), `service/`
(см. дерево выше и `R-MOD-*`). `R-HEX-CORE-3` — **NestJS-декораторы (`@Injectable`/`@Inject`) на классах
`core/` запрещены** — авто-пикающего стартера в Node нет; handlers и domain services — plain classes,
wiring — `useFactory`-провайдеры в `app/`/feature-модулях. `R-HEX-CORE-4` — rich domain: логика в агрегате
(`order.confirm()`), не в `*Service` (cross-ref `R-AGG-2`, `ddd-tactical/node`).

```ts
// app/order.module.ts — wiring plain-handler'а без декораторов в core/
{ provide: CreateOrderHandler,
  useFactory: (orders: OrderRepository, tx: TransactionRunner, clock: Clock) =>
    new CreateOrderHandler(orders, tx, clock),
  inject: [ORDER_REPOSITORY, TX_RUNNER, CLOCK] }
```

`R-HEX-CORE-X1` — `@nestjs/*`-импорт в `core/` (enforce dependency-cruiser). `R-HEX-CORE-X2` — TypeORM-импорт
в `core/` (ORM — деталь persistence; маппинг в `adapters/out/persistence/<x>.mapper.ts`, `R-TYPEORM-MAP-1`).
`R-HEX-CORE-X3` — анемичная модель. `R-HEX-CORE-X4` — TypeORM-Entity как доменный тип в `core/`.
`R-HEX-CORE-X5` — request/response-DTO (class-validator) в `core/` — деталь in-adapter.

## 4. Ports (`R-HEX-PORT-*`)

`R-HEX-PORT-1` — outbound-порт = интерфейс + Symbol-токен в `core/<bc>/port/out/` (интерфейсы TS стираются в
runtime — токен обязателен для DI): `<X>Repository`, `<X>ViewRepository`, `<Y>Port`, `<Z>EventPublisher`.
`R-HEX-PORT-2` — методы порта оперируют domain-типами, не DTO внешней системы. `R-HEX-PORT-3` —
port-исключения объявлены в `core/` (`PaymentPortError`); подклассы (`SberError`) — в out-adapter; handler
ловит базовый. `R-HEX-PORT-4` — inbound-порт = UseCase + Handler (вход через `Dispatcher`), отдельный
«InboundPort» не нужен.

```ts
// core/payment/port/out/payment-port.ts
export const PAYMENT_PORT = Symbol('PaymentPort');
export interface PaymentPort {
  register(cmd: RegisterPayment): Promise<RegisterResult>;   // domain-типы, не SberRegisterRequest
  cancel(paymentId: PaymentId): Promise<void>;
}
```

`R-HEX-PORT-X1` — порт объявлен в out-adapter (порт — контракт core). `R-HEX-PORT-X2` — DTO внешней системы в
сигнатуре порта (адаптер мапит внутри). `R-HEX-PORT-X3` — `X | null` из порта, где отсутствие = ошибка (брось
доменное `OrderNotFoundError`). `R-HEX-PORT-X4` — порт как класс с реализацией, не интерфейс — убивает подмену
в тестах.

## 5. Adapters in (`R-HEX-AIN-*`)

`R-HEX-AIN-1` — папка на каждый тип входа: `adapters/in/http/`, `adapters/in/http-admin/`,
`adapters/in/kafka/`, `adapters/in/cli/`. `R-HEX-AIN-2`/`R-HEX-AIN-3` — контроллер маппит request-DTO
(class-validator) → UseCase, зовёт `Dispatcher`; маппер — отдельный файл (`order-request.mapper.ts`); не
возвращай domain-агрегат как HTTP-ответ. `R-HEX-AIN-4` — in-adapter знает NestJS/class-validator, не знает
про `adapters/out/*`.

`R-HEX-AIN-X1` — бизнес-логика в контроллере (`if (req.amount > 100)`). `R-HEX-AIN-X2` — контроллер инжектит
репозиторий напрямую (только через `Dispatcher` → Handler, cross-ref `R-DSP-1`). `R-HEX-AIN-X3` — контроллер
возвращает domain-агрегат наружу (маппи в response-DTO). `R-HEX-AIN-X4` — `adapters/in/*` импортирует
`adapters/out/*` — адаптеры зависят от `core/`, не друг от друга.

## 6. Adapters out (`R-HEX-AOUT-*`)

`R-HEX-AOUT-1` — папка `adapters/out/<system>/` на каждую внешнюю систему (per-system isolation, cross-ref
`R-RES-ISO-1`). `R-HEX-AOUT-2` — адаптер реализует порт-интерфейс из `core/` и биндится на его токен
(`{ provide: PAYMENT_PORT, useClass: SberPaymentAdapter }`, `NESTBOOT-6`). `R-HEX-AOUT-3` — маппер domain ↔
DTO внешней системы в адаптере. `R-HEX-AOUT-4` — адаптер знает свою инфраструктуру (`persistence/` — TypeORM;
`sber/` — axios + Sber-DTO; `kafka/` — kafkajs), не знает другие адаптеры.

`R-HEX-AOUT-X1` — адаптер возвращает DTO внешней системы из порт-метода (только domain). `R-HEX-AOUT-X2` —
бизнес-логика в out-adapter (`if (sberResponse.code === 1)`); адаптер мапит, решает handler. `R-HEX-AOUT-X3` —
один адаптер реализует порты разных доменов. `R-HEX-AOUT-X4` — out-adapter инжектит другой out-adapter
(координация двух — это use case в `core/`, handler инжектит оба порта).

## 7. Composition root (`R-HEX-BOOT-*`)

`R-HEX-BOOT-1` — `app/` = composition root: `main.ts` (`NestFactory.create` + `enableShutdownHooks`),
`AppModule`, типизированный конфиг, `Dockerfile` (cross-ref `NESTBOOT-2/5/12`). `R-HEX-BOOT-2` — `AppModule`
собирает feature-модули и биндит **все** порты на адаптеры (токен → `useClass`/`useFactory`); от `app/` не
зависит никто. `R-HEX-BOOT-3` — wiring полный: каждый порт из `core/<bc>/port/` получает провайдера в
композиции — незабинженный токен в Nest падает на старте, не на первом запросе.

`R-HEX-BOOT-X1` — бизнес-логика/контроллеры в `app/` (только композиция и конфиг, `NESTBOOT-X2`).
`R-HEX-BOOT-X2` — `NestFactory.create`/wiring модулей в `core/` или `adapters/*` — только в `app/`.

## 8. Архитектурные тесты (`R-HEX-TEST-*`)

`R-HEX-TEST-1`/`R-HEX-TEST-2` — `depcruise --validate .dependency-cruiser.cjs src` (или ESLint с
eslint-plugin-boundaries) запускается в CI как required check; PR не мерджится при падении. Это аналог
ArchUnit — guard на импортах: `core/` чист, адаптеры независимы, никто не зависит от `app/`.
`R-HEX-TEST-3` — единый корень скана (`src/`) в одном конфиге, не разрозненные правила по папкам.

`R-HEX-TEST-X1` — только code-review для enforcement границ — человек пропустит импорт; нужен автомат в CI.

## 9. Чеклист подключения к новому сервису (Node/NestJS)

1. `core/` без `@nestjs/*`/`typeorm`/`class-validator` и без NestJS-декораторов (dependency-cruiser зелёный).
2. Стрелка зависимостей `app → adapters → core`; адаптеры не зависят друг от друга.
3. Порты — интерфейсы + Symbol-токены в `core/<bc>/port/out/`, оперируют domain-типами.
4. Контроллеры через `Dispatcher`, не репозиторий напрямую; маппинг REST-DTO ↔ command/response.
5. out-adapter реализует порт (биндинг по токену), мапит domain ↔ DTO, без бизнес-логики; per-system папки.
6. `app/` — только композиция; `main.ts`/`AppModule`/конфиг; все порты забинжены.
7. `depcruise --validate` (или eslint-boundaries) в CI как required check.
