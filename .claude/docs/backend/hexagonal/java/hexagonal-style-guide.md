# Hexagonal Architecture Style Guide

Свод правил применения Hexagonal Architecture (ports & adapters) в Java/Spring-сервисах команды UCP. Каждое правило идентифицируется кодом (`R-HEX-CORE-1`, `R-HEX-PORT-X1`) — скилл `ucp-hexagonal-review` цитирует эти коды в findings.

Hexagonal — часть **Уровня 3** (DDD + Hexagonal) в UCP (см. `R-LAY-*` в `usecase-pattern-style-guide.md`). Этот гайд **углубляет**: что ложится в `core/`, что в `adapter/in/*` и `adapter/out/*`, какие зависимости разрешены, как описывать ports, как работает dependency inversion, как тестировать.

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
  ├── core/                          # Pure Java/Kotlin, без Spring
  ├── persistence/                   # adapter/out для PG (jOOQ)
  ├── user-api-in-adapter/           # adapter/in для REST (user-facing)
  ├── admin-api-in-adapter/          # adapter/in для REST (admin)
  ├── kafka-in-adapter/              # adapter/in для Kafka consumers (если есть)
  ├── kafka-out-adapter/             # adapter/out для Kafka producers (если есть)
  ├── <system>-out-adapter/          # adapter/out для каждой внешней системы (sber, sms, etc.)
  ├── scheduler-out-adapter/         # adapter/out для @Scheduled tasks
  └── bootstrap/                     # composition root: Spring Boot Application + конфиги
  ```

- **R-HEX-MOD-2.** **`core/` — единственный модуль без Spring**. Чистый Java + Lombok + DDD-библиотеки (`ddd-building-blocks`, `usecase-pattern`). Это даёт:
  - Compile-time guarantee: `core/` нельзя загрязнить Spring-аннотациями случайно.
  - Быстрые unit-тесты без Spring context.
  - Возможность переиспользовать `core/` в другой run-time (CLI, batch, Lambda).

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
  - `usecase-pattern` (наша OSS — UseCase / Handler / Dispatcher).
  - `hexagonal-architecture` (наша OSS — `@CoreComponent`, `@Port`-маркеры).
  - `jakarta.validation` API (без implementation Hibernate Validator — это в bootstrap).
  - **Никаких** Spring, JOOQ, Jackson, OkHttp, Kafka — это infrastructure.

- **R-HEX-CORE-2.** **Структура core/:**
  ```
  core/src/main/java/<pkg>/
  ├── domain/                         # DDD-tactical: aggregates, entities, VO, events
  │   ├── <bc>/                       # Bounded Context
  │   │   ├── aggregate/<X>.java
  │   │   ├── entity/<Y>.java
  │   │   ├── valueobject/<V>.java
  │   │   ├── event/<X>Event.java
  │   │   └── exception/<X>DomainException.java
  │   └── port/out/                   # outbound port-интерфейсы (см. R-HEX-PORT-*)
  │       ├── <X>Repository.java       # для persistence
  │       ├── <Y>Port.java             # для других внешних систем
  │       └── <Z>EventPublisher.java   # для исходящих событий
  ├── usecase/
  │   ├── command/<Op>Command.java + <Op>CommandHandler.java
  │   └── query/<Op>Query.java + <Op>QueryHandler.java
  ├── dto/                            # внутренние application DTO (records preferred)
  └── service/                        # shared business services без явного UseCase
  ```

- **R-HEX-CORE-3.** **`@Component` / `@Service` / `@Repository` на классах core/** — **разрешены** только если использовать стартер `usecase-pattern-starter`, который автоматически их пикает. В этом случае Spring **не компилирует** core, а просто сканирует beans из uber-jar. Альтернатива — голые POJO + явные `@Bean`-фабрики в `bootstrap/`.

- **R-HEX-CORE-4.** **Domain методы — rich**: бизнес-логика **внутри** entity/aggregate (`order.confirm()`, `account.withdraw(amount)`), не в `*Service`-классах. Anemic domain — антипаттерн (`R-HEX-CORE-X3`).

### 3.2 Запрещено

- **R-HEX-CORE-X1.** **Spring-импорт в `core/`** (`import org.springframework.*`). Compile-time guard через [ArchUnit](https://www.archunit.org/) — обязательный архитектурный тест (см. `R-HEX-TEST-*`).

- **R-HEX-CORE-X2.** **JOOQ-импорт в `core/`** (`import org.jooq.*`). JOOQ — persistence-деталь, живёт в `persistence/`-модуле. Domain работает с domain-объектами; mapping POJO ↔ Domain — в `persistence/<X>DomainRecordMapper`.

- **R-HEX-CORE-X3.** **Anemic domain model** — entity без методов, только геттеры/сеттеры; вся логика в `*Service`-классах. Это процедурный стиль в DDD-обёртке.

- **R-HEX-CORE-X4.** **Generated POJO / Record (jOOQ) в `core/`** как доменный тип. POJO — internal деталь persistence; в core используется domain entity.

- **R-HEX-CORE-X5.** **HTTP / REST DTO в `core/`** (`OrderJson`, `CreateOrderRequest`). REST DTO — деталь in-adapter; в core — UseCase/Command/domain entity.

---

## 4. Ports

### 4.1 Обязательно

- **R-HEX-PORT-1.** **Outbound port — interface в `core/<bc>/port/out/`**, описывает **что** core нужно от внешнего мира. Имя:
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

- **R-HEX-PORT-4.** **Inbound port = use case** в нашей терминологии. UseCase + UseCaseHandler — это вход в core. Не нужен отдельный «InboundPort» интерфейс — `UseCaseDispatcher` уже играет роль.

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

- **R-HEX-AIN-2.** **Controller** реализует generated `<Tag>Api` (см. `R-OAS-1` REST guide), маппит request DTO в `UseCase` command, dispatchит:
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
  - `persistence/` — implements `<X>Repository` (через JOOQ, см. `R-JOOQ-REPO-1`).
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

- **R-HEX-AOUT-3.** **Mapper** (`SberMapper`) — отдельный класс в out-adapter, переводит между domain (port-сигнатура) и generated DTO внешней системы. См. `R-RES-OAS-4`.

- **R-HEX-AOUT-4.** **Out-adapter знает свою инфраструктуру**: `persistence/` знает JOOQ; `sber-out-adapter/` знает Retrofit/RestClient + Sber-DTO; `kafka-out-adapter/` знает Kafka. Между собой adapter'ы **не знают**.

### 6.2 Запрещено

- **R-HEX-AOUT-X1.** **Out-adapter возвращает port-методом generated DTO** (`SberRegisterResponse`). Только domain-результат.

- **R-HEX-AOUT-X2.** **Бизнес-логика в out-adapter** (`if (sberResponse.code == 1) ... else ...`). Адаптер мапит, не решает. Решение — handler в `core/`.

- **R-HEX-AOUT-X3.** **Один out-adapter implements несколько ports** разных доменов. Per-system isolation (`R-RES-ISO-1`).

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
  - `core/` не импортирует Spring (`org.springframework.*`).
  - `core/` не импортирует JOOQ (`org.jooq.*`), Jackson, OkHttp, Retrofit, Kafka.
  - `core/<bc>/port/out/*` содержит только interfaces.
  - `*-out-adapter/` implements interface из `core/<bc>/port/out/`.
  - `*-in-adapter/` не импортирует `*-out-adapter/`.
  - `<X>Controller implements <Tag>Api` (generated) — не handcrafted `@RequestMapping`.

  Пример теста:
  ```java
  @Test
  void coreShouldNotDependOnSpring() {
      noClasses().that().resideInAPackage("..core..")
          .should().dependOnClassesThat().resideInAPackage("org.springframework..")
          .check(allClasses);
  }
  ```

- **R-HEX-TEST-2.** **Архитектурные тесты — в CI как required check**. PR не мерджится если `archtest` падает. Это compile-time guard правил Hexagonal.

- **R-HEX-TEST-3.** **`@AnalyzeClasses(packages = "<root.package>")`** для всех тестов — единая точка скана.

### 8.2 Запрещено

- **R-HEX-TEST-X1.** **Только code-review для enforcement** Hexagonal-правил. Человек-ревьюер пропустит хотя бы один import — нужен автомат.

---

## 9. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Hexagonal как cargo-cult на Уровне 1 | `R-HEX-WHEN-X1` | Hexagonal как часть Уровня 3 |
| Частичный Hexagonal | `R-HEX-WHEN-X2` | полный или ничего |
| Один gradle-модуль с папками core/adapter | `R-HEX-MOD-X1` | multi-module gradle |
| `core/` зависит от persistence/ | `R-HEX-MOD-X2` | bootstrap → core ← adapters |
| Все REST в одном in-adapter | `R-HEX-MOD-X3` | per-purpose isolation |
| Spring import в core/ | `R-HEX-CORE-X1` | ArchUnit guard |
| JOOQ import в core/ | `R-HEX-CORE-X2` | persistence/ + DomainRecordMapper |
| Anemic domain model | `R-HEX-CORE-X3` | rich domain methods |
| Generated POJO в core | `R-HEX-CORE-X4` | mapper в persistence/ |
| HTTP DTO в core/ | `R-HEX-CORE-X5` | mapper в *-in-adapter/ |
| Port в out-adapter | `R-HEX-PORT-X1` | port в core/<bc>/port/out/ |
| Generated DTO в port-сигнатуре | `R-HEX-PORT-X2` | domain DTO |
| Optional где отсутствие = error | `R-HEX-PORT-X3` | throw exception |
| Port-классы вместо interfaces | `R-HEX-PORT-X4` | interfaces |
| Бизнес-логика в Controller | `R-HEX-AIN-X1` | в Handler в core/ |
| Controller вызывает Repository | `R-HEX-AIN-X2` | через UseCaseDispatcher |
| Controller возвращает domain | `R-HEX-AIN-X3` | REST-DTO |
| in-adapter зависит от out-adapter | `R-HEX-AIN-X4`, `R-HEX-AOUT-X4` | через core/ |
| Out-adapter возвращает generated DTO | `R-HEX-AOUT-X1` | domain |
| Бизнес-логика в out-adapter | `R-HEX-AOUT-X2` | в Handler |
| Один adapter implements несколько ports | `R-HEX-AOUT-X3` | per-system |
| bootstrap/ с бизнес-логикой | `R-HEX-BOOT-X1` | только composition |
| @SpringBootApplication в core/adapter | `R-HEX-BOOT-X2` | только в bootstrap/ |
| Без ArchUnit-тестов | `R-HEX-TEST-X1` | required CI check |

Финальная сводка: правил «Обязательно» — около 25, «Запрещено» — около 22.
