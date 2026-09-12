# Hexagonal Architecture — реализация

Свод правил применения Hexagonal Architecture (ports & adapters) в Java/Spring-сервисах команды UCP. Каждое правило идентифицируется кодом (`hexagonal/core-free-of-framework`, `hexagonal/outbound-port-interface-in-core`) — скилл `ucp-hexagonal-review` цитирует эти коды в findings.

Hexagonal — часть **Уровня 3** (DDD + Hexagonal) в UCP (см. `R-LAY-*` в `backend/usecase-pattern/references/java/implementation.md`). Этот гайд **углубляет**: что ложится в `core/`, что в `adapter/in/*` и `adapter/out/*`, какие зависимости разрешены, как описывать ports, как работает dependency inversion, как тестировать.

Не покрывает: DDD-агрегаты как часть core/ (это `R-AGG-*`), UseCase Pattern (`R-UC-*`), persistence (`R-JOOQ-*`), специфику адаптеров (REST в `R-OAS-*`, Kafka в `R-KFK-*`).

Связанные стандарты:
- `R-LAY-*` (Use Case Pattern §2 уровни внедрения) — Уровень 3 включает Hexagonal.
- `R-AGG-*` / `R-ENT-*` / `R-VO-*` (DDD tactical) — наполнение domain-слоя в `core/`.
- Библиотека [`hexagonal-architecture`](https://github.com/remodov/hexagonal-architecture) — наша OSS-имплементация маркеров `@CoreComponent`, `@AdapterIn`, `@AdapterOut` и архитектурных тестов.

---

## Содержание

1. [Когда переходить на Hexagonal — `R-HEX-WHEN-*`](#1-когда-переходить-на-hexagonal)
2. [Структура модулей — `R-HEX-MOD-*`](#2-структура-модулей)
3. [Core слой — `R-HEX-CORE-*`](#3-core-слой)
4. [Ports — `R-HEX-PORT-*`](#4-ports)
5. [Adapters in — `R-HEX-AIN-*`](#5-adapters-in)
6. [Adapters out — `R-HEX-AOUT-*`](#6-adapters-out)
7. [Bootstrap / composition root — `R-HEX-BOOT-*`](#7-bootstrap--composition-root)
8. [Архитектурные тесты — `R-HEX-TEST-*`](#8-архитектурные-тесты)
9. [Антипаттерны — сводка `R-HEX-*-X*`](#9-антипаттерны)

---

## 1. Когда переходить на Hexagonal

Hexagonal — паттерн, добавляющий ceremony. Применяется когда выгода (testability, тех-опции, изоляция домена) перевешивает.

### 1.1 Обязательно

- **R-HEX-WHEN-1.** Hexagonal — часть **Уровня 3** (DDD + Hexagonal: агрегаты, ports/adapters, ArchUnit). На Уровне 1–2 — overkill.

- **R-HEX-WHEN-2.** Признаки, что **пора** переходить:
  - Сервис интегрируется с 2+ внешними системами (БД + платежи + Kafka).
  - Доменная логика становится сложной — бизнес-инварианты, агрегаты, события.
  - Появляются 3+ способа input (REST + scheduler + Kafka consumer + admin CLI).
  - Тесты становится трудно писать без поднятия половины Spring context.
  - Команда из 3+ разработчиков — нужна явная архитектурная граница.

- **R-HEX-WHEN-3.** Признаки, что **рано** переходить:
  - Один сервис без зависимостей кроме PG.
  - 1-2 разработчика, < 10K LOC.
  - Активно меняется бизнес-логика, форма ещё не устаканилась.
  - Нет агрегатов с инвариантами, нет богатой domain-model.

### 1.2 Запрещено

- **R-HEX-WHEN-X1.** **Hexagonal как cargo-cult** — все сервисы под него причёсаны независимо от сложности. Сервис Уровня 1 из 3 endpoints в hexagonal-раскладке = ceremony без выгоды.

- **R-HEX-WHEN-X2.** **Частичный Hexagonal** — `core/` есть, но `adapter/in/*` смешан с REST-controller'ами + бизнес-логикой. Либо полный Hexagonal, либо ничего.

---

## 2. Структура модулей

### 2.1 Обязательно

- **R-HEX-MOD-1.** Многомодульный Gradle-проект:
  ```
  <service>/
  ├── core/                          # чистый Java + DDD-библиотеки; Spring — compileOnly, только whitelist
  ├── persistence/                   # adapter/out для PG (jOOQ)
  ├── user-api-in-adapter/           # adapter/in для REST (user-facing)
  ├── admin-api-in-adapter/          # adapter/in для REST (admin)
  ├── kafka-in-adapter/              # adapter/in для Kafka consumers (если есть)
  ├── kafka-out-adapter/             # adapter/out для Kafka producers (если есть)
  ├── <system>-out-adapter/          # adapter/out для каждой внешней системы (sber, sms, etc.)
  ├── scheduler-out-adapter/         # adapter/out для @Scheduled tasks
  └── bootstrap/                     # composition root: Spring Boot Application + конфиги
  ```

- **R-HEX-MOD-2.** **`core/` — единственный модуль без инфраструктуры**. Чистый Java + Lombok + DDD-библиотеки (`ddd-building-blocks`, `usecase-pattern-starter`); Spring подключён `compileOnly` и ограничен whitelist'ом пакетов (`R-HEX-CORE-1`, тест — `R-HEX-TEST-1`). Это даёт:
  - Runtime без Spring: в jar `core/` фреймворка нет, аннотации из whitelist'а JVM игнорирует.
  - Быстрые unit-тесты агрегатов и handler'ов без Spring context.
  - Возможность переиспользовать `core/` в другой run-time (CLI, batch, Lambda).
  ```kotlin
  // core/build.gradle.kts
  dependencies {
      api(libs.usecase.pattern.starter)
      api(libs.ddd.building.blocks)
      compileOnly("org.springframework:spring-context")
      compileOnly("org.springframework:spring-tx")
      compileOnly(libs.jackson.databind)
  }
  ```

- **R-HEX-MOD-3.** **Каждый out-adapter** — отдельный gradle-модуль:
  - `persistence/` — JOOQ-репозитории, RecordDomainMappers.
  - `<system>-out-adapter/` — внешние клиенты (Sber, OdnaKassa, etc.).
  - `kafka-out-adapter/` — Kafka producers (если есть direct send для технических событий).
  - `scheduler-out-adapter/` — `@Scheduled` tasks.
  - Изоляция dependencies: `core/` не зависит от Sber-SDK или JOOQ.

- **R-HEX-MOD-4.** **Каждый in-adapter** — отдельный gradle-модуль:
  - `user-api-in-adapter/` — публичный REST.
  - `admin-api-in-adapter/` — admin REST (отдельный security профиль).
  - `kafka-in-adapter/` — Kafka consumers как entry point.
  Разделение позволяет deploy-ить с разными security-конфигами и compile-time блокировать смешение.

- **R-HEX-MOD-5.** **`bootstrap/`** — composition root: `@SpringBootApplication`, `@Configuration` для wiring beans, `application.yml`, `Dockerfile`. Зависит от `core/` + всех адаптеров. Никто не зависит от `bootstrap/`.

### 2.2 Запрещено

- **R-HEX-MOD-X1.** **Один gradle-модуль** для всего сервиса с папками `core/`, `adapter/`. Compile-time нарушения не ловятся — кто-то добавит `import org.springframework.*` в `core/` package и никто не заметит.

- **R-HEX-MOD-X2.** **`core/` зависит от `persistence/`** (или любого адаптера) в `build.gradle`. Стрелка зависимостей всегда: `bootstrap/ → core/ ← adapters`. Не наоборот.

- **R-HEX-MOD-X3.** **Все REST в одном `*-in-adapter/`** для User + Admin endpoints — теряется compile-time изоляция security-перепутывания.

---

## 3. Core слой

### 3.1 Обязательно

- **R-HEX-CORE-1.** **`core/` зависит ТОЛЬКО от:**
  - JDK + Lombok.
  - `ddd-building-blocks` (наша OSS — Entity, Aggregate, ValueObject маркеры).
  - `usecase-pattern-starter` (наша OSS — UseCase / Handler / Dispatcher).
  - `hexagonal-architecture` (наша OSS — `@CoreComponent`, `@Port`-маркеры).
  - `jakarta.validation` API (без implementation Hibernate Validator — это в bootstrap).
  - Spring — **только `compileOnly`** (`spring-context`, `spring-tx`) и **только whitelist пакетов**: `stereotype`, `transaction`, `beans.factory` (точный пакет — `ObjectProvider` да, `beans.factory.annotation` с `@Value` нет), `core.task`. На runtime-classpath core Spring отсутствует.
  - Jackson (`jackson-databind`) — `compileOnly`, только для сериализации payload'ов событий и JSON-VO; в сигнатурах портов и доменных типах — нет.
  - Сборка сообщений — в core: `*RequestBuilder` / `*PayloadBuilder` собирают DTO для внешней системы, порт `DomainEventContractMapper.toPayload(...)` отдаёт payload события. Транспорт — `KafkaTemplate`, `RestClient`, wire-модели брокера — в адаптере.
  - **Никаких** jOOQ, Kafka-клиента (`org.apache.kafka..`, `org.springframework.kafka..`), servlet, ShedLock, Logbook, Liquibase, драйвера PostgreSQL, HTTP-клиентов — это infrastructure.

- **R-HEX-CORE-2.** **Структура core/** — техническая, по роли элемента; слоя bounded context'ов внутри `core/` нет: границы контекстов живут в `docs/domain/bounded-contexts.md` и в пакетах persistence-адаптера (`adapter/out/postgres/<bc>/<entity>/`). Схема — как в эталоне partnerapi-hub:
  ```
  core/src/main/java/<pkg>/core/
  ├── domain/
  │   ├── aggregate/<X>.java              # AggregateRoot<UUID> — адрес держит ArchUnit
  │   ├── entity/<Y>.java                 # Entity<UUID> внутри агрегата — адрес держит ArchUnit
  │   ├── valueobject/<V>.java            # record'ы; enum'ы — valueobject/enumeration/
  │   ├── event/<X>Event.java             # sealed-иерархия событий агрегата
  │   ├── factory/<X>Factory.java         # статические create()
  │   └── service/                        # доменные сервисы без состояния
  ├── usecase/
  │   ├── command/<фича>/<Op>Command.java + <Op>CommandHandler.java
  │   └── query/<фича>/<Op>Query.java + <Op>QueryHandler.java   # management/ — подпакет для management-API
  ├── port/
  │   ├── in/                             # интерфейсы конфигурации и контекста вызова (R-HEX-PORT-5)
  │   └── out/                            # SelectMode, общие request-типы
  │       ├── repository/<X>Repository.java, <X>ViewRepository.java
  │       ├── filter/<X>Filter.java
  │       ├── publisher/<X>Publisher.java, <X>EventContractMapper.java
  │       └── client/<System>Client.java
  ├── view/                               # read-модели: <X>View, <X>ShortView, PaginationView
  ├── service/                            # прикладные сервисы: *Saver, *Resolver, *RequestBuilder, стратегии
  ├── exception/                          # sealed <X>Exception на агрегат
  ├── dto/                                # обменные модели — свои record'ы, не generated (hexagonal/no-generated-types-in-core)
  ├── mapper/                             # ручные мапперы между внутренними моделями
  └── util/                               # DateTimeUtil и чистые помощники
  ```
  `<фича>` — агрегат или предмет операции (`hubconnection`, `location`, `relay`, `lifecycle`). Что допустимо внутри `dto/`, `service/`, `factory/` — свои требования; здесь фиксируются имена и адреса.

- **R-HEX-CORE-3.** **`@Component` / `@Repository` / `@Transactional` / `TransactionTemplate` на классах core/** — **разрешены**: Spring подключён `compileOnly`, на runtime без него аннотации не читаются, а стартер `usecase-pattern-starter` сканирует handler'ы из готового jar. **Запрещены** `@Value`, `@Autowired` / `@Qualifier`, `@Configuration` / `@Bean`, web-, scheduling- и kafka-аннотации: конфигурация приходит через интерфейс `port/in` (`R-HEX-PORT-5`), wiring живёт в `bootstrap/`.

- **R-HEX-CORE-4.** **Domain методы — rich**: бизнес-логика **внутри** entity/aggregate (`order.confirm()`, `account.withdraw(amount)`), не в `*Service`-классах. Anemic domain — антипаттерн (`hexagonal/rich-domain-model`).

### 3.2 Запрещено

- **R-HEX-CORE-X1.** **Spring вне whitelist'а в `core/`** — `org.springframework.web..`, `..scheduling..`, `..kafka..`, `..context.annotation..`, `..beans.factory.annotation..` (`@Value`) и любой пакет, не перечисленный в тесте. Guard — правило `coreUsesOnlyWhitelistedSpringPackages` в [ArchUnit](https://www.archunit.org/) (см. `R-HEX-TEST-1`).

- **R-HEX-CORE-X2.** **JOOQ-импорт в `core/`** (`import org.jooq.*`). JOOQ — persistence-деталь, живёт в `persistence/`-модуле. Domain работает с domain-объектами; mapping POJO ↔ Domain — в `persistence/<X>DomainRecordMapper`.

- **R-HEX-CORE-X3.** **Anemic domain model** — entity без методов, только геттеры/сеттеры; вся логика в `*Service`-классах. Это процедурный стиль в DDD-обёртке.

- **R-HEX-CORE-X4.** **Generated POJO / Record (jOOQ) в `core/`** как доменный тип. POJO — internal деталь persistence; в core используется domain entity.

- **R-HEX-CORE-X5.** **HTTP / REST DTO в `core/`** (`OrderJson`, `CreateOrderRequest`). REST DTO — деталь in-adapter; в core — UseCase/Command/domain entity.

---

## 4. Ports

### 4.1 Обязательно

- **R-HEX-PORT-1.** **Outbound port — interface в `core/port/out/`** (`repository/`, `client/`, `publisher/`), описывает **что** core нужно от внешнего мира. Имя:
  - `<X>Repository` — для persistence (агрегат).
  - `<X>ViewRepository` — для read-проекции (CQRS).
  - `<Y>Port` — для других внешних систем (`PaymentPort`, `NotificationPort`, `StoragePort`).
  - `<Z>EventPublisher` — для исходящих событий (если outbox не используется).

- **R-HEX-PORT-2.** **Port-методы оперируют domain-типами**, не infrastructure-DTO:
  ```java
  public interface PaymentPort {
      RegisterResult register(RegisterCommand cmd);    // RegisterCommand — domain DTO, не SberRegisterRequest
      void cancel(Long paymentId);
  }
  ```
  Generated DTO внешней системы (`SberRegisterRequest`) — деталь out-adapter, не пробрасывается в port.

- **R-HEX-PORT-3.** **Port-исключения** в `core/`:
  ```java
  public abstract class PaymentPortException extends RuntimeException {
      protected PaymentPortException(String msg, Throwable cause) { super(msg, cause); }
  }
  ```
  Подклассы (`SberException`, `OdnaKassaException`) — в out-adapter'ах. Handler ловит `PaymentPortException`, не специфические.

- **R-HEX-PORT-4.** **Inbound port = use case** в нашей терминологии. UseCase + UseCaseHandler — это вход в core. Не нужен отдельный «InboundPort» интерфейс — `UseCaseDispatcher` уже играет роль. Интерфейсы в `core/port/in/` — конфигурация и контекст вызова (`R-HEX-PORT-5`) — не входы в core, а его требования к окружению; на них это правило не распространяется.

- **R-HEX-PORT-5.** **Конфигурация входит в core через интерфейс в `port/in`.** Всё, что core должен знать об окружении — идентичность сервиса, лимиты, имена топиков, расписания — объявляется интерфейсом в `core/port/in/`, а реализуется `@ConfigurationProperties`-record'ом в `bootstrap/`, заполненным из `application.yml` и профильных yaml. `@Value` в `core/` запрещён (вне whitelist'а `R-HEX-TEST-1`), чтение окружения — тоже.
  ```java
  // core/port/in/PlatformConfig.java
  public interface PlatformConfig {
      String countryCode();
      String partyId();
      String baseUrl();
  }

  // bootstrap/config/PlatformProperties.java
  @ConfigurationProperties(prefix = "platform")
  public record PlatformProperties(
      String countryCode,
      String partyId,
      String baseUrl
  ) implements PlatformConfig {}
  ```
  В `bootstrap/` — `@ConfigurationPropertiesScan` (или `@EnableConfigurationProperties(PlatformProperties.class)`); handler в core получает `PlatformConfig` через конструктор, unit-тест подставляет интерфейсу заглушку без контекста. Так же входит контекст вызова: `*Provider`-интерфейс в `port/in`, реализация — в security-пакете in-адаптера.

### 4.2 Запрещено

- **R-HEX-PORT-X1.** **Port в out-adapter** (`<X>Port.java` в `<system>-out-adapter/`). Port — контракт core-к-инфраструктуре, живёт в `core/`. Adapter — реализация.

- **R-HEX-PORT-X2.** **Generated DTO внешней системы в port-сигнатуре** (`PaymentPort.register(SberRequest req)`). Adapter мапит из domain в generated DTO **внутри**.

- **R-HEX-PORT-X3.** **`Optional<<EntityRef>>` в port-методе** где отсутствие значения = error. Используй throw exception с конкретным domain-meaning (`OrderNotFoundException`).

- **R-HEX-PORT-X4.** **Port-классы (не interfaces)**. Port — контракт; реализация (адаптер) подсовывается DI. Класс убивает testability.

---

## 5. Adapters in

### 5.1 Обязательно

- **R-HEX-AIN-1.** **`*-in-adapter/`-модуль на каждый тип входа**:
  - `user-api-in-adapter/` — REST для пользователя.
  - `admin-api-in-adapter/` — REST для админов (отдельный SecurityFilterChain, отдельные `@PreAuthorize`).
  - `kafka-in-adapter/` — Kafka consumers (если consumer != просто sync read-projection).
  - `cli-in-adapter/` — CLI / batch entry points.

- **R-HEX-AIN-2.** **Controller** реализует generated `<Tag>Api` (см. `rest-api/operation-id-and-tags` REST guide), маппит request DTO в `UseCase` command, dispatchит:
  ```java
  @RestController
  @RequiredArgsConstructor
  public class OrderController implements OrdersApi {

      private final UseCaseDispatcher dispatcher;
      private final OrderRequestMapper mapper;

      @Override
      public ResponseEntity<OrderJson> createOrder(@Valid CreateOrderRequest req) {
          var cmd = mapper.toCommand(req);
          var order = dispatcher.dispatch(cmd);
          return ResponseEntity.created(URI.create("/orders/" + order.getId()))
              .body(mapper.toJson(order));
      }
  }
  ```

- **R-HEX-AIN-3.** **Маппер** (`OrderRequestMapper`) — отдельный класс в `*-in-adapter/`, переводит REST-DTO ↔ Use Case command + REST-DTO ↔ domain. Не возвращай domain entity напрямую как HTTP-response.

- **R-HEX-AIN-4.** **In-adapter знает Spring + REST** (Spring Web, Jackson, Jakarta Validation), **не знает** про другие адаптеры (`persistence/`, `<system>-out-adapter/`).

### 5.2 Запрещено

- **R-HEX-AIN-X1.** **Бизнес-логика в Controller** (`if (req.amount > 100) ...`). Логика в `<Op>CommandHandler` в `core/`.

- **R-HEX-AIN-X2.** **Controller вызывает `<X>Repository` напрямую**. Только через `UseCaseDispatcher` → `<Op>Handler` → `<X>Repository`. Иначе теряется единая точка transactional / authorization.

- **R-HEX-AIN-X3.** **Controller возвращает domain entity** наружу как HTTP-response. Используй REST-DTO (generated через openapi-generator).

- **R-HEX-AIN-X4.** **`*-in-adapter/` зависит от `*-out-adapter/`** — нарушение симметрии Hexagonal. Все адаптеры зависят от `core/`, не друг от друга.

---

## 6. Adapters out

### 6.1 Обязательно

- **R-HEX-AOUT-1.** **`*-out-adapter/`-модуль на каждую внешнюю систему**:
  - `persistence/` — implements `<X>Repository` (через JOOQ, см. `jooq/repository-interface-in-domain`).
  - `<system>-out-adapter/` — implements `<Y>Port` для каждой внешней HTTP-системы.
  - `kafka-out-adapter/` — для Kafka producers (часто не нужен, если outbox-relay в `persistence/`).
  - `s3-out-adapter/`, `redis-out-adapter/` — для других internal-инфраструктур.

- **R-HEX-AOUT-2.** **Adapter implements port-интерфейс из `core/`**:
  ```java
  // <system>-out-adapter/.../SberClientAdapter.java
  @Component
  @RequiredArgsConstructor
  public class SberClientAdapter implements PaymentPort {

      private final SberOrderServicesApi sberApi;     // generated клиент
      private final SberMapper mapper;

      @Override
      public RegisterResult register(RegisterCommand cmd) {
          var apiRequest = mapper.toApi(cmd);
          var response = executeCall(sberApi.register(apiRequest, null));
          return mapper.toDomain(response);
      }
  }
  ```

- **R-HEX-AOUT-3.** **Mapper** (`SberMapper`) — отдельный класс в out-adapter, переводит между domain (port-сигнатура) и generated DTO внешней системы. См. `resilience/mapper-between-client-and-port`.

- **R-HEX-AOUT-4.** **Out-adapter знает свою инфраструктуру**: `persistence/` знает JOOQ; `sber-out-adapter/` знает Retrofit/RestClient + Sber-DTO; `kafka-out-adapter/` знает Kafka. Между собой adapter'ы **не знают**.

### 6.2 Запрещено

- **R-HEX-AOUT-X1.** **Out-adapter возвращает port-методом generated DTO** (`SberRegisterResponse`). Только domain-результат.

- **R-HEX-AOUT-X2.** **Бизнес-логика в out-adapter** (`if (sberResponse.code == 1) ... else ...`). Адаптер мапит, не решает. Решение — handler в `core/`.

- **R-HEX-AOUT-X3.** **Один out-adapter implements несколько ports** разных доменов. Per-system isolation (`resilience/client-per-external-system`).

- **R-HEX-AOUT-X4.** **Out-adapter знает другой out-adapter** (`SberAdapter` инжектит `OdnaKassaAdapter`). Координация двух адаптеров — это use case в `core/` (handler инжектит оба port'а).

---

## 7. Bootstrap / composition root

### 7.1 Обязательно

- **R-HEX-BOOT-1.** **`bootstrap/`** содержит:
  - `<App>Application.java` с `@SpringBootApplication`.
  - `application.yml` + profile-specific (`application-local.yml`, `application-prod.yml`).
  - `@Configuration`-классы для wiring beans (если требуются explicit `@Bean`-фабрики).
  - `Dockerfile` + `Helm chart` (если есть).

- **R-HEX-BOOT-2.** **Зависимости `bootstrap/build.gradle`:**
  ```kotlin
  dependencies {
      implementation(project(":core"))
      implementation(project(":persistence"))
      implementation(project(":user-api-in-adapter"))
      implementation(project(":admin-api-in-adapter"))
      implementation(project(":sber-out-adapter"))
      implementation(project(":kafka-out-adapter"))
      // ...все адаптеры
      implementation("org.springframework.boot:spring-boot-starter-web")
      implementation("org.springframework.boot:spring-boot-starter-actuator")
      implementation("org.springframework.boot:spring-boot-starter-jooq")
      // ...
  }
  ```

- **R-HEX-BOOT-3.** **`@SpringBootApplication(scanBasePackages = ...)`** или дефолтный component scan покрывает все адаптеры. Альтернатива — explicit `@Import` модулей через `@Configuration`-классы.

### 7.2 Запрещено

- **R-HEX-BOOT-X1.** **`bootstrap/` содержит бизнес-логику** или REST-контроллеры. Только композиция и configs.

- **R-HEX-BOOT-X2.** **`@SpringBootApplication` в `core/` или `*-adapter/`**. Только в `bootstrap/` — иначе невозможно собрать сервис из частей.

---

## 8. Архитектурные тесты

ArchUnit — обязательный механизм enforcement правил Hexagonal на compile-time / test-time.

### 8.1 Обязательно

- **R-HEX-TEST-1.** **ArchUnit-тесты в `bootstrap/src/test/java/`** (или отдельный модуль `architecture-tests/`) проверяют:
  - `core/` импортирует из Spring только whitelist — `stereotype`, `transaction`, `beans.factory` (точный пакет, без `annotation`), `core.task`; остальной `org.springframework..` запрещён.
  - `core/` не импортирует инфраструктуру: `org.jooq..`, `org.apache.kafka..`, `jakarta.servlet..`, `net.javacrumbs.shedlock..`, `org.zalando.logbook..`, `liquibase..`, `org.postgresql..`, HTTP-клиенты.
  - `core/` не зависит от адаптеров, `config..` bootstrap'а и сгенерированных пакетов (`generated..`, jOOQ-классы).
  - Порты в `core` (`port/in`, `port/out/**`) — только interfaces.
  - `*-out-adapter/` implements interface из портов `core`; реализации `AggregateRepository` живут только в persistence-адаптере.
  - `*-in-adapter/` не импортирует `*-out-adapter/`, и наоборот.
  - `<X>Controller implements <Tag>Api` (generated) — не handcrafted `@RequestMapping`.

  Правила whitelist'а и инфраструктуры — как в эталоне partnerapi-hub:
  ```java
  @ArchTest
  static final ArchRule coreUsesOnlyWhitelistedSpringPackages = noClasses()
          .that().resideInAPackage("<root>.core..")
          .should().dependOnClassesThat(resideInAPackage("org.springframework..")
                  .and(resideOutsideOfPackages(
                          "org.springframework.stereotype..",
                          "org.springframework.transaction..",
                          "org.springframework.beans.factory",
                          "org.springframework.core.task..")));

  @ArchTest
  static final ArchRule coreDoesNotDependOnInfrastructure = noClasses()
          .that().resideInAPackage("<root>.core..")
          .should().dependOnClassesThat().resideInAnyPackage(
                  "org.jooq..", "org.apache.kafka..", "jakarta.servlet..",
                  "net.javacrumbs.shedlock..", "org.zalando.logbook..",
                  "liquibase..", "org.postgresql..");
  ```
  `beans.factory` без `..` — точный пакет: `ObjectProvider` разрешён, `beans.factory.annotation.Value` — нет, конфигурация идёт через интерфейс (`R-HEX-PORT-5`).

  Адреса раскладки (`R-HEX-CORE-2`) держит `CoreStructureTest` — те же правила, что в эталоне:
  ```java
  @ArchTest
  static final ArchRule aggregateRootsResideInDomainAggregatePackage = classes()
          .that().areAssignableTo(AggregateRoot.class)
          .should().resideInAPackage("<root>.core.domain.aggregate");

  @ArchTest
  static final ArchRule entitiesResideInDomainEntityPackage = classes()
          .that().areAssignableTo(Entity.class).and().areNotAssignableTo(AggregateRoot.class)
          .should().resideInAPackage("<root>.core.domain.entity");

  @ArchTest
  static final ArchRule portsAreInterfaces = classes()
          .that().resideInAnyPackage("<root>.core.port.in", "<root>.core.port.out.client",
                  "<root>.core.port.out.publisher", "<root>.core.port.out.repository")
          .should().beInterfaces();
  ```

- **R-HEX-TEST-2.** **Архитектурные тесты — в CI как required check**. PR не мерджится если `archtest` падает. Это compile-time guard правил Hexagonal.

- **R-HEX-TEST-3.** **`@AnalyzeClasses(packages = "<root.package>")`** для всех тестов — единая точка скана.

### 8.2 Запрещено

- **R-HEX-TEST-X1.** **Только code-review для enforcement** Hexagonal-правил. Человек-ревьюер пропустит хотя бы один import — нужен автомат.

---

## 9. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Hexagonal как cargo-cult на Уровне 1 | `hexagonal/level-three-only` | Hexagonal как часть Уровня 3 |
| Частичный Hexagonal | `hexagonal/no-partial-adoption` | полный или ничего |
| Один gradle-модуль с папками core/adapter | `hexagonal/module-per-part` | multi-module gradle |
| `core/` зависит от persistence/ | `hexagonal/core-free-of-framework` | bootstrap → core ← adapters |
| Все REST в одном in-adapter | `hexagonal/in-adapter-per-audience` | per-purpose isolation |
| Spring вне whitelist'а или инфраструктура в core/ | `hexagonal/core-free-of-framework` | ArchUnit guard |
| `@Value` в core/ | `hexagonal/config-enters-core-via-interface` | интерфейс в `port/in` + `@ConfigurationProperties` в bootstrap/ |
| JOOQ import в core/ | `hexagonal/core-free-of-framework` | persistence/ + DomainRecordMapper |
| Anemic domain model | `hexagonal/rich-domain-model` | rich domain methods |
| Generated POJO в core | `hexagonal/no-generated-types-in-core` | mapper в persistence/ |
| HTTP DTO в core/ | `hexagonal/no-generated-types-in-core` | mapper в *-in-adapter/ |
| Port в out-adapter | `hexagonal/outbound-port-interface-in-core` | port в core/port/out/ |
| Агрегат или сущность вне `domain/aggregate` / `domain/entity`, BC-слой внутри core | `hexagonal/core-structure` | схема R-HEX-CORE-2, ArchUnit `CoreStructureTest` |
| Generated DTO в port-сигнатуре | `hexagonal/port-speaks-domain-types` | domain DTO |
| Optional где отсутствие = error | `hexagonal/absence-is-not-error` | throw exception |
| Port-классы вместо interfaces | `hexagonal/outbound-port-interface-in-core` | interfaces |
| Бизнес-логика в Controller | `hexagonal/controller-dispatches-only` | в Handler в core/ |
| Controller вызывает Repository | `hexagonal/controller-dispatches-only` | через UseCaseDispatcher |
| Controller возвращает domain | `hexagonal/rest-mapping-in-adapter` | REST-DTO |
| in-adapter зависит от out-adapter | `hexagonal/adapters-do-not-know-each-other`, `hexagonal/adapters-do-not-know-each-other` | через core/ |
| Out-adapter возвращает generated DTO | `hexagonal/port-speaks-domain-types` | domain |
| Бизнес-логика в out-adapter | `hexagonal/adapter-maps-not-decides` | в Handler |
| Один adapter implements несколько ports | `hexagonal/out-adapter-per-system` | per-system |
| bootstrap/ с бизнес-логикой | `hexagonal/bootstrap-composition-only` | только composition |
| @SpringBootApplication в core/adapter | `hexagonal/bootstrap-composition-only` | только в bootstrap/ |
| Без ArchUnit-тестов | `hexagonal/architecture-tests-required` | required CI check |

Финальная сводка: правил «Обязательно» — около 25, «Запрещено» — около 22.
