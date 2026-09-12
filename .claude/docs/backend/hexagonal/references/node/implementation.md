# Hexagonal Architecture — реализация на Node (папки + dependency-cruiser)

Реализация язык-нейтрального контракта `../spec.md` (`R-HEX-*`) на Node/NestJS. Коды общие с Java и
Python; меняется **механизм изоляции**: вместо multi-module Gradle + ArchUnit — единое дерево папок со строгими
границами импортов, enforce'ится **dependency-cruiser** (или eslint-plugin-boundaries) в CI. В Node нет
compile-time изоляции модулей (npm workspaces возможны, но для одного сервиса — overkill), поэтому
import-правила в CI — не украшение, а единственный enforcement границ.

## 1. Когда переходить (`R-HEX-WHEN-*`)

`hexagonal/level-three-only` — Hexagonal = Уровень 3 (DDD + ports/adapters + import-контроль). На Уровне 1–2 — overkill.
`hexagonal/level-three-only` — пора: 2+ внешних системы, сложные инварианты/агрегаты, 3+ типа входа (REST + consumer +
scheduler), тесты требуют половину Nest-контекста. `hexagonal/level-three-only` — рано: один сервис с PG, 1-2 разработчика,
форма домена не устаканилась. `hexagonal/level-three-only` — cargo-cult (сервис из 3 эндпоинтов в полной раскладке).
`hexagonal/no-partial-adoption` — частичный Hexagonal (есть `core/`, но контроллеры мешают бизнес-логику с HTTP) — либо
полностью, либо никак.

## 2. Структура (`R-HEX-MOD-*`)

Вместо gradle-модулей — папки с контрактом dependency-cruiser. `hexagonal/module-per-part` — раскладка (cross-ref
`nest-bootstrap/layout-directs-dependencies-inward`); `hexagonal/core-free-of-framework` — `core/` не импортирует ничего инфраструктурного (ни `@nestjs/*`, ни `typeorm`,
ни `class-validator`) — даёт быстрые unit-тесты без Nest-контекста и переносимость core. `hexagonal/module-per-part` —
папка `adapters/out/<system>/` на каждую внешнюю систему; `hexagonal/module-per-part` — папка на каждый тип входа
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

`hexagonal/module-per-part` — отсутствие контракта (полагаться на дисциплину) — кто-нибудь импортнёт `typeorm` в `core/` и
никто не заметит. `hexagonal/core-free-of-framework` — `core/` импортирует `adapters/*` — стрелка всегда `app → adapters → core`.
`hexagonal/in-adapter-per-audience` — user- и admin-контроллеры в одной папке без разделения — теряется изоляция security.

## 3. Core (`R-HEX-CORE-*`)

`hexagonal/core-free-of-framework` — `core/` зависит только от TS/stdlib + доменных утилит (Big.js, uuid) — без `@nestjs/*`,
`typeorm`, `axios`, `kafkajs`. `hexagonal/core-structure` — структура `core/<bc>/`: `aggregate/`, `entity/`,
`value-object/`, `event/`, `port/` (out-порты), `usecases/` (command/query + handlers), `service/`
(см. дерево выше и `R-MOD-*`). `hexagonal/di-annotations-in-core` — **NestJS-декораторы (`@Injectable`/`@Inject`) на классах
`core/` запрещены** — авто-пикающего стартера в Node нет; handlers и domain services — plain classes,
wiring — `useFactory`-провайдеры в `app/`/feature-модулях. `hexagonal/rich-domain-model` — rich domain: логика в агрегате
(`order.confirm()`), не в `*Service` (cross-ref `ddd-tactical/aggregate-root-is-single-entry`, `ddd-tactical/node`).

```ts
// app/order.module.ts — wiring plain-handler'а без декораторов в core/
{ provide: CreateOrderHandler,
  useFactory: (orders: OrderRepository, tx: TransactionRunner, clock: Clock) =>
    new CreateOrderHandler(orders, tx, clock),
  inject: [ORDER_REPOSITORY, TX_RUNNER, CLOCK] }
```

`hexagonal/core-free-of-framework` — `@nestjs/*`-импорт в `core/` (enforce dependency-cruiser). `hexagonal/core-free-of-framework` — TypeORM-импорт
в `core/` (ORM — деталь persistence; маппинг в `adapters/out/persistence/<x>.mapper.ts`, `typeorm/explicit-mapper`).
`hexagonal/rich-domain-model` — анемичная модель. `hexagonal/no-generated-types-in-core` — TypeORM-Entity как доменный тип в `core/`.
`hexagonal/no-generated-types-in-core` — request/response-DTO (class-validator) в `core/` — деталь in-adapter.

## 4. Ports (`R-HEX-PORT-*`)

`hexagonal/outbound-port-interface-in-core` — outbound-порт = интерфейс + Symbol-токен в `core/<bc>/port/out/` (интерфейсы TS стираются в
runtime — токен обязателен для DI): `<X>Repository`, `<X>ViewRepository`, `<Y>Port`, `<Z>EventPublisher`.
`hexagonal/port-speaks-domain-types` — методы порта оперируют domain-типами, не DTO внешней системы. `hexagonal/port-exceptions-in-core` —
port-исключения объявлены в `core/` (`PaymentPortError`); подклассы (`SberError`) — в out-adapter; handler
ловит базовый. `hexagonal/inbound-port-is-use-case` — inbound-порт = UseCase + Handler (вход через `Dispatcher`), отдельный
«InboundPort» не нужен.

```ts
// core/payment/port/out/payment-port.ts
export const PAYMENT_PORT = Symbol('PaymentPort');
export interface PaymentPort {
  register(cmd: RegisterPayment): Promise<RegisterResult>;   // domain-типы, не SberRegisterRequest
  cancel(paymentId: PaymentId): Promise<void>;
}
```

`hexagonal/outbound-port-interface-in-core` — порт объявлен в out-adapter (порт — контракт core). `hexagonal/port-speaks-domain-types` — DTO внешней системы в
сигнатуре порта (адаптер мапит внутри). `hexagonal/absence-is-not-error` — `X | null` из порта, где отсутствие = ошибка (брось
доменное `OrderNotFoundError`). `hexagonal/outbound-port-interface-in-core` — порт как класс с реализацией, не интерфейс — убивает подмену
в тестах.

## 5. Adapters in (`R-HEX-AIN-*`)

`hexagonal/in-adapter-per-audience` — папка на каждый тип входа: `adapters/in/http/`, `adapters/in/http-admin/`,
`adapters/in/kafka/`, `adapters/in/cli/`. `hexagonal/controller-dispatches-only`/`hexagonal/rest-mapping-in-adapter` — контроллер маппит request-DTO
(class-validator) → UseCase, зовёт `Dispatcher`; маппер — отдельный файл (`order-request.mapper.ts`); не
возвращай domain-агрегат как HTTP-ответ. `hexagonal/adapters-do-not-know-each-other` — in-adapter знает NestJS/class-validator, не знает
про `adapters/out/*`.

`hexagonal/controller-dispatches-only` — бизнес-логика в контроллере (`if (req.amount > 100)`). `hexagonal/controller-dispatches-only` — контроллер инжектит
репозиторий напрямую (только через `Dispatcher` → Handler, cross-ref `usecase-pattern/entry-calls-dispatcher`). `hexagonal/rest-mapping-in-adapter` — контроллер
возвращает domain-агрегат наружу (маппи в response-DTO). `hexagonal/adapters-do-not-know-each-other` — `adapters/in/*` импортирует
`adapters/out/*` — адаптеры зависят от `core/`, не друг от друга.

## 6. Adapters out (`R-HEX-AOUT-*`)

`hexagonal/out-adapter-per-system` — папка `adapters/out/<system>/` на каждую внешнюю систему (per-system isolation, cross-ref
`resilience/client-per-external-system`). `hexagonal/out-adapter-per-system` — адаптер реализует порт-интерфейс из `core/` и биндится на его токен
(`{ provide: PAYMENT_PORT, useClass: SberPaymentAdapter }`, `nest-bootstrap/inject-by-port-tokens`). `hexagonal/adapter-maps-not-decides` — маппер domain ↔
DTO внешней системы в адаптере. `hexagonal/adapters-do-not-know-each-other` — адаптер знает свою инфраструктуру (`persistence/` — TypeORM;
`sber/` — axios + Sber-DTO; `kafka/` — kafkajs), не знает другие адаптеры.

`hexagonal/port-speaks-domain-types` — адаптер возвращает DTO внешней системы из порт-метода (только domain). `hexagonal/adapter-maps-not-decides` —
бизнес-логика в out-adapter (`if (sberResponse.code === 1)`); адаптер мапит, решает handler. `hexagonal/out-adapter-per-system` —
один адаптер реализует порты разных доменов. `hexagonal/adapters-do-not-know-each-other` — out-adapter инжектит другой out-adapter
(координация двух — это use case в `core/`, handler инжектит оба порта).

## 7. Composition root (`R-HEX-BOOT-*`)

`hexagonal/bootstrap-composition-only` — `app/` = composition root: `main.ts` (`NestFactory.create` + `enableShutdownHooks`),
`AppModule`, типизированный конфиг, `Dockerfile` (cross-ref `NESTBOOT-2/5/12`). `hexagonal/bootstrap-composition-only` — `AppModule`
собирает feature-модули и биндит **все** порты на адаптеры (токен → `useClass`/`useFactory`); от `app/` не
зависит никто. `hexagonal/composition-covers-all-adapters` — wiring полный: каждый порт из `core/<bc>/port/` получает провайдера в
композиции — незабинженный токен в Nest падает на старте, не на первом запросе.

`hexagonal/bootstrap-composition-only` — бизнес-логика/контроллеры в `app/` (только композиция и конфиг, `nest-bootstrap/root-module-is-composition-only`).
`hexagonal/bootstrap-composition-only` — `NestFactory.create`/wiring модулей в `core/` или `adapters/*` — только в `app/`.

## 8. Архитектурные тесты (`R-HEX-TEST-*`)

`hexagonal/architecture-tests-required`/`hexagonal/architecture-test-required-check` — `depcruise --validate .dependency-cruiser.cjs src` (или ESLint с
eslint-plugin-boundaries) запускается в CI как required check; PR не мерджится при падении. Это аналог
ArchUnit — guard на импортах: `core/` чист, адаптеры независимы, никто не зависит от `app/`.
`hexagonal/single-scan-root` — единый корень скана (`src/`) в одном конфиге, не разрозненные правила по папкам.

`hexagonal/architecture-tests-required` — только code-review для enforcement границ — человек пропустит импорт; нужен автомат в CI.

## 9. Чеклист подключения к новому сервису (Node/NestJS)

1. `core/` без `@nestjs/*`/`typeorm`/`class-validator` и без NestJS-декораторов (dependency-cruiser зелёный).
2. Стрелка зависимостей `app → adapters → core`; адаптеры не зависят друг от друга.
3. Порты — интерфейсы + Symbol-токены в `core/<bc>/port/out/`, оперируют domain-типами.
4. Контроллеры через `Dispatcher`, не репозиторий напрямую; маппинг REST-DTO ↔ command/response.
5. out-adapter реализует порт (биндинг по токену), мапит domain ↔ DTO, без бизнес-логики; per-system папки.
6. `app/` — только композиция; `main.ts`/`AppModule`/конфиг; все порты забинжены.
7. `depcruise --validate` (или eslint-boundaries) в CI как required check.
