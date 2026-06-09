---
name: ucp-hexagonal-review
description: Ревью Hexagonal Architecture Java/Spring-сервиса (коды R-HEX-*) — multi-module gradle структура, чистота core без Spring/jOOQ/Jackson, ports в core/<bc>/port, маппинг в adapters in/out, bootstrap только композиция, ArchUnit-тесты.
when_to_use: Ревью многомодульного Hexagonal-сервиса — core/, *-in-adapter, *-out-adapter, bootstrap, build-файлы.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Hexagonal Architecture

Ты ревьюишь Hexagonal-структуру Java/Spring-сервиса на соответствие Hexagonal Style Guide. Главные точки контроля: чистота core/, правильное направление зависимостей (`bootstrap → core ← adapters`), naming и расположение ports, маппинг между слоями, ArchUnit-тесты.

## Зависимости

- **`.claude/docs/backend/hexagonal/hexagonal-rules.md`** — индекс всех правил (полный текст — соответствующий `*-style-guide.md`). Подгруппы: `R-HEX-WHEN-*` (когда), `R-HEX-MOD-*` (модули), `R-HEX-CORE-*` (core), `R-HEX-PORT-*` (ports), `R-HEX-AIN-*` (adapters in), `R-HEX-AOUT-*` (adapters out), `R-HEX-BOOT-*` (bootstrap), `R-HEX-TEST-*` (архитектурные тесты).
- Парные: `backend/usecase-pattern/usecase-pattern-rules.md` (`R-LAY-*` — Уровень 3), `backend/ddd-tactical/ddd-tactical-rules.md` (`R-AGG-*` для core), `backend/java/jooq/jooq-rules.md` (`R-JOOQ-REPO-*`), `backend/rest-api/rest-api-rules.md` (`R-OAS-*` для in-adapter).

## Инструкции

1. **Прочти** `.claude/docs/backend/hexagonal/hexagonal-rules.md`. Цитируй коды (`R-HEX-CORE-X1`, `R-HEX-PORT-X2`).

2. **Определи объект ревью.** Если пользователь назвал — бери. Иначе:
   - `git diff` на любые файлы в `core/`, `*-in-adapter/`, `*-out-adapter/`, `bootstrap/`.
   - `settings.gradle.kts` / `build.gradle.kts` с `include`-ами модулей.
   - ArchUnit-тесты в `bootstrap/src/test/java/` или `architecture-tests/`.
   - `<App>Application.java` и `@Configuration`-классы в bootstrap.

3. **Прогон по подгруппам:**
   - **`R-HEX-WHEN-*`** — Уровень 3 оправдан (Hexagonal — часть Уровня 3), Уровень 1–2 — overkill. Признаки готовности: 2+ внешних систем, агрегаты, 3+ типа input.
   - **`R-HEX-MOD-*`** — multi-module, core/ единственный без Spring, per-system out-adapters, per-purpose in-adapters, bootstrap composition root.
   - **`R-HEX-CORE-*`** — core зависит ТОЛЬКО от JDK + Lombok + ddd-building-blocks + usecase-pattern + jakarta.validation API; rich domain methods не anemic; generated POJO не используется как domain.
   - **`R-HEX-PORT-*`** — port-interfaces в core/<bc>/port/out/; сигнатуры с domain-типами; `<X>PortException` базовый в core, конкретные в adapters; UseCase = inbound port.
   - **`R-HEX-AIN-*`** — Controller implements generated `<Tag>Api`; маппит REST-DTO ↔ Command через mapper; диспатчит через UseCaseDispatcher; не зависит от out-adapter; не возвращает domain entity наружу.
   - **`R-HEX-AOUT-*`** — implements port из core; mapper для generated DTO ↔ domain; не возвращает generated DTO; не содержит бизнес-логику; не один adapter под несколько ports разных доменов.
   - **`R-HEX-BOOT-*`** — bootstrap только composition + configs; @SpringBootApplication только тут.
   - **`R-HEX-TEST-*`** — ArchUnit-тесты обязательны: core не импортит Spring/JOOQ/etc, port в правильном пакете, adapter implements port, in-adapter не зависит от out-adapter.

4. **Ищи паттерны-нарушения:**
   - Один gradle-модуль с `core/` подпапкой и `adapter/` подпапкой — `R-HEX-MOD-X1`.
   - В `core/build.gradle.kts` зависимость `implementation(project(":persistence"))` или подобная — `R-HEX-MOD-X2` критическое.
   - В `core/` файлы с `import org.springframework.*` — `R-HEX-CORE-X1` критическое.
   - В `core/` `import org.jooq.*` — `R-HEX-CORE-X2` критическое.
   - В `core/` `import com.fasterxml.jackson.*` — `R-HEX-CORE-X1` (Jackson — infra).
   - В `core/` Entity без методов, только `@Getter @Setter`, вся логика в `*Service` — `R-HEX-CORE-X3` (anemic).
   - В `core/` использование `OrdersPojo` (generated jOOQ) как тип агрегата — `R-HEX-CORE-X4`.
   - В `core/` использование `OrderJson` / `CreateOrderRequest` (REST-DTO) как тип — `R-HEX-CORE-X5`.
   - Port-interface (`<X>Port`) находится в `<system>-out-adapter/` а не в `core/<bc>/port/out/` — `R-HEX-PORT-X1` критическое.
   - `PaymentPort.register(SberRegisterRequest req)` (generated DTO в port-сигнатуре) — `R-HEX-PORT-X2`.
   - `PaymentPort.find(Long id) → Optional<Payment>` где отсутствие — error → `R-HEX-PORT-X3`.
   - `class <X>Port { ... }` (class вместо interface) — `R-HEX-PORT-X4`.
   - Controller с `if (req.amount > X) throw ...` (бизнес-логика) — `R-HEX-AIN-X1`.
   - Controller инжектит `<X>Repository` напрямую и вызывает методы — `R-HEX-AIN-X2`.
   - Controller возвращает `Order` (агрегат) или `OrderItem` наружу — `R-HEX-AIN-X3`.
   - В `*-in-adapter/build.gradle.kts` `implementation(project(":sber-out-adapter"))` — `R-HEX-AIN-X4` / `R-HEX-AOUT-X4` критическое.
   - Out-adapter port-метод возвращает `SberRegisterResponse` (generated) — `R-HEX-AOUT-X1`.
   - `if (sberResponse.code == 1) ... else ...` логика в адаптере — `R-HEX-AOUT-X2`.
   - `class XAdapter implements PaymentPort, NotificationPort` (несколько ports разных доменов) — `R-HEX-AOUT-X3`.
   - Out-adapter инжектит другой out-adapter — `R-HEX-AOUT-X4`.
   - В `bootstrap/` REST-controller или handler — `R-HEX-BOOT-X1`.
   - `@SpringBootApplication` в `core/` или `*-adapter/` — `R-HEX-BOOT-X2`.
   - **Отсутствие ArchUnit-тестов** в проекте — `R-HEX-TEST-X1` критическое.

5. **При ревью settings.gradle.kts:**
   - Перечислены все ожидаемые модули: `core`, `persistence`, `*-in-adapter`, `*-out-adapter`, `bootstrap`.

6. **При ревью build.gradle.kts модулей:**
   - `core/build.gradle.kts` — нет dependencies на `org.springframework`, `org.jooq`, project-зависимостей на adapters.
   - `*-out-adapter/build.gradle.kts` — `implementation(project(":core"))`, не `:persistence` или другой adapter.
   - `*-in-adapter/build.gradle.kts` — `implementation(project(":core"))`, не другой adapter.
   - `bootstrap/build.gradle.kts` — `implementation(project(":core"))` + все adapters.

7. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-finding-format.md`.

8. **Доменные ориентиры серьёзности:**
   - **Критично:**
     - Spring/JOOQ/Jackson import в core — нарушает фундамент Hexagonal.
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
