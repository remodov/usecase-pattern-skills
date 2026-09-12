---
name: ucp-hexagonal-review
description: Ревью Hexagonal Architecture Java/Spring-сервиса (требования hexagonal/*) — multi-module gradle структура, чистота core по whitelist'у, ports в core/port, маппинг в adapters in/out, bootstrap только композиция, ArchUnit-тесты.
when_to_use: Ревью многомодульного Hexagonal-сервиса — core/, *-in-adapter, *-out-adapter, bootstrap, build-файлы.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Hexagonal Architecture

Ты ревьюишь Hexagonal-структуру Java/Spring-сервиса на соответствие требованиям `hexagonal/*`. Главные точки контроля: чистота core/, правильное направление зависимостей (`bootstrap → core ← adapters`), naming и расположение ports, маппинг между слоями, ArchUnit-тесты.

## Зависимости

- **`.claude/docs/backend/hexagonal/spec.md`** — индекс всех правил (полный текст — `references/<lang>/implementation.md`). Подгруппы: `R-HEX-WHEN-*` (когда), `R-HEX-MOD-*` (модули), `R-HEX-CORE-*` (core), `R-HEX-PORT-*` (ports), `R-HEX-AIN-*` (adapters in), `R-HEX-AOUT-*` (adapters out), `R-HEX-BOOT-*` (bootstrap), `R-HEX-TEST-*` (архитектурные тесты).
- Парные: `backend/usecase-pattern/spec.md` (`R-LAY-*` — Уровень 3), `backend/ddd-tactical/spec.md` (`R-AGG-*` для core), `backend/java/jooq/spec.md` (`R-JOOQ-REPO-*`), `backend/rest-api/spec.md` (`R-OAS-*` для in-adapter).

## Инструкции

0. **Проверь, что гейты, обещанные требованиями, включены.** Поле **Гейт** в `spec.md` называет механизм — убедись, что он есть в проекте: ArchUnit-тесты в `bootstrap/src/test/**` (или модуле `architecture-tests/`) и джоба `archtest` в CI. Обещанный, но не включённый гейт — **отдельная находка**, и она важнее отдельного нарушения: без него граница держится только на внимательности.
   Требования с гейтом `ревью` (богатый домен, адаптер мапит а не решает, раздельные in-adapter'ы по аудиториям) не поймает никто, кроме тебя — смотри их внимательнее остальных.

1. **Прочти** `.claude/docs/backend/hexagonal/spec.md`. Цитируй коды (`hexagonal/core-free-of-framework`, `hexagonal/port-speaks-domain-types`).

2. **Определи объект ревью.** Если пользователь назвал — бери. Иначе:
   - `git diff` на любые файлы в `core/`, `*-in-adapter/`, `*-out-adapter/`, `bootstrap/`.
   - `settings.gradle.kts` / `build.gradle.kts` с `include`-ами модулей.
   - ArchUnit-тесты в `bootstrap/src/test/java/` или `architecture-tests/`.
   - `<App>Application.java` и `@Configuration`-классы в bootstrap.

3. **Прогон по подгруппам:**
   - **`R-HEX-WHEN-*`** — Уровень 3 оправдан (Hexagonal — часть Уровня 3), Уровень 1–2 — overkill. Признаки готовности: 2+ внешних систем, агрегаты, 3+ типа input.
   - **`R-HEX-MOD-*`** — multi-module, core/ без инфраструктуры (Spring — compileOnly, по whitelist'у), per-system out-adapters, per-purpose in-adapters, bootstrap composition root.
   - **`R-HEX-CORE-*`** — core зависит ТОЛЬКО от JDK + Lombok + ddd-building-blocks + usecase-pattern-starter + jakarta.validation API + Spring `compileOnly` по whitelist'у (`stereotype`, `transaction`, `beans.factory`, `core.task`) + Jackson `compileOnly` для payload'ов; rich domain methods не anemic; generated POJO не используется как domain.
   - **`R-HEX-PORT-*`** — port-interfaces в core/port/out/{repository,client,publisher}/, агрегаты в core/domain/aggregate, сущности в core/domain/entity (ArchUnit `CoreStructureTest`); сигнатуры с domain-типами; `<X>PortException` базовый в core, конкретные в adapters; UseCase = inbound port.
   - **`R-HEX-AIN-*`** — Controller implements generated `<Tag>Api`; маппит REST-DTO ↔ Command через mapper; диспатчит через UseCaseDispatcher; не зависит от out-adapter; не возвращает domain entity наружу.
   - **`R-HEX-AOUT-*`** — implements port из core; mapper для generated DTO ↔ domain; не возвращает generated DTO; не содержит бизнес-логику; не один adapter под несколько ports разных доменов.
   - **`R-HEX-BOOT-*`** — bootstrap только composition + configs; @SpringBootApplication только тут.
   - **`R-HEX-TEST-*`** — ArchUnit-тесты обязательны: core импортирует из Spring только whitelist и не импортит jOOQ/Kafka-клиент/servlet/etc, port в правильном пакете, adapter implements port, in-adapter не зависит от out-adapter.

4. **Ищи паттерны-нарушения:**
   - Один gradle-модуль с `core/` подпапкой и `adapter/` подпапкой — `hexagonal/module-per-part`.
   - В `core/build.gradle.kts` зависимость `implementation(project(":persistence"))` или подобная — `hexagonal/core-free-of-framework` критическое.
   - В `core/` импорт Spring вне whitelist'а — `web`, `scheduling`, `kafka` (транспорт; сборка сообщений в core — норма), `context.annotation`, `beans.factory.annotation` (`@Value`) — `hexagonal/core-free-of-framework` критическое; `@Component` / `@Transactional` / `TransactionTemplate` — норма (`hexagonal/di-annotations-in-core`), `@Value` — `hexagonal/config-enters-core-via-interface`.
   - В `core/` `import org.jooq.*` — `hexagonal/core-free-of-framework` критическое.
   - В `core/` инжектирован `UseCaseDispatcher` — `usecase-pattern/handlers-do-not-call-handlers` критическое: операции запускают только входящие адаптеры.
   - В `core/` `import com.fasterxml.jackson.*` вне сериализации payload'ов (события, JSON-VO) — `hexagonal/core-free-of-framework` замечание; `compileOnly` для payload'ов допустим.
   - В `core/` Entity без методов, только `@Getter @Setter`, вся логика в `*Service` — `hexagonal/rich-domain-model` (anemic).
   - В `core/` использование `OrdersPojo` (generated jOOQ) как тип агрегата — `hexagonal/no-generated-types-in-core`.
   - В `core/` использование `OrderJson` / `CreateOrderRequest` (REST-DTO) как тип — `hexagonal/no-generated-types-in-core`.
   - Port-interface (`<X>Port`) находится в `<system>-out-adapter/` а не в `core/port/out/` — `hexagonal/outbound-port-interface-in-core` критическое.
   - В `core/` слой `<bc>/` над `domain/` или `usecase/`, агрегат вне `domain/aggregate/`, сущность вне `domain/entity/` — `hexagonal/core-structure`.
   - `PaymentPort.register(SberRegisterRequest req)` (generated DTO в port-сигнатуре) — `hexagonal/port-speaks-domain-types`.
   - `PaymentPort.find(Long id) → Optional<Payment>` где отсутствие — error → `hexagonal/absence-is-not-error`.
   - `class <X>Port { ... }` (class вместо interface) — `hexagonal/outbound-port-interface-in-core`.
   - Controller с `if (req.amount > X) throw ...` (бизнес-логика) — `hexagonal/controller-dispatches-only`.
   - Controller инжектит `<X>Repository` напрямую и вызывает методы — `hexagonal/controller-dispatches-only`.
   - Controller возвращает `Order` (агрегат) или `OrderItem` наружу — `hexagonal/rest-mapping-in-adapter`.
   - В `*-in-adapter/build.gradle.kts` `implementation(project(":sber-out-adapter"))` — `hexagonal/adapters-do-not-know-each-other` / `hexagonal/adapters-do-not-know-each-other` критическое.
   - Out-adapter port-метод возвращает `SberRegisterResponse` (generated) — `hexagonal/port-speaks-domain-types`.
   - `if (sberResponse.code == 1) ... else ...` логика в адаптере — `hexagonal/adapter-maps-not-decides`.
   - `class XAdapter implements PaymentPort, NotificationPort` (несколько ports разных доменов) — `hexagonal/out-adapter-per-system`.
   - Out-adapter инжектит другой out-adapter — `hexagonal/adapters-do-not-know-each-other`.
   - В `bootstrap/` REST-controller или handler — `hexagonal/bootstrap-composition-only`.
   - `@SpringBootApplication` в `core/` или `*-adapter/` — `hexagonal/bootstrap-composition-only`.
   - **Отсутствие ArchUnit-тестов** в проекте — `hexagonal/architecture-tests-required` критическое.

5. **При ревью settings.gradle.kts:**
   - Перечислены все ожидаемые модули: `core`, `persistence`, `*-in-adapter`, `*-out-adapter`, `bootstrap`.

6. **При ревью build.gradle.kts модулей:**
   - `core/build.gradle.kts` — Spring только `compileOnly` (`spring-context`, `spring-tx`); никаких `implementation`-зависимостей на `org.springframework`, `org.jooq`, project-зависимостей на adapters.
   - `*-out-adapter/build.gradle.kts` — `implementation(project(":core"))`, не `:persistence` или другой adapter.
   - `*-in-adapter/build.gradle.kts` — `implementation(project(":core"))`, не другой adapter.
   - `bootstrap/build.gradle.kts` — `implementation(project(":core"))` + все adapters.

7. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md`.

8. **Доменные ориентиры серьёзности:**
   - **Критично:**
     - jOOQ/Kafka-клиент/web import в core или Spring вне whitelist'а — нарушает фундамент Hexagonal.
     - core зависит от persistence/ или другого adapter — направление зависимостей сломано.
     - Port-interface вне core/ — теряется dependency inversion.
     - in-adapter зависит от out-adapter — нарушение симметрии.
     - Отсутствие ArchUnit-тестов — без enforcement правила гарантированно нарушаются за месяцы.
   - **Предупреждение:**
     - Один gradle-модуль для всего сервиса.
     - Anemic domain (entity без методов).
     - Один adapter implements несколько ports разных доменов.
     - Generated DTO в port-сигнатуре.
   - **Замечание:**
     - bootstrap содержит небольшой business code (один-два класса) — рефакторить в core.
     - Отсутствие per-purpose in-adapter (User + Admin в одном).

## Что не входит

- DDD-агрегаты как код — `ucp-ddd-tactical-review`.
- UseCase Pattern (Command / Query / Handler) — `ucp-pattern-review`.
- jOOQ-имплементация в persistence/ — `ucp-jooq-review`.
- REST API контракт — `ucp-api-review`.
- Resilience-обвязка адаптеров — `ucp-resilience-review`.

$ARGUMENTS
