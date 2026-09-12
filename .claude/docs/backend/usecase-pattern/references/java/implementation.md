# Use Case Pattern — реализация

Правила применения **Use Case Pattern** в Java-сервисах с библиотекой
[`ru.vikulinva:usecase-pattern-starter`](https://github.com/remodov/usecase-pattern)
(пакеты `ru.vikulinva.usecase` и `ru.vikulinva.usecase.cqrs`).

Этот документ — единственный источник правды для скиллов
`usecase-pattern-review` и `usecase-pattern-design`. Все правила
идентифицируются кодами (`usecase-pattern/usecase-implements-marker`, `usecase-pattern/explicit-mapper-between-layers` и т.п.) — цитируйте их в
findings.

---

## 1. Используемые абстракции

| Абстракция | Тип | Назначение |
|---|---|---|
| `UseCase<R>` | `interface` | Команда/запрос. Несёт входные данные и тип результата. |
| `UseCaseHandler<U, R>` | `interface` | Реализация одного `UseCase`. Возвращает `R`. |
| `UseCaseDispatcher` | `class` | Маршрутизация: по классу `UseCase` находит `Handler`. |
| `UseCaseStep<I, O>` | `@FunctionalInterface` | Переиспользуемая операция, выносится из Handler. |
| `UseCaseEmptyResult` / `UseCaseStepEmptyResult` | `class` | Маркер «нет результата» для команд без возврата. |
| `UseCaseCommand<R>` | `interface extends UseCase<R>` | Маркер: операция меняет состояние (CQRS). |
| `UseCaseQuery<R>` | `interface extends UseCase<R>` | Маркер: операция только читает (CQRS). |

---

## 2. Уровни внедрения

Уровень зрелости — одна ось. Этот гайд применяется начиная с **Уровня 2** (сам Use Case Pattern). Скилл определяет уровень проекта и применяет соответствующие правила. Уровень узнаётся по:

- наличию пакета `domain/` с `Entity`/`AggregateRoot` и/или `core/` + `adapter/` со строгим направлением зависимостей → Уровень 3 (DDD + Hexagonal);
- использованию `usecase-pattern` (Command/Query + Handler), без агрегатов и ports/adapters → Уровень 2; каждая операция — `UseCaseCommand` или `UseCaseQuery`, голого `UseCase` нет;
- Controller → Service → Repository без `usecase-pattern` → Уровень 1 (Слоёный), этот гайд не применяется.

| Уровень | Слои моделей | Обязательные правила |
|---|---|---|
| 1 — Слоёный (без `usecase-pattern`) | JsonBean → jOOQ Pojo | этот гайд не применяется |
| 2 — Use Case Pattern | JsonBean → Command/Query → Pojo/View | §3, §4, §5, §6, §7 |
| 3 — DDD + Hexagonal | JsonBean → Command/Query → Domain → Pojo; core/ + `*-in-adapter` / `*-out-adapter` | §3, §4, §5, §6, §7 + требования `ddd-tactical/*` + §8 |

---

## 3. UseCase

### 3.1 Обязательно

- **R-UC-1.** Класс реализует `UseCaseCommand<R>` (меняет состояние) или
  `UseCaseQuery<R>` (только читает). Голый `UseCase<R>` не используется:
  операции «ни то ни другое» не бывает.
- **R-UC-2.** Команда и запрос — Java `record` (или `final class` с финальными
  полями): **immutable data carrier**, без бизнес-логики.
- **R-UC-3.** Имя выражает бизнес-операцию и кончается маркером:
  `CreateOrderCommand`, `FindOrderByIdQuery`; handler — `CreateOrderCommandHandler`,
  `FindOrderByIdQueryHandler`. Одна запись = одна операция. Суффикс сверяется
  с маркером ArchUnit-правилом `CommandsAndQueriesAreNamedTest` (§6).
- **R-UC-4.** Параметр `R` — это тип результата, который контроллер вернёт
  клиенту: на Уровне 2 это обычно `JsonBean` или `UseCaseEmptyResult`,
  на Уровне 3 — read-модель из `core/view/` либо `<Op>Result`-record рядом
  с запросом (`CpoGetLocationsResult`), если результат нужен только ему.

### 3.2 Запрещено

- **R-UC-X1.** Логика внутри UseCase (вычисления, обращения к БД,
  валидация бизнес-правил). Только в Handler.
- **R-UC-X2.** Одна запись для нескольких операций (`OrderCommand` с признаком-переключателем,
  делающий и create, и update — разнести на два).
- **R-UC-X3.** Mutable поля или сеттеры в UseCase.
- **R-UC-X4.** Возвращать `void` — используйте `UseCaseEmptyResult` как `R`.

---

## 4. UseCaseHandler

### 4.1 Обязательно

- **R-HND-1.** Реализует `UseCaseHandler<MyCommand, R>` и метод
  `useCaseType()` возвращает `MyCommand.class`.
- **R-HND-2.** Помечен `@Component` (или эквивалентом для DI), чтобы
  Spring Boot starter подхватил его автоматически.
- **R-HND-3.** На handler команды — `@Transactional`. На handler запроса —
  `@Transactional(readOnly = true)` (на Уровне 2 и выше).
- **R-HND-4.** Один Handler — один UseCase. Не делать «универсальных»
  handler-ов на несколько UseCase.
- **R-HND-5.** Все внешние зависимости (репозитории, мапперы,
  внешние API) приходят через конструктор. **Default — `@RequiredArgsConstructor`**
  + `private final` поля (см. `java-style/boilerplate-is-generated` в `backend/java/java-style/references/implementation.md`). Явный
  `public Foo(Bar bar)`-constructor допустим только в нестандартных
  кейсах: валидация DI-аргументов в теле конструктора, вызов
  `super(...)`, нетривиальная инициализация поля.

### 4.2 Запрещено

- **R-HND-X1.** Вызывать другой `UseCaseHandler` напрямую или запускать другую
  команду/запрос через `UseCaseDispatcher` из handler'а или сервиса core.
  Операцию запускает только входящий адаптер (`R-DSP-4`); общая логика — `UseCaseStep`
  либо прикладной сервис в `core/service` (`*Saver`, `*Resolver`), который зовут
  handler'ы напрямую. В эталоне так: диспетчер — в 56 классах `adapter.in.*`, в core — нет.
- **R-HND-X2.** Бросать наружу инфраструктурные исключения
  (`SQLException`, `JOOQException`). Превращайте их в доменные
  (`OrderException.NotFound`, `PaymentException.AlreadyProcessed`).
- **R-HND-X3.** Иметь поля, изменяемые между вызовами `handle(...)` —
  Handler stateless.

---

## 5. UseCaseDispatcher и Controller

### 5.1 Обязательно

- **R-DSP-1.** Контроллер не вызывает Handler напрямую — только через
  `UseCaseDispatcher.dispatch(useCase)`.
- **R-DSP-2.** Dispatcher регистрируется через
  `usecase-pattern-starter` автоматически. Вручную создавать второй
  диспетчер — только если нужно физическое разделение (например,
  командный пул и пул запросов).
- **R-DSP-3.** Контроллер делает только: маппинг `Request → UseCase`,
  `dispatch`, маппинг `Result → Response`, выставление HTTP-кода.
- **R-DSP-4.** `UseCaseDispatcher` инжектируется **только во входящие адаптеры** —
  контроллер, `@KafkaListener`, `*Processing` планировщика (`adapter.in..`). В `core`
  диспетчера нет: handler'ы и сервисы ядра зовут друг друга как обычные бины
  (`UseCaseStep`, `core/service`), а не через операции. Держит `HandlersDoNotDependOnHandlersTest`:
  ```java
  @ArchTest
  static final ArchRule handlersDoNotDependOnHandlers = noClasses()
          .that().implement(UseCaseHandler.class)
          .should().dependOnClassesThat().implement(UseCaseHandler.class);

  @ArchTest
  static final ArchRule dispatcherOnlyInInboundAdapters = noClasses()
          .that().resideInAPackage("<root>.core..")
          .should().dependOnClassesThat().areAssignableTo(UseCaseDispatcher.class);
  ```

### 5.2 Запрещено

- **R-DSP-X1.** Бизнес-логика в контроллере (`if (...) throw new ...`,
  обращение к БД).
- **R-DSP-X2.** Передача `HttpServletRequest`/`Authentication` в UseCase —
  извлекайте `userId`/`tenantId` в контроллере и кладите в UseCase
  как обычные поля.

---

## 6. CQRS-маркеры (обязательны с Уровня 2)

### 6.1 Обязательно

- **R-CQRS-1.** Команда (меняет состояние) реализует `UseCaseCommand<R>`,
  запрос (только читает) — `UseCaseQuery<R>`. Каждая операция — одно из
  двух; операций без маркера нет.
- **R-CQRS-2.** На handler-е команды — `@Transactional` (по умолчанию
  read-write), на handler-е запроса — `@Transactional(readOnly = true)`.
- **R-CQRS-3.** Имя: команда — глагол в инфинитиве (`CreateOrder`,
  `ConfirmPayment`), запрос — `Find*` / `Get*` / `Search*`.
- **R-CQRS-4.** Чтения возвращают **Read Model**: `OrderView`,
  материализованное представление, `*View*Repository`. Запись — через
  `*Repository` с агрегатом / Pojo.
- **R-CQRS-5.** Маркер и имя держит архитектурный тест
  `CommandsAndQueriesAreNamedTest` — три правила рядом с `HexagonalArchitectureTest`:
  ```java
  @ArchTest
  static final ArchRule everyUseCaseIsCommandOrQuery = classes()
          .that().implement(UseCase.class)
          .should().implement(UseCaseCommand.class)
          .orShould().implement(UseCaseQuery.class);

  @ArchTest
  static final ArchRule commandsEndWithCommand = classes()
          .that().implement(UseCaseCommand.class)
          .should().haveSimpleNameEndingWith("Command");

  @ArchTest
  static final ArchRule queriesEndWithQuery = classes()
          .that().implement(UseCaseQuery.class)
          .should().haveSimpleNameEndingWith("Query");
  ```

### 6.2 Запрещено

- **R-CQRS-X1.** Команда возвращает большой read-DTO с подгрузкой
  связанных сущностей. Команда возвращает только то, что породила:
  идентификатор, минимальный summary или `UseCaseEmptyResult`.
- **R-CQRS-X2.** Запрос меняет состояние БД (включая «обновление last-seen»
  или «инкремент counter» в read-handler). Если действительно нужно —
  это уже команда.

---

## 7. Слои моделей

Зависит от уровня.

### 7.1 Универсальные правила

- **R-LAY-1.** На входе UseCase — только `JsonBean` (Уровень 2) или
  явные DTO/VO (Уровень 3). Не передавать сразу `Pojo` БД в UseCase.
- **R-LAY-2.** На выходе UseCase — только `JsonBean` или явный read-DTO,
  никогда — `Pojo` БД напрямую.
- **R-LAY-3.** Маппинг между слоями — **default: MapStruct**:
  `@Mapper(componentModel = "spring")` interface, при необходимости
  `default`-методы внутри интерфейса для нетривиальных конверсий
  (`@Mapping(qualifiedByName = ...)`). Hand-written `@Component`-маппер
  допустим **только** когда маппинг выражается DI-зависимыми вызовами
  или stateful-логикой, что MapStruct не покрывает. «Лень настраивать
  annotation processor» — не основание для отступления.

### 7.2 Запрещено

- **R-LAY-X1.** Использовать один и тот же класс для API-слоя и слоя БД
  (`Order order = …` приходит из БД и сразу уходит в JSON).
- **R-LAY-X2.** Циклические зависимости между мапперами.
- **R-LAY-X3.** Маппинг через рефлексию вручную (`BeanUtils.copyProperties`)
  или `ObjectMapper` в качестве «универсального маппера».

### 7.3 Уровень 3 (DDD)

- **R-LAY-DDD.** Обязательно использовать `ddd-building-blocks` и
  правила из `backend/ddd-tactical/references/java/implementation.md`. Доменные объекты
  (`AggregateRoot`, `Entity`, `ValueObject`) **не** утекают в API-слой.

---

## 8. Hexagonal (часть Уровня 3)

### 8.1 Обязательно

- **R-HEX-1.** Структура пакетов: `core/{domain,usecase,port,view,service}`
  по `hexagonal/core-structure` (без слоя bounded context'ов) и модули
  `*-in-adapter`, `*-out-adapter` (REST, Kafka, jOOQ).
- **R-HEX-2.** Зависимости направлены **внутрь**: `core/` не импортирует
  jOOQ, web, Kafka-клиент; из Spring — только whitelist `compileOnly`
  (`hexagonal/core-free-of-framework`). Плюс `usecase-pattern-starter` +
  `ddd-building-blocks`.
- **R-HEX-3.** Все внешние взаимодействия — за интерфейсами портов в
  `core/port/out/`. Реализация — в `*-out-adapter`.
- **R-HEX-4.** Один UseCase может вызываться из нескольких входных
  адаптеров (REST, Kafka-listener, scheduler). Это нормальная цель
  Уровня 3 — **не дублировать** Handler.

### 8.2 Запрещено

- **R-HEX-X1.** Прямой `JdbcTemplate`/`DSLContext` в `core/`. Только
  через порт.
- **R-HEX-X2.** Импорт `org.springframework.web.*` или
  `org.jooq.*` в `core/`.

---

## 9. UseCaseStep — переиспользование

### 9.1 Обязательно

- **R-STEP-1.** Step реализует `UseCaseStep<I, O>` и метод `execute`.
- **R-STEP-2.** Step используется, когда **одна и та же** логика
  встречается в ≥ 2 Handler-ах. Один Handler — не повод выносить Step.

### 9.2 Запрещено

- **R-STEP-X1.** Step внутри Step (вкладывать). Если хочется — это
  должно быть в Handler.
- **R-STEP-X2.** Step с состоянием. Step — stateless `@Component`.

---

## 10. Транзакции и события

- **R-TX-1.** `@Transactional` ставится на уровне `UseCaseHandler`, а не
  Repository, не Service.
- **R-TX-2.** Один UseCase = одна транзакция. Если нужна Saga — это
  оркестратор в Handler, а каждый шаг — отдельный UseCase или вызов
  внешнего сервиса с Outbox.
- **R-TX-3.** Публикация доменных событий (Уровень 3) — через
  `DomainEventPublisher` после `repository.save(...)`. После публикации
  `clearDomainEvents()` (см. backend/ddd-tactical/references/java/implementation.md).

---

## 11. Структура пакетов (опорная)

### Уровни 1–2 (плоская раскладка)

```
<root>/
  controller/
    OrderController.java
  usecase/
    order/
      CreateOrderCommand.java
      CreateOrderCommandHandler.java
      FindOrderByIdQuery.java
      FindOrderByIdQueryHandler.java
  repository/
    OrderRepository.java
    JooqOrderRepository.java
  mapper/
    OrderJsonBeanMapper.java
```

### Уровень 3

```
core/
  domain/
    aggregate/Order.java
    valueobject/Money.java
    event/OrderCreated.java
    repository/OrderRepository.java
  usecase/
    command/CreateOrderCommand.java
    command/CreateOrderCommandHandler.java
    query/FindOrderByIdQuery.java
    query/FindOrderByIdQueryHandler.java
adapter/
  in/rest/OrderController.java
  out/postgres/JooqOrderRepository.java
```

### Уровень 3 (Hexagonal-раскладка)

`core/` строго отделено от `adapter/*`, зависимости только внутрь.

---

## 12. Проектные конвенции (default-ы для генерации)

Когда скиллы (`ucp-pattern-design`, `ucp-ddd-tactical-design`, `ucp-api-design`, `ucp-test-design`) собирают новый сервис на Уровне 3 (DDD + Hexagonal) — берут эти решения по умолчанию. Команда может явно отступить, но обязана зафиксировать причину.

### 12.0 Сборка и persistence-стек (default)

| Слой | Инструмент |
|---|---|
| Сборка | **Gradle (Kotlin DSL)** + версионный каталог `gradle/libs.versions.toml` |
| Java | **21** (toolchain) — для самого сервиса и для всех публикуемых библиотек методологии |
| Spring | Spring Boot 3.x |
| Миграции БД | **Liquibase** (YAML changelog) — **не Flyway** |
| Структура миграций | `migrations/db/changelog-master.yaml` на уровне репо + `migrations/db/changelog/v-X.Y/<feature>.yaml` |
| jOOQ codegen | **`nu.studer.jooq`** Gradle-плагин, генерация после Liquibase update |
| Локальная БД для разработки | `docker-compose.yml` с `postgres:16-alpine` |
| Liquibase Gradle plugin | `org.liquibase.gradle` версия 2.2.2 + `liquibase-core 4.29.x` (стабильная связка) |

**Почему Liquibase, а не Flyway:**

- YAML-changeset читается людьми и diff-ится в PR.
- `databasechangelog` хранит метаданные применённых изменений → откат через `rollback` встроен.
- Плагин `org.liquibase.gradle` совместим с CLI-командой `update` и продакшен-Liquibase в Spring Boot.
- В команде уже есть инструменты и шаблоны под Liquibase (см. эталон bus-tickets).

### 12.1 Gradle multi-module с самого старта

Для Уровня 3 (DDD + Hexagonal) проект **сразу** разделяется на модули (один модуль на каждый порт/адаптер), чтобы ArchUnit-правила работали с первого коммита:

```
<service>/
  core/                          # @InboundPort, @OutboundPort, домен, UseCase, Handler
  adapter-in-rest/               # @InboundAdapter REST
  adapter-in-kafka/              # @InboundAdapter Kafka consumers
  adapter-out-postgres/          # @OutboundAdapter jOOQ + Outbox writer
  adapter-out-<external>/        # @OutboundAdapter HTTP-клиенты внешних систем
  bootstrap/                     # Spring Boot main + application.yml + Dockerfile
  test-utils/                    # BaseIntegrationTest, DatabasePreparer, TestObjectGenerator
```

Зависимости направлены внутрь: `bootstrap → adapter-* → core`. Adapter-модули **не зависят друг от друга** (горизонтально). `core` не зависит ни от чего, кроме `usecase-pattern-core`, `ddd-building-blocks`, `hexagonal-architecture-core` и стандартной Java.

Уровень 2 (Use Case Pattern) может оставаться single-module — multi-module не оправдан без Hexagonal.

### 12.2 OpenAPI-first

Для REST-контрактов **всегда** идём от OpenAPI:

1. Скилл `ucp-api-design` пишет/обновляет YAML в `<module>/src/main/resources/openapi/<service>.openapi.yaml`.
2. Plugin `org.openapi.generator` генерирует JsonBean DTO + интерфейсы контроллеров (`OrdersApi`) в `core/build/generated`.
3. `OrderController implements OrdersApi` в `adapter-in-rest`.

Никаких runtime аннотаций `@Operation`/`@ApiResponse` (springdoc) — спека первична. Изменение API → правка YAML → regenerate → код подхватывает.

### 12.3 Outbox-relay через `@Scheduled`-job (V1)

Outbox реализуется **внутри сервиса**:

- `adapter-out-postgres` пишет в таблицу `outbox` в той же транзакции, что и агрегат (через `DomainEventPublisher`).
- `OutboxRelayJob` в `adapter-out-kafka` (`@Scheduled(fixedDelay = ...)`), читает `outbox WHERE published_at IS NULL FOR UPDATE SKIP LOCKED`, публикует в Kafka, проставляет `published_at`.
- Не используем Debezium / Kafka Connect в V1 — лишняя инфраструктура. Переходим на CDC только при реальной необходимости (RPS > 1000 событий/сек или требование zero-lag).

Гарантия: at-least-once. Подписчики обязаны быть idempotent (`processed_events` таблица).

### 12.4 Внешние HTTP-клиенты — Resilience4j

В `adapter-out-<external>`:
- `RestTemplate` или `WebClient` (по согласию команды).
- Resilience4j: `Retry` + `CircuitBreaker` + `Timeout` + `Bulkhead` (если пул RPS заметный).
- Бросаем доменные исключения наружу (`PaymentGatewayException`, `CatalogUnavailableException`), не `RestClientException`.

### 12.5 jOOQ codegen после Liquibase

Связка:

1. `./gradlew :adapter-out-postgres:update` — Liquibase накатывает changelog на локальный Postgres из `docker-compose.yml`.
2. `./gradlew :adapter-out-postgres:generateJooq` — `nu.studer.jooq` читает живую схему и генерирует Pojo + Records в `build/generated/jooq`.
3. Композитная задача `regenerate` объединяет оба шага.

**Конвенции codegen:**

- Pojo называются `<Table>_Pojo` (PASCAL strategy с `MatcherRule.expression = "$0_Pojo"`).
- `TIMESTAMP` (без TZ) → `OffsetDateTime` через `forcedTypes`.
- Из генерации исключаются `databasechangelog` и `databasechangeloglock`.
- Сгенерированный код — в classpath модуля `adapter-out-postgres`, **не коммитится** (в `.gitignore`).

### 12.6 Тесты — см. `test-strategy.md`

Synchronous, только Postgres + WireMock, фиксация времени по варианту проекта (`fixClock` или `@MockitoBean DateTimeService`), `DatabasePreparer` + `TestObjectGenerator`. Полные правила — в [`test-strategy.md`](test-strategy.md).

---

## 13. Чек-лист обзора

1. Каждый UseCase — record/final, без логики, имя = бизнес-операция.
2. Каждый Handler — `@Component`, реализует useCaseType, помечен
   `@Transactional` (или readOnly).
3. Контроллер ходит только через `UseCaseDispatcher`.
4. Каждая операция — `UseCaseCommand` или `UseCaseQuery`, имя кончается
   на `Command` / `Query`; голого `UseCase` нет.
5. Слои моделей не смешаны. JsonBean ≠ Pojo ≠ Domain.
6. На Уровне 3 — соблюдены правила требования `ddd-tactical/*`.
7. На Уровне 3 — `core/` не импортирует jOOQ/web/Kafka-клиент; из Spring — только whitelist.
8. Step-ы используются только при реальном переиспользовании.
