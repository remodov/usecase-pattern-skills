# claude-code-java

Скиллы (slash-команды) для Claude Code по методологии Use Case Pattern. Каждый скилл — компактный чек-лист для агента; полные style-guide-снапшоты лежат в `.claude/docs/*.md`.

## Принцип

- **`.claude/docs/*.md` — единственный источник правды.** Скиллы цитируют коды правил (`R-UC-1`, `JS-4.7`, `AUTH-15`, `PG-T-013` и т.д.), агент читает соответствующий гайд при работе.
- **Скиллы** — короткие инструкции для агента: что проверить, как отчитаться.

## Workflow: как пользоваться скиллами

Скиллы UCP — атомарные операции «сделай один артефакт по правилам». Для небольших задач этого хватает: открыл `ucp-pattern-design`, описал команду, получил `UseCase + Handler + контроллер`. Для **целого сервиса от спеки до прода** нужен оркестратор — эту роль играет [плагин `superpowers`](https://github.com/anthropics/skills/tree/main/skills/superpowers).

```
1. ИНПУТ — спецификация
   ucp-spec-design                              (если спеки ещё нет)
   ucp-spec-review                              (валидация дизайна — до кода!)
      ▸ замечания → правки → ucp-spec-review (fast) → 0 Критично

2. ПЛАНИРОВАНИЕ
   superpowers:brainstorming                    (если требования размытые)
   superpowers:writing-plans                    (читает спеку → план по шагам)

3. ИСПОЛНЕНИЕ
   superpowers:executing-plans                  (оркестратор)
      └─ на каждом шаге вызывает один из:
          ucp-bootstrap-design                  (gradle, профили, Liquibase, jOOQ codegen)
          ucp-ddd-tactical-design               (агрегаты, VO, события)
          ucp-pattern-design                    (UseCase + Handler + Controller)
          ucp-auth-design                       (Spring Security + RBAC + ABAC)
          ucp-api-design                        (OpenAPI + ProblemDetails)
          ucp-integration-design                (новый out-adapter с CB/Bulkhead/Retry + HealthIndicator)
          ucp-resilience-design                 (миграция existing out-adapter под R-RES-*)
          ucp-jooq-design                       (Jooq<X>Repository + Mapper + FilterConditionBuilder + ViewRepository)
          ucp-pg-schema-design                  (Liquibase changeset для нового агрегата под PG-T-*/PG-N-*)
          ucp-pg-migration-design               (expand-contract шаблоны: RENAME/DROP COLUMN, ALTER TYPE, FK NOT VALID + VALIDATE)
          ucp-pg-runtime-design                 (outbox-relay, task-queue, advisory-lock, optimistic-lock с @Retryable)
          ucp-validation-design                 (custom Jakarta-constraints, validation groups, cross-field-валидаторы)
          ucp-test-design                       (тесты на UC + BR)
   superpowers:test-driven-development          (TDD-дисциплина по ходу)
   superpowers:subagent-driven-development      (параллельно независимые шаги)

4. ПРОВЕРКА (обязательная)
   superpowers:verification-before-completion   (compileJava, test — всё зелёное)
   ucp-pg-schema-review     ← ОБЯЗАТЕЛЬНО на каждый PR с DDL/миграцией
   ucp-pattern-review + ucp-api-review + ucp-ddd-tactical-review +
   ucp-java-style-review + ucp-auth-review
   ucp-jooq-review                              (при ревью persistence/ — Jooq*Repository, *DomainRecordMapper, *FilterConditionBuilder)
   ucp-resilience-review                        (при ревью *-out-adapter/ — *ClientConfig, *ClientAdapter, application.yml resilience4j)
   ucp-validation-review                        (при ревью контроллеров, DTO, custom validators, @ConfigurationProperties)
   ucp-pg-explain-review                        (если есть тормозящие запросы / новые индексы)
   ucp-pg-runtime-review                        (при ревью @Transactional / outbox / bulk-операций / locks / pool / isolation)
   ucp-pg-migration-review  ← ОБЯЗАТЕЛЬНО на каждый PR с миграцией (lock-safety, expand-contract)
   superpowers:requesting-code-review           (внешний review)

5. ЗАВЕРШЕНИЕ
   superpowers:using-git-worktrees              (изоляция от main)
   superpowers:finishing-a-development-branch
```

**Симметрия design ↔ review.** Для каждого design-скилла есть парный review:
- `ucp-spec-design` ↔ `ucp-spec-review` (дизайн спеки)
- `ucp-pattern-design` ↔ `ucp-pattern-review` (UseCase Pattern)
- `ucp-ddd-tactical-design` ↔ `ucp-ddd-tactical-review` (DDD-тактические паттерны)
- `ucp-api-design` ↔ `ucp-api-review` (REST API контракт)
- `ucp-auth-design` ↔ `ucp-auth-review` (auth-паттерны)
- `ucp-integration-design` / `ucp-resilience-design` ↔ `ucp-resilience-review` (out-adapter, CB/Bulkhead/Retry; integration — новый, resilience-design — миграция existing)
- `ucp-jooq-design` ↔ `ucp-jooq-review` (persistence-слой: репозиторий, mapper, filter-builder, view-репозиторий)
- `ucp-pg-schema-design` ↔ `ucp-pg-schema-review` (Liquibase changeset для нового агрегата)
- `ucp-pg-migration-design` ↔ `ucp-pg-migration-review` (expand-contract шаблоны для breaking changes)
- `ucp-pg-runtime-design` ↔ `ucp-pg-runtime-review` (outbox-relay, task-queue, advisory-lock, optimistic-lock)
- `ucp-validation-design` ↔ `ucp-validation-review` (Jakarta Validation: custom constraints, groups, cross-field, @ConfigurationProperties)
- `ucp-bootstrap-design`, `ucp-test-design`, `ucp-java-style-review`, `ucp-pg-explain-review` — без пары

**`ucp-pg-schema-review` — обязательный шаг ПРОВЕРКИ.** Любой PR, который трогает DDL (`db/changelog/**`, `db/migration/**`, `*.sql` с `CREATE TABLE`/`ALTER TABLE`), должен пройти через `ucp-pg-schema-review` до code-review. Скилл проверяет типы (`PG-T-NNN`): `bigint IDENTITY` для PK, `timestamptz` для бизнес-времени, `numeric(p,s)` для денег, `uuid` для UUID, антипаттерны (`varchar(255)`, `varchar(36)`, `float` для денег, `timestamp` без TZ). Без этого ревью DDL не уходит в merge.

**Когда нужна вся связка:** новый сервис с нуля, миграция с классической слоёной архитектуры на UCP, большой рефакторинг с переходом на новый Tier.

**Когда `superpowers` избыточен:** одна операция, один UseCase, добавить эндпоинт в существующий сервис. Дёргай `ucp-*-design` напрямую. Но `ucp-pg-schema-review` всё равно вызывай, если меняется DDL.

`superpowers` ставится отдельно (см. [skills marketplace](https://github.com/anthropics/skills)), не зависит от этого репозитория.

## Скиллы

### `/ucp-api-review`

Ревью REST API контракта или кода на соответствие REST API Style Guide (`.claude/docs/rest-api-style-guide.md`).

**Что проверяет:**
- Формат URL (kebab-case, множественное число, вложенность)
- HTTP-методы и коды ответов
- Именование полей в JSON (camelCase, даты, enum)
- Формат ошибок (RFC 9457 ProblemDetails)
- Пагинация, сортировка, фильтрация
- OpenAPI-метаданные (`operationId`, `tags`, `summary`)
- Версионирование, deprecation, batch, async

**Использование:**

```
/ucp-api-review                              # ревью изменений из git diff
/ucp-api-review path/to/openapi.yaml         # ревью конкретного файла
/ucp-api-review src/.../OrderController.java
```

### `/ucp-api-design`

Проектирование новых REST API эндпоинтов по style guide. Генерирует OpenAPI-спеку и заметки по реализации.

**Что генерирует:**
- OpenAPI YAML с paths, schemas, error responses
- Примеры ошибок по RFC 9457
- Сигнатуры Spring-контроллеров
- Список DTO и error codes

**Использование:**

```
/ucp-api-design Управление заказами: CRUD + подтверждение + отмена
/ucp-api-design Эндпоинт загрузки аватара пользователя
/ucp-api-design Поиск товаров с фильтрами по категории, цене и наличию
```

### `/ucp-ddd-tactical-review`

Ревью доменного кода на соответствие тактическим паттернам DDD (`.claude/docs/ddd-tactical-style-guide.md`) и корректное использование библиотеки [`ddd-building-blocks`](https://gitlab.mosmetro.tech/common/ddd-building-blocks).

**Что проверяет:**
- Entity → `Entity<ID>`, equals/hashCode не переопределены, ID `final`
- Value Object → `ValueObject` + immutable + equals по значениям
- Aggregate Root → `AggregateRoot<ID>`, события только в корне
- Domain Event → `DomainEvent`, имя в прошедшем времени, immutable
- Repository → `AggregateRepository<T, ID>`, публикация событий в `save`
- Domain Service / Factory / Specification — обоснованность применения
- Структура пакетов (по домену, не по типу)

**Использование:**

```
/ucp-ddd-tactical-review                         # ревью изменений из git diff
/ucp-ddd-tactical-review src/.../order/domain    # ревью конкретного пакета
```

### `/ucp-pattern-review`

Ревью Java/Spring-кода на соответствие методологии Use Case Pattern (`.claude/docs/usecase-pattern-style-guide.md`) и корректное использование библиотеки [`usecase-pattern`](https://gitlab.mosmetro.tech/common/usecase-pattern).

**Что проверяет:**
- UseCase — immutable record/final, без логики
- UseCaseHandler — `@Component`, `useCaseType()`, `@Transactional` (или `readOnly`)
- Controller ходит только через `UseCaseDispatcher`
- CQRS-маркеры (Уровень 2+): `UseCaseCommand` / `UseCaseQuery`
- Слои моделей: JsonBean ≠ Pojo ≠ Domain
- Hexagonal (Уровень 4): `core/` не импортирует Spring/jOOQ/REST/Kafka
- UseCaseStep — только при реальном переиспользовании
- Транзакции на Handler, события после `repository.save(...)`

Скилл сам определяет уровень внедрения (1–4) и применяет соответствующие правила.

**Использование:**

```
/ucp-pattern-review                       # ревью изменений из git diff
/ucp-pattern-review src/.../OrderHandler.java
```

### `/ucp-pattern-design`

Проектирование нового UseCase + UseCaseHandler (плюс контроллер и маппер) под `usecase-pattern`.

**Что генерирует:**
- `<Operation>UseCase` — record, реализующий `UseCase` / `UseCaseCommand` / `UseCaseQuery`
- `<Operation>UseCaseHandler` — `@Component` с транзакционной политикой
- Метод контроллера, диспатчащий UseCase
- MapStruct-мапперы при необходимости
- Доменные объекты (на Уровне 3+) и раскладку под `core/` + `adapter/` (на Уровне 4)

**Использование:**

```
/ucp-pattern-design Команда «отменить заказ» с проверкой статуса
/ucp-pattern-design Запрос списка заказов клиента с пагинацией
```

### `/ucp-ddd-tactical-design`

Проектирование нового агрегата (entity, value object, события, repository) с использованием `ddd-building-blocks`.

**Что генерирует:**
- Корень агрегата, внутренние Entity, Value Objects (records)
- Доменные события (extends `DomainEvent`)
- Интерфейс репозитория (extends `AggregateRepository`)
- Раскладку пакетов по бизнес-домену
- Чек-лист тестов на инварианты и события

**Использование:**

```
/ucp-ddd-tactical-design Агрегат Order: позиции, статусы, событие OrderConfirmed
/ucp-ddd-tactical-design VO Money с поддержкой валют и арифметики
```

### `/ucp-spec-design`

Написание Use Case спецификации (`.claude/docs/usecase-spec-template.md`) сервиса по бизнес-описанию. Сам определяет нужный Tier (A — классическая слоёная, B — UCP L1–2, C — DDD/Hexagonal) и заполняет 16 разделов с правильной глубиной.

**Что генерирует:**
- Папка `docs/spec/` с **разбитыми по разделам файлами** — один `.md` на каждый из 16 разделов плюс консолидированный `<service>.md` для шаринга. Это инвариант — спеки одним файлом скилл больше не делает.
- 16 разделов: Bounded Context, глоссарий, доменная модель, состояния, роли, бизнес-правила, команды, события, queries, use cases, UI, саги, ошибки, интеграции, критерии приёмки, НФТ
- Frontmatter с `tier`, `service`, `last_updated`
- Кросс-ссылки между разделами (BR ↔ commands ↔ errors)

**Использование:**

```
/ucp-spec-design Сервис заказов: бизнес-описание в docs/case.md
/ucp-spec-design Tier C, Order Service, см. case.md и текущие агрегаты в src/
```

### `/ucp-spec-review`

**Парный к `/ucp-spec-design`** — AI как design-критик: проверка качества спецификации (или черновика Event Storming) **до кодогенерации**. Закрывает симметрию design ↔ review на спека-слое — то, что архитектор ловит на review, но что часто проскакивает мимо.

**Что проверяет (9 категорий правил):**
- **SR-T** Tier consistency — заявленный Tier vs реальная глубина содержания
- **SR-UL** Ubiquitous Language — синонимы вне глоссария, осиротевшие термины, термины без определения
- **SR-BC** Bounded Context — явный scope/not-scope, чужие команды, невидимое пересечение с соседями
- **SR-AG** Aggregates — > 7 инвариантов (кандидат на разделение), циклические ссылки, identity-типы вместо примитивов
- **SR-AR** Actors / Roles — orphan-актор, отсутствие permissions matrix, команды без роли-владельца
- **SR-CM** Commands — pre/post-conditions, идемпотентность для money-операций, CQRS-leak (read-DTO в команде)
- **SR-EV** Domain Events — события без потребителей, payload без типов, retryable без идемпотентного консьюмера, события вне Outbox
- **SR-FD** Failure Domains — стратегия при отказе для каждого внешнего соседа, таймаут / Circuit Breaker
- **SR-DO / SR-ACR / SR-NFR** — единственный владелец данных, PII-retention, покрытие BR через AC, измеримые пороги НФТ

**Три режима:**
- По умолчанию — полный прогон по всем 9 категориям
- `fast` — только правила-кандидаты на «Критично» (быстрая проверка перед кодогенерацией)
- `es` — урезанный набор для черновиков Event Storming (фокус на SR-UL, SR-BC, SR-AR, SR-EV)

**Использование:**

```
/ucp-spec-review                              # полный прогон спеки в docs/spec/
/ucp-spec-review fast                          # только критичные правила
/ucp-spec-review es docs/event-storming.md    # ревью ES-черновика
```

**Типичный цикл:**

```
ucp-spec-design  →  спека в docs/spec/
                          ↓
                  ucp-spec-review        →  список замечаний с кодами правил
                          ↓
       пользователь правит спеку / перезапускает ucp-spec-design с поправками
                          ↓
                  ucp-spec-review (fast)  →  0 Критично → готова к коду
                          ↓
              ucp-pattern-design / ucp-ddd-tactical-design / ucp-api-design
```

### `/ucp-java-style-review`

Ревью Java-кода на соответствие Java Style Guide (`.claude/docs/java-style-guide.md`) — именование, импорты, выражения, отступы. Каждое нарушение цитируется кодом правила (`JS-2.5`, `JS-4.7` и т.д.).

**Что проверяет:**
- Именование (классы — существительные; интерфейсы — без `I`; аббревиатуры по правилу 2/3 букв; константы UPPER_SNAKE_CASE; имена тестов).
- Импорты (без wildcard, без неиспользуемых).
- Выражения (булева сложность ≤ 3, Java-стиль массивов, порядок модификаторов, guard expressions, method references, big lambdas).
- Отступы (≤ 120 символов, перенос длинных выражений, без горизонтального выравнивания).

Скилл осознанно фокусируется на правилах, **которые не ловит checkstyle**: аббревиатуры, имена тестов, big lambdas, guard expressions, переносы.

**Использование:**

```
/ucp-java-style-review                         # ревью изменений из git diff
/ucp-java-style-review src/main/java/.../OrderHandler.java
```

### `/ucp-jooq-review`

Ревью persistence-слоя (модуль `persistence/`) на соответствие jOOQ Style Guide (`.claude/docs/jooq-style-guide.md`) — repository-pattern, multiset, фильтры, маппинг record↔domain, SelectMode, view-репозитории, transaction boundaries. Каждое нарушение цитируется кодом из подгрупп (`R-JOOQ-MS-1`, `R-JOOQ-LCK-X1` и т. д.).

**Что проверяет:**
- Codegen-конфиг: `setDaos(false)`, `setImmutablePojos(false)`, `OffsetDateTime` для timestamptz, `<enumConverter>true</enumConverter>` для domain-enum'ов.
- Repository-pattern: `Jooq<X>Repository implements <X>Repository` (interface в `core/`), конструкторная инъекция `DSLContext`, public-методы возвращают domain-типы, `SelectMode mode` параметром.
- Запросы: правильные fetch-методы (`fetchOptional`, `fetchExists`), UPDATE через `dslContext.update().set()`, не plain SQL.
- Multiset для nested-fetch: alias-keys в `SelectMultisetAliasKeys`, `RecordMappingUtils` для извлечения, batch-fetch при много parents.
- Filter-builders: `<X>FilterConditionBuilder` Spring-bean + `FilterConditionHelper.andIfNotNull/Empty/True`, EXISTS для cross-table.
- Mapper: plain Java class (Spring `@Component`), не MapStruct; `toDomain` / `fromDomain` / `assembleAggregate`; enum через `forcedType` или `fromValue`; JSONB через `JooqJsonbHelper`.
- Locks: `SelectMode` enum в `core/`, `applyLock()` switch, `forUpdate()` всегда внутри `@Transactional`.
- Транзакции: `@Transactional` на handler, не на репозитории; `readOnly = true` для query-handler'ов.
- View-репозитории: `<X>ViewRepository` отдельно от `<X>Repository`, если read-проекция отличается.

Скилл фокусируется на **jOOQ-фасаде** над PostgreSQL. Настройки runtime (WAL, autovacuum, connection pool) — это `ucp-pg-runtime-review`. Сама схема — `ucp-pg-schema-review`.

**Использование:**

```
/ucp-jooq-review                          # ревью изменений из git diff
/ucp-jooq-review persistence/.../order/JooqOrderRepository.java
/ucp-jooq-review persistence/.../order/   # весь пакет
```

### `/ucp-resilience-review`

Ревью защиты сервиса от отказов внешних систем на соответствие Resilience Style Guide (`.claude/docs/resilience-style-guide.md`) — timeouts, circuit breaker, retry, bulkhead, fallback, health checks, связка с OpenAPI generator. Каждое нарушение цитируется кодом из подгрупп (`R-RES-CB-1`, `R-RES-OAS-X1` и т. д.).

**Что проверяет:**
- Per-system isolation: свой `OkHttpClient`/`RestClient` bean + pool + dispatcher на каждую внешнюю систему (Sber, OdnaKassa, etc.). Shared pool — критическое нарушение.
- Timeouts: `connectTimeout < readTimeout < callTimeout`, типовые значения, обоснования отклонений в yml.
- Circuit Breaker: `@CircuitBreaker(name = "<system>")` на public-методе adapter (не на generated client, не на helper, не на репозитории), per-system конфиг через `application.yml`.
- Retry только при идемпотентности: GET либо команда с `Idempotency-Key` (`AUTH-19`); не на 4xx; обязательный exp backoff; не Spring-Retry.
- Bulkhead: semaphore-based (не thread-pool), отдельный слой защиты от connection pool.
- Fallback: cached read / default / async-mode (queue + 202 Accepted) — да; null/zero для money — нет.
- Конфиг через `application.yml` (Spring Cloud Config friendly), не программный `CircuitBreakerConfig.custom()`.
- **Связка с OpenAPI generator:** аннотации на adapter-методе (не на generated `<X>Api`), `spring-restclient` target для нового кода (Retrofit2 — только legacy), mapper между generated DTO и domain.
- HealthIndicator per-system, cached с TTL 30s, light probe (не business-операция).
- `Thread.sleep` цикл в sync-handler — критическое нарушение, переводить в task-queue.
- Resilience4j metrics через Micrometer не отключены, OTel-spans с `circuit_breaker.state`.

Скилл сфокусирован на **outbound HTTP к внешним системам**. Inbound rate-limiting обычно живёт в API Gateway (Spring Cloud Gateway / Kong / Istio), не в каждом сервисе.

**Использование:**

```
/ucp-resilience-review                    # ревью изменений из git diff
/ucp-resilience-review sber-out-adapter/  # весь модуль
/ucp-resilience-review src/main/resources/application.yml  # только конфиг
```

### `/ucp-integration-design`

Генерирует **полный скелет outbound-интеграции** с новой внешней системой под Resilience Style Guide. Создаёт:
- Доменный port в `core/<bc>/port/out/<system>/` (interface + command/result records).
- Gradle-модуль `<system>-client-generator/` с `openapi-generator` плагином (target `spring-restclient`).
- Gradle-модуль `<system>-out-adapter/` со всем требуемым: `<System>ClientConfig` + `ClientSettings` + `ClientAdapter` (с `@CircuitBreaker`/`@Bulkhead`/`@Retry`) + `Mapper` + `HealthIndicator` (TTL-кеш) + exception hierarchy (4xx/5xx).
- Patch для `application.yml`: блок `client.<system>` + `resilience4j.{circuitbreaker,bulkhead,retry}.instances.<system>` + `management.health.<system>.enabled`.
- Patch для `settings.gradle.kts` и `bootstrap/build.gradle.kts`.

Решает по входным параметрам:
- **Money** (`PaymentPort`, `BillingPort`) → CB failure rate `30%`, fallback = task-queue + 202 Accepted.
- **Idempotent** (read или Idempotency-Key per `AUTH-19`) → `@Retry` добавляется.
- **Non-idempotent write** → `@Retry` запрещён (`R-RES-RE-X1`), только CB+Bulkhead.
- **Long-running (>30s)** → не sync-вызов, генерируется задача в task-queue (`R-RES-ASYNC-1`).

После генерации — финальный шаг `/ucp-resilience-review` для верификации.

**Использование:**

```
/ucp-integration-design Адаптер для twilio: SMS-уведомления, AUTH=apiKey
/ucp-integration-design Платёжный адаптер для yandex-pay, money, OpenAPI здесь:...
/ucp-integration-design Outbound для system X, read-heavy, без Idempotency-Key
```

### `/ucp-jooq-design`

**Парный к `/ucp-jooq-review`.** Генерирует persistence-слой на jOOQ из доменного `<X>Repository` интерфейса под jOOQ Style Guide. Создаёт:
- `Jooq<X>Repository` — реализация с `DSLContext`, multiset для eager-fetch child-коллекций, `applyLock()` switch для `SelectMode`, private `toSortFields()` helper.
- `<X>DomainRecordMapper` — Plain Java (если есть assemble-логика, enum-translation, JSONB) или MapStruct interface (для простых DTO ↔ POJO).
- `<X>FilterConditionBuilder` — если фильтр > 3 полей или содержит EXISTS-условия. С `FilterConditionHelper.andIfNotNull/Empty/True`.
- `Jooq<X>ViewRepository` — отдельный класс, если `<X>ViewRepository` интерфейс отличается от основного репозитория (read-проекции).
- `SelectMode`, `PaginationView`, `SelectMultisetAliasKeys`, `FilterConditionHelper` в core/persistence — если ещё не существуют.

Решает по входным параметрам:
- **Aggregate с children** → multiset для eager-fetch, alias-key из `SelectMultisetAliasKeys`.
- **Filter > 3 полей** → отдельный `<X>FilterConditionBuilder`, иначе inline-предикаты.
- **Read-проекция отличается от агрегата** → `Jooq<X>ViewRepository` отдельно.
- **Mapper с assemble/enum/JSONB** → Plain Java; иначе MapStruct interface.

Предполагает, что `<X>Repository` интерфейс и Aggregate уже существуют (через `ucp-ddd-tactical-design`). Liquibase-миграции — отдельным шагом.

**Использование:**

```
/ucp-jooq-design Репозиторий для агрегата Order: фильтр по статусам, customerId, диапазон дат
/ucp-jooq-design persistence для Receipt — есть OrderViewRepository с summary-проекциями
```

### `/ucp-pg-schema-design`

**Парный к `/ucp-pg-schema-review`.** Генерирует Liquibase changeset (YAML) для нового агрегата под `pg-types-style-guide.md` (`PG-T-*`) и `pg-naming-style-guide.md` (`PG-N-*`):
- `CREATE TABLE` с типами: `bigint IDENTITY` или `uuid v7` для PK, `numeric(p,s)` для денег, `timestamptz` для бизнес-времени, `text` для строк (без `varchar(255)`), JSONB для VO с complex structure.
- FK constraints с CASCADE-стратегией (`ON DELETE CASCADE` для child-сущностей агрегата).
- Индексы под фильтрацию (FK всегда отдельным индексом + composite под `<X>Filter`).
- Audit-колонки (`created_at` / `updated_at`), soft-delete (`deleted_at` если применимо).
- Подключение в `migrations/db/changelog-master.yaml` через include.

Применяется **после** `ucp-ddd-tactical-design` (Aggregate Root уже существует) и **до** `ucp-jooq-design` (jOOQ codegen из живой схемы).

**Использование:**

```
/ucp-pg-schema-design DDL для агрегата Order: items, status, totalAmount, customerId, soft-delete
/ucp-pg-schema-design Schema для Receipt с child Receipt_Item, JSONB для fiscal-данных
```

### `/ucp-pg-migration-design`

**Парный к `/ucp-pg-migration-review`.** Генерирует **безопасные** expand-contract Liquibase changeset'ы для типовых breaking changes по `pg-migrations-style-guide.md` (`PG-M-*`):
- `RENAME COLUMN` — 3 фазы (add new + sync trigger → deploy code → drop trigger + drop old).
- `ALTER TYPE` — 2-3 фазы через теневую колонку + swap.
- `ADD CONSTRAINT FK` — 2 фазы (`NOT VALID` + отдельный `VALIDATE`).
- `SET NOT NULL` — через `CHECK NOT VALID + VALIDATE + SET NOT NULL` (PG12+).
- `CREATE INDEX` — `CONCURRENTLY` + `runInTransaction: false` + `VACUUM` после.
- Удаление значения enum — через теневой тип.

Каждая phase имеет `SET LOCAL lock_timeout = '3s'`. Все операции обеспечивают **N-1 совместимость** (миграция работает с предыдущей версией кода). Без down-rollback'ов: `PG-M-*` правило — forward fix, не rollback.

**Использование:**

```
/ucp-pg-migration-design RENAME COLUMN customer.email → primary_email
/ucp-pg-migration-design SET NOT NULL для order.confirmed_at, таблица 50M строк
/ucp-pg-migration-design Добавить FK order.customer_id → customer.id в проде
```

### `/ucp-pg-runtime-design`

**Парный к `/ucp-pg-runtime-review`.** Генерирует runtime-инфраструктуру для четырёх типовых PG-сценариев по `pg-runtime-style-guide.md`:

1. **Outbox-relay** — durable publishing доменных событий. DDL `outbox_event` с partial-индексом `WHERE published_at IS NULL`, scheduler с `FOR UPDATE SKIP LOCKED` (`PG-L-021`), запись в outbox в той же транзакции что и UPDATE агрегата.
2. **Task-queue** — durable retry для resilience-fallback (см. `R-RES-FB-1`). DDL `<x>_task` с retry_count + next_attempt_at, scheduler-poll, `Process<X>TaskCommandHandler` с exponential backoff.
3. **Advisory lock** — singleton scheduled-job в кластере (`PG-L-060`). `pg_try_advisory_xact_lock` (xact-вариант, отпускается на коммите).
4. **Optimistic lock** — через `version`-колонку (`PG-L-051`), UPDATE с проверкой `version`, Spring `@Retryable` на `OptimisticLockException` (`PG-L-072`).

При выборе сценария скилл уточняет один из четырёх параметров и генерирует только нужное.

**Использование:**

```
/ucp-pg-runtime-design Outbox-relay для domain-событий Order
/ucp-pg-runtime-design Task-queue для платёжных задач (PaymentTask)
/ucp-pg-runtime-design Advisory lock для DailyReportJob — только один инстанс
/ucp-pg-runtime-design Optimistic locking для агрегата Order
```

### `/ucp-validation-review`

Ревью валидации входных данных (Jakarta Validation) на соответствие Validation Style Guide (`.claude/docs/validation-style-guide.md`) — где валидируем, какие constraints, custom-валидаторы, validation groups, cross-field, OpenAPI integration. Каждое нарушение цитируется кодом из подгрупп (`R-VLD-WHERE-1`, `R-VLD-OAS-X1` и т. д.).

**Что проверяет:**
- `@Valid` на `@RequestBody`/`@RequestParam` контроллеров и на nested-полях DTO (без `@Valid` nested не валидируется).
- `@Validated` на каждом `@ConfigurationProperties` классе (невалидный конфиг → fail-fast на старте).
- Manual `if (cmd.x < 0) throw` в Handler — критическое нарушение (теряется единый формат `violations` в ProblemDetails).
- `@NotNull` на примитивах — мёртвый код.
- `@Pattern` с regex для email — должен быть `@Email`.
- Custom validators в правильных местах (`core/<bc>/validation/` для domain, `common/validation/` для общих).
- Custom validator: `isValid(null) → true` (для композиции с `@NotBlank`/`@NotNull`).
- Cross-field правила как class-level annotations, не `@AssertTrue`-методы.
- Validation groups только для одного DTO с разными required-полями (Create/Update), не для «строгая/мягкая».
- `useBeanValidation = true` в openapi-generator конфиге.
- Аннотации руками в generated DTO (затрётся при regenerate) — критическое.
- `message` на русском, не английском.

Связь с `R-ERR-5`/`R-ERR-6` (REST API): violations возвращаются в стандартном формате ProblemDetails, не пиши свой обработчик.

**Использование:**

```
/ucp-validation-review                          # ревью изменений из git diff
/ucp-validation-review user-api-in-adapter/     # все контроллеры + DTO модуля
/ucp-validation-review src/main/java/.../validation/   # custom-validators
```

### `/ucp-validation-design`

**Парный к `/ucp-validation-review`.** Генерирует кастомный Jakarta Validation constraint, validation group или cross-field-валидатор по Validation Style Guide:
- **Field-level custom constraint** (`@RussianPhone`, `@VatNumber`, `@Iso8601Duration`) — annotation interface + `ConstraintValidator` implementation, расположение по domain (`core/<bc>/validation/` для domain-specific, `common/validation/` для общих технических).
- **Validation group** — пустой interface с doc-comment («применяется в Create/Update»).
- **Cross-field constraint** (`@DateRange`, `@PasswordsMatch`) — class-level annotation с `addPropertyNode(<field>)` для прицепления ошибки к конкретному полю в violations.

Решает по входным параметрам:
- **Куда положить** — domain-vocabulary в `core/<bc>/validation/`, общий технический в `common/validation/`.
- **Имя** — `@<DomainTerm>` без префиксов `Valid`/`Check`/`Is`.
- **`isValid(null)` → `true`** — обязательно для композиции с `@NotNull`/`@NotBlank`.
- **Standard composition** (только `@NotBlank + @Size + @Pattern`) — НЕ создаёт custom constraint, использовать standard-аннотации напрямую.

**Использование:**

```
/ucp-validation-design Custom constraint @RussianPhone — формат +7XXXXXXXXXX
/ucp-validation-design Validation group OnCreate / OnUpdate для OrderRequest
/ucp-validation-design Cross-field @DateRange для OrderFilterRequest
```

### `/ucp-resilience-design`

**Парный к `/ucp-integration-design` для existing-кода.** Добавляет Resilience4j-обвязку к **уже существующему** out-adapter, который сейчас защищается ad-hoc (только timeouts + try/catch). Миграционный скилл — превращает «защита из try-catch» в стандарт `R-RES-*`.

Что делает:
- Audit текущего адаптера: что есть из `R-RES-*`, чего нет.
- Per-system isolation в `<X>ClientConfig` (если был shared bean — разделяет).
- Аннотации `@CircuitBreaker`/`@Bulkhead`/`@Retry` на public-методах adapter.
- Маркирует sleep-loop polling (`R-RES-ASYNC-X1`) **TODO-комментариями** + явно отмечает в отчёте «требует доработки в `core/`» (полный перевод в task-queue — отдельным шагом через `ucp-pattern-design`).
- Добавляет `<System>HealthIndicator` если ещё нет.
- Patch для `application.yml`: блок `resilience4j.*.instances.<system>`.

Не создаёт новые модули, не трогает port в `core/`. Для **новых** интеграций — `/ucp-integration-design`.

**Использование:**

```
/ucp-resilience-design sber-out-adapter/                     # миграция всего модуля
/ucp-resilience-design insurance-out-adapter/                # включая sleep-loop → TODO
```

### `/ucp-auth-review`

Ревью кода на соответствие паттернам авторизации (`.claude/docs/auth-patterns-style-guide.md`) — JWT + RBAC + ABAC + S2S + audit + PII / секреты + идемпотентность. Каждое нарушение цитируется кодом правила (`AUTH-9`, `AUTH-15` и т.д.).

**Что проверяет:**
- JWT validation через `oauth2ResourceServer().jwt()`, без кастомных фильтров.
- На каждом REST-endpoint — `@PreAuthorize`.
- Если endpoint работает с агрегатом по id — есть ABAC-проверка владения.
- Outbound клиенты используют mTLS / Bearer (не анонимный HTTP).
- `admin`-команды пишутся в audit log.
- PII (email/phone/address/токены) не попадают в логи и `ProblemDetails.detail`.
- Денежные команды требуют `Idempotency-Key`.

**Использование:**

```
/ucp-auth-review                                # ревью изменений из git diff
/ucp-auth-review src/main/java/.../SecurityConfig.java
```

### `/ucp-auth-design`

Генерирует Spring Security + OAuth2 Resource Server конфигурацию под методологию: JWT, RBAC, ABAC-хелперы, audit-аспект, layout секретов, идемпотентность.

**Что генерирует:**
- `SecurityConfig` с `oauth2ResourceServer().jwt()` + `JwtAuthenticationConverter` (роли из `realm_access.roles`).
- `AuthenticatedX` хелперы по ролям.
- `@Component("access")` с ABAC-методами.
- `@Around`-аспект для audit log админских команд.
- Шаблоны `application-*.yml` с плейсхолдерами секретов.

**Использование:**

```
/ucp-auth-design Domain Service: customer + admin, ABAC по customerId
/ucp-auth-design BFF: OAuth2 Authorization Code + PKCE + Redis-сессия
```

### `/ucp-test-design`

Проектирование интеграционных и unit-тестов под стратегию тестов (`.claude/docs/test-strategy.md`): синхронные, только PostgreSQL + WireMock, без Kafka/Redis в базовом классе, события через in-memory publisher.

**Что генерирует:**
- `BaseIntegrationTest` (если ещё нет) — Testcontainers PostgreSQL с reuse, WireMock, in-memory `DomainEventPublisher`.
- Тесты на каждый UseCase / use case из спеки (UC-N happy + альтернативы + ошибки).
- Тесты на каждое бизнес-правило (BR-N) с кодом в `@DisplayName`.
- Тесты на каждое доменное событие — что оно публикуется в правильный момент.

**Использование:**

```
/ucp-test-design Тесты для CreateOrderUseCase из docs/spec/order-service.md
/ucp-test-design Покрой UC-1..UC-3 + BR-001..BR-007
```

### `/ucp-pg-schema-review`

Ревью PostgreSQL-схемы и миграций (DDL Liquibase / Flyway / сырой SQL) против `pg-types-style-guide.md` (правила `PG-T-NNN`).

**Что проверяет:**
- Числа: `bigint IDENTITY` для PK, `numeric(p,s)` для денег, без `serial`/`float`.
- Строки: `text` по умолчанию, `varchar(N)` только под доменное правило, без `varchar(255)`.
- Время: `timestamptz` для бизнес-времени, никогда `timestamp without time zone`.
- UUID: тип `uuid`, не `varchar(36)`; v7 для PK; индексы по FK.
- Boolean / enum / JSONB / массивы / range — правила выбора.

**Использование:**

```
/ucp-pg-schema-review                          # все DDL-файлы из git diff
/ucp-pg-schema-review db/changelog/v0001.xml   # конкретный changeset
```

### `/ucp-pg-explain-review`

Ревью индексов и плана запроса PostgreSQL против `pg-indexes-style-guide.md` (правила `PG-I-NNN`, `PG-E-NNN`).

**Что проверяет:**
- Composite-индексы: левый префикс, порядок полей, range последним.
- Типы индексов: B-tree / GIN / GiST / BRIN / pg_trgm / partial / `INCLUDE` — выбор под задачу.
- Селективность через `pg_stats`, ловушка с `Index Only Scan` на «неподходящем» индексе для `count(1)`.
- Чтение `EXPLAIN (ANALYZE, BUFFERS)`: `Filter` vs `Index Cond`, `Heap Fetches`, `Rows Removed by Filter`, `external merge Disk`, Nested Loop `loops`.
- `CREATE INDEX CONCURRENTLY` в продакшен-миграциях.

**Использование:**

```
/ucp-pg-explain-review                                  # из git diff (DDL индексов)
/ucp-pg-explain-review                                  # с приложенным EXPLAIN ANALYZE
```

### `/ucp-pg-runtime-review`

Ревью runtime-аспектов PostgreSQL против `pg-runtime-style-guide.md` (правила `PG-W-NNN`, `PG-V-NNN`, `PG-L-NNN`).

**Что проверяет:**
- WAL: длинные транзакции в `@Transactional` (HTTP/Kafka/S3 внутри), bulk-операции (COPY vs цикл INSERT), HOT/fillfactor, JSONB с горячими полями.
- VACUUM: `autovacuum_enabled = false`, отсутствие `VACUUM ANALYZE` после big-миграции, тюнинг `scale_factor` для горячих таблиц.
- Locks: `SELECT FOR UPDATE` без `@Transactional`, отсутствие `SKIP LOCKED` в outbox-relay/очередях, deadlock-prone порядок блокировок (multi-row без сортировки по id), `pg_advisory_xact_lock` для singleton scheduled-job, optimistic vs pessimistic выбор.
- `lock_timeout` в миграциях, `synchronous_commit = off` для метрик.

**Использование:**

```
/ucp-pg-runtime-review                                  # все Java/SQL изменения из git diff
/ucp-pg-runtime-review src/main/java/.../OutboxRelay.java
```

### `/ucp-pg-migration-review`

Ревью PostgreSQL миграций (Liquibase / Flyway / сырой SQL) на безопасность для прода против `pg-migrations-style-guide.md` (правила `PG-M-NNN`).

**Что проверяет:**
- Lock-агрессивность: `ALTER TABLE` без `lock_timeout`, `CREATE INDEX` без `CONCURRENTLY`, `ADD CONSTRAINT FK` без `NOT VALID`.
- Expand-contract: `RENAME COLUMN`, `DROP COLUMN`, `ALTER TYPE` одним statement без 3+ релизов.
- N-1 совместимость: миграция работает с предыдущей версией кода.
- `SET NOT NULL` через `CHECK NOT VALID + VALIDATE + SET NOT NULL`.
- `UPDATE` миллионов строк в миграции (должно быть в backfill-job).
- Удаление значения из enum (только через теневой тип).
- `down`-миграции (почти всегда не работают на проде).

**Использование:**

```
/ucp-pg-migration-review                              # из git diff (миграции)
/ucp-pg-migration-review db/changelog/v0042.xml       # конкретный changeset
```

**Обязательный шаг ПРОВЕРКИ.** Любой PR с миграцией должен пройти этот скилл. На проде это разница между «прокатилось за минуту» и «легло на 30 минут с лок-стормом».

## Подключение к проекту

### Через `install.sh` (рекомендуется)

```bash
git clone https://gitlab.mosmetro.tech/common/claude-code-java.git ~/projects/claude-code-java
cd ~/projects/claude-code-java

# подключить все скиллы и style-guide-снапшоты в свой Java-проект:
./install.sh ~/my-java-project
```

Скрипт создаёт симлинки на `.claude/skills/*` и `.claude/docs/*.md` — обновления
в этом репо автоматически прилетят в проект, без ручного re-копирования.

После установки в проекте появятся:

- `.claude/skills/ucp-*/` — все скиллы (`ucp-pattern-review`, `ucp-api-design` и т.д.)
- `.claude/docs/*.md` — снапшоты style-guide-ов, которые скиллы читают как input

Style-guide-ы — это **инструментальные** документы, не часть проектной
документации. Поэтому они живут под `.claude/docs/`, а не в пользовательской
`docs/`. Ваша проектная `docs/` остаётся чистой для проектной документации
(спецификация, ADR-ы, диаграммы и т.п.).

> Если вы устанавливали скиллы старым `install.sh` (до 2026-04-29) — он создавал
> симлинки в `<project>/docs/`. Новый `install.sh` автоматически их вычищает
> при повторном запуске. Просто `git pull` в репо скиллов и `./install.sh
> ~/your-project` — старые симлинки удалятся, новые появятся в `.claude/docs/`.

### Глобально для всех проектов

```bash
./install.sh ~/.claude
# скиллы будут доступны во всех Claude Code-сессиях независимо от проекта
```

### Опциональные плагины Claude Code

Большинство скиллов (11 из 12) работают **без внешних плагинов** — только на
стандартных tools (Read, Glob, Grep, Write, Edit, Bash, Agent).

Скилл `ucp-spec-design` опционально использует два расширения.

#### `superpowers` — планирование, TodoWrite, TDD-дисциплина

Marketplace плагинов от obra ([obra/superpowers-marketplace](https://github.com/obra/superpowers-marketplace)):

```bash
claude plugin marketplace add obra/superpowers-marketplace
claude plugin install superpowers@superpowers-marketplace
```

После установки доступны скиллы `superpowers:writing-plans`,
`superpowers:executing-plans`, `superpowers:brainstorming`,
`superpowers:test-driven-development` и т.д. — `ucp-spec-design`
интегрируется с ними автоматически.

#### `context7` — MCP-сервер с актуальной документацией библиотек

Сервер от Upstash ([upstash/context7](https://github.com/upstash/context7)).
Stdio-вариант (рекомендуется, не требует серверной части):

```bash
claude mcp add context7 -- npx -y @upstash/context7-mcp
```

HTTP-вариант (если предпочитаете remote endpoint):

```bash
claude mcp add --transport http context7 https://mcp.context7.com/mcp
```

После установки `ucp-spec-design` и другие скиллы могут запросить актуальные
версии Spring Boot, jOOQ и других зависимостей через
`mcp__plugin_context7_context7__resolve-library-id` и `query-docs`.

#### Без плагинов

`ucp-spec-design` всё равно работает — просто без TodoWrite-планирования
и без проверки актуальности версий библиотек. Остальные 11 скиллов их
не требуют вообще.

## Структура

```
.claude/skills/
├── ucp-api-review/                 # ревью контракта REST API
├── ucp-api-design/                 # проектирование REST-эндпоинтов
├── ucp-pattern-review/     # ревью кода на соответствие Use Case Pattern
├── ucp-pattern-design/     # проектирование UseCase + Handler
├── ucp-ddd-tactical-review/        # ревью доменного кода (DDD tactical)
├── ucp-ddd-tactical-design/        # проектирование агрегата (DDD tactical)
├── ucp-spec-design/        # написание Use Case спецификации сервиса
├── ucp-java-style-review/  # ревью Java-кода на стиль (naming, imports, expressions)
├── ucp-jooq-review/        # ревью persistence-слоя на jOOQ (repository, multiset, mapper)
├── ucp-jooq-design/        # генерация Jooq<X>Repository + Mapper + FilterConditionBuilder + ViewRepository
├── ucp-pg-schema-design/   # Liquibase changeset для нового агрегата (PG-T-*/PG-N-*)
├── ucp-pg-migration-design/ # expand-contract шаблоны для breaking changes (PG-M-*)
├── ucp-pg-runtime-design/  # outbox-relay, task-queue, advisory-lock, optimistic-lock (PG-W/L-*)
├── ucp-validation-review/  # ревью Jakarta Validation (R-VLD-*)
├── ucp-validation-design/  # генерация custom constraints, groups, cross-field
├── ucp-resilience-review/  # ревью защиты от отказов внешних систем (CB, retry, bulkhead, OpenAPI generator)
├── ucp-integration-design/ # генерация ПОЛНОГО скелета новой outbound-интеграции (port + client-generator + out-adapter)
├── ucp-resilience-design/  # миграция existing out-adapter под R-RES-* (CB/Bulkhead/Retry без создания модулей)
├── ucp-test-design/        # проектирование интеграционных и unit-тестов
├── ucp-auth-review/        # ревью авторизации (JWT, RBAC, ABAC, audit, PII)
└── ucp-auth-design/        # scaffold Spring Security + OAuth2 для UCP-сервиса

.claude/docs/
├── rest-api-style-guide.md          # REST API Style Guide (R-*-*)
├── usecase-pattern-style-guide.md   # Use Case Pattern (R-UC-*, R-HND-*, R-LAY-*)
├── ddd-tactical-style-guide.md      # тактические паттерны DDD (R-ENT-*, R-AGG-*, R-VO-*)
├── usecase-spec-template.md         # шаблон Use Case спецификации
├── java-style-guide.md              # Java Style Guide (JS-*)
├── jooq-style-guide.md              # jOOQ Style Guide (R-JOOQ-CFG-*/REPO-*/MS-*/...)
├── resilience-style-guide.md        # Resilience Style Guide (R-RES-CB-*/RE-*/BH-*/OAS-*/...)
├── validation-style-guide.md        # Validation Style Guide (R-VLD-WHERE-*/STD-*/CC-*/OAS-*/...)
├── test-strategy.md                 # стратегия тестов
└── auth-patterns-style-guide.md     # паттерны авторизации (AUTH-*)
```

## Связанные библиотеки

- [`ddd-building-blocks`](https://gitlab.mosmetro.tech/common/ddd-building-blocks) — Java-библиотека базовых DDD-абстракций, на которой опираются скиллы DDD.
- [`usecase-pattern`](https://gitlab.mosmetro.tech/common/usecase-pattern) — Java-библиотека UseCase / UseCaseHandler / UseCaseDispatcher.
- [`hexagonal-architecture`](https://gitlab.mosmetro.tech/common/hexagonal-architecture) — Java-библиотека для Hexagonal-разделения (`core` ↔ `adapter-in/out`) на Уровне 4.

В планах — скиллы для CQRS, Hexagonal, Distributed Patterns, Observability, Caching, Kafka.

## Лицензия

MIT
