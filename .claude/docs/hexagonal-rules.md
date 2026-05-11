# Hexagonal Architecture — индекс правил

> **Что это.** Сжатый индекс правил `hexagonal-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами, code-блоками, обоснованием и под-пунктами — `hexagonal-style-guide.md`**; открывай её точечно по
> нужному разделу, когда индекса не хватает (под-списки и code-сниппеты сюда не вынесены).
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

## 1. Когда переходить на Hexagonal
**MUST:**
- **R-HEX-WHEN-1.** Hexagonal обязателен на **Tier C** (DDD-сервисы) и **Tier D** (event-sourced / CQRS+). Tier A/B — overkill.
- **R-HEX-WHEN-2.** Признаки, что **пора** переходить:
- **R-HEX-WHEN-3.** Признаки, что **рано** переходить:
**MUST NOT:**
- **R-HEX-WHEN-X1.** **Hexagonal как cargo-cult** — все сервисы под него причёсаны независимо от сложности. Tier A-сервис из 3 endpoints в hexagonal-раскладке = ceremony без выгоды.
- **R-HEX-WHEN-X2.** **Частичный Hexagonal** — `core/` есть, но `adapter/in/*` смешан с REST-controller'ами + бизнес-логикой. Либо полный Hexagonal, либо ничего.

## 2. Структура модулей
**MUST:**
- **R-HEX-MOD-1.** Многомодульный Gradle-проект:
- **R-HEX-MOD-2.** **`core/` — единственный модуль без Spring**. Чистый Java + Lombok + DDD-библиотеки (`ddd-building-blocks`, `usecase-pattern`). Это даёт:
- **R-HEX-MOD-3.** **Каждый out-adapter** — отдельный gradle-модуль:
- **R-HEX-MOD-4.** **Каждый in-adapter** — отдельный gradle-модуль:
- **R-HEX-MOD-5.** **`bootstrap/`** — composition root: `@SpringBootApplication`, `@Configuration` для wiring beans, `application.yml`, `Dockerfile`. Зависит от `core/` + всех адаптеров. Никто не зависит от `bootstrap/`.
**MUST NOT:**
- **R-HEX-MOD-X1.** **Один gradle-модуль** для всего сервиса с папками `core/`, `adapter/`. Compile-time нарушения не ловятся — кто-то добавит `import org.springframework.*` в `core/` package и никто не заметит.
- **R-HEX-MOD-X2.** **`core/` зависит от `persistence/`** (или любого адаптера) в `build.gradle`. Стрелка зависимостей всегда: `bootstrap/ → core/ ← adapters`. Не наоборот.
- **R-HEX-MOD-X3.** **Все REST в одном `*-in-adapter/`** для User + Admin endpoints — теряется compile-time изоляция security-перепутывания.

## 3. Core слой
**MUST:**
- **R-HEX-CORE-1.** **`core/` зависит ТОЛЬКО от:**
- **R-HEX-CORE-2.** **Структура core/:**
- **R-HEX-CORE-3.** **`@Component` / `@Service` / `@Repository` на классах core/** — **разрешены** только если использовать стартер `usecase-pattern-starter`, который автоматически их пикает. В этом случае Spring **не компилирует** core, а просто сканирует beans из uber-jar. Альтернатива — голые POJO + явные `@Bean`-фабрики в `bootstrap/`.
- **R-HEX-CORE-4.** **Domain методы — rich**: бизнес-логика **внутри** entity/aggregate (`order.confirm()`, `account.withdraw(amount)`), не в `*Service`-классах. Anemic domain — антипаттерн (`R-HEX-CORE-X3`).
**MUST NOT:**
- **R-HEX-CORE-X1.** **Spring-импорт в `core/`** (`import org.springframework.*`). Compile-time guard через [ArchUnit](https://www.archunit.org/) — обязательный архитектурный тест (см. `R-HEX-TEST-*`).
- **R-HEX-CORE-X2.** **JOOQ-импорт в `core/`** (`import org.jooq.*`). JOOQ — persistence-деталь, живёт в `persistence/`-модуле. Domain работает с domain-объектами; mapping POJO ↔ Domain — в `persistence/<X>DomainRecordMapper`.
- **R-HEX-CORE-X3.** **Anemic domain model** — entity без методов, только геттеры/сеттеры; вся логика в `*Service`-классах. Это процедурный стиль в DDD-обёртке.
- **R-HEX-CORE-X4.** **Generated POJO / Record (jOOQ) в `core/`** как доменный тип. POJO — internal деталь persistence; в core используется domain entity.
- **R-HEX-CORE-X5.** **HTTP / REST DTO в `core/`** (`OrderJson`, `CreateOrderRequest`). REST DTO — деталь in-adapter; в core — UseCase/Command/domain entity.

## 4. Ports
**MUST:**
- **R-HEX-PORT-1.** **Outbound port — interface в `core/<bc>/port/out/`**, описывает **что** core нужно от внешнего мира. Имя:
- **R-HEX-PORT-2.** **Port-методы оперируют domain-типами**, не infrastructure-DTO: Generated DTO внешней системы (`SberRegisterRequest`) — деталь out-adapter, не пробрасывается в port.
- **R-HEX-PORT-3.** **Port-исключения** в `core/`: Подклассы (`SberException`, `OdnaKassaException`) — в out-adapter'ах. Handler ловит `PaymentPortException`, не специфические.
- **R-HEX-PORT-4.** **Inbound port = use case** в нашей терминологии. UseCase + UseCaseHandler — это вход в core. Не нужен отдельный «InboundPort» интерфейс — `UseCaseDispatcher` уже играет роль.
**MUST NOT:**
- **R-HEX-PORT-X1.** **Port в out-adapter** (`<X>Port.java` в `<system>-out-adapter/`). Port — контракт core-к-инфраструктуре, живёт в `core/`. Adapter — реализация.
- **R-HEX-PORT-X2.** **Generated DTO внешней системы в port-сигнатуре** (`PaymentPort.register(SberRequest req)`). Adapter мапит из domain в generated DTO **внутри**.
- **R-HEX-PORT-X3.** **`Optional<<EntityRef>>` в port-методе** где отсутствие значения = error. Используй throw exception с конкретным domain-meaning (`OrderNotFoundException`).
- **R-HEX-PORT-X4.** **Port-классы (не interfaces)**. Port — контракт; реализация (адаптер) подсовывается DI. Класс убивает testability.

## 5. Adapters in
**MUST:**
- **R-HEX-AIN-1.** **`*-in-adapter/`-модуль на каждый тип входа**:
- **R-HEX-AIN-2.** **Controller** реализует generated `<Tag>Api` (см. `R-OAS-1` REST guide), маппит request DTO в `UseCase` command, dispatchит:
- **R-HEX-AIN-3.** **Маппер** (`OrderRequestMapper`) — отдельный класс в `*-in-adapter/`, переводит REST-DTO ↔ Use Case command + REST-DTO ↔ domain. Не возвращай domain entity напрямую как HTTP-response.
- **R-HEX-AIN-4.** **In-adapter знает Spring + REST** (Spring Web, Jackson, Jakarta Validation), **не знает** про другие адаптеры (`persistence/`, `<system>-out-adapter/`).
**MUST NOT:**
- **R-HEX-AIN-X1.** **Бизнес-логика в Controller** (`if (req.amount > 100) ...`). Логика в `<Op>CommandHandler` в `core/`.
- **R-HEX-AIN-X2.** **Controller вызывает `<X>Repository` напрямую**. Только через `UseCaseDispatcher` → `<Op>Handler` → `<X>Repository`. Иначе теряется единая точка transactional / authorization.
- **R-HEX-AIN-X3.** **Controller возвращает domain entity** наружу как HTTP-response. Используй REST-DTO (generated через openapi-generator).
- **R-HEX-AIN-X4.** **`*-in-adapter/` зависит от `*-out-adapter/`** — нарушение симметрии Hexagonal. Все адаптеры зависят от `core/`, не друг от друга.

## 6. Adapters out
**MUST:**
- **R-HEX-AOUT-1.** **`*-out-adapter/`-модуль на каждую внешнюю систему**:
- **R-HEX-AOUT-2.** **Adapter implements port-интерфейс из `core/`**:
- **R-HEX-AOUT-3.** **Mapper** (`SberMapper`) — отдельный класс в out-adapter, переводит между domain (port-сигнатура) и generated DTO внешней системы. См. `R-RES-OAS-4`.
- **R-HEX-AOUT-4.** **Out-adapter знает свою инфраструктуру**: `persistence/` знает JOOQ; `sber-out-adapter/` знает Retrofit/RestClient + Sber-DTO; `kafka-out-adapter/` знает Kafka. Между собой adapter'ы **не знают**.
**MUST NOT:**
- **R-HEX-AOUT-X1.** **Out-adapter возвращает port-методом generated DTO** (`SberRegisterResponse`). Только domain-результат.
- **R-HEX-AOUT-X2.** **Бизнес-логика в out-adapter** (`if (sberResponse.code == 1) ... else ...`). Адаптер мапит, не решает. Решение — handler в `core/`.
- **R-HEX-AOUT-X3.** **Один out-adapter implements несколько ports** разных доменов. Per-system isolation (`R-RES-ISO-1`).
- **R-HEX-AOUT-X4.** **Out-adapter знает другой out-adapter** (`SberAdapter` инжектит `OdnaKassaAdapter`). Координация двух адаптеров — это use case в `core/` (handler инжектит оба port'а).

## 7. Bootstrap / composition root
**MUST:**
- **R-HEX-BOOT-1.** **`bootstrap/`** содержит:
- **R-HEX-BOOT-2.** **Зависимости `bootstrap/build.gradle`:**
- **R-HEX-BOOT-3.** **`@SpringBootApplication(scanBasePackages = ...)`** или дефолтный component scan покрывает все адаптеры. Альтернатива — explicit `@Import` модулей через `@Configuration`-классы.
**MUST NOT:**
- **R-HEX-BOOT-X1.** **`bootstrap/` содержит бизнес-логику** или REST-контроллеры. Только композиция и configs.
- **R-HEX-BOOT-X2.** **`@SpringBootApplication` в `core/` или `*-adapter/`**. Только в `bootstrap/` — иначе невозможно собрать сервис из частей.

## 8. Архитектурные тесты
**MUST:**
- **R-HEX-TEST-1.** **ArchUnit-тесты в `bootstrap/src/test/java/`** (или отдельный модуль `architecture-tests/`) проверяют:
- **R-HEX-TEST-2.** **Архитектурные тесты — в CI как required check**. PR не мерджится если `archtest` падает. Это compile-time guard правил Hexagonal.
- **R-HEX-TEST-3.** **`@AnalyzeClasses(packages = "<root.package>")`** для всех тестов — единая точка скана.
**MUST NOT:**
- **R-HEX-TEST-X1.** **Только code-review для enforcement** Hexagonal-правил. Человек-ревьюер пропустит хотя бы один import — нужен автомат.

## 9. Антипаттерны
