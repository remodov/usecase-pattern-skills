# claude-code-java

Скиллы (slash-команды) для Claude Code по методологии Use Case Pattern. Каждый скилл — компактный чек-лист для агента; корпус требований лежит в `.claude/docs/`.

> **Мультиязычность и специализации.** Методология устроена по двум ортогональным осям:
> **язык** (`lang`: java — референс, python — полностью покрыт, node/go — пилот) и
> **специализация** (`track`: backend — 42 домена, общий слой — 4, e2e — 2; frontend — процедура поверх требований
> шаблонов `<репозиторий шаблонов фронтенда>`).
> Требование язык-нейтрально, реализация — в `<домен>/references/<lang>/`. Подробно —
> `.claude/docs/_meta/authoring-contract.md`. Backend-скиллы названы `ucp-<concern>` (java) /
> `ucp-<lang>-<concern>` (напр. `ucp-py-pattern-design`); каталог ниже описывает java-набор.

## Принцип

- **`.claude/docs/` — единственный источник правды.** Правило — это **требование** с идентификатором (`jooq/nested-collections-in-one-query`, `pg-types/money-is-numeric`), а не буллет с кодом. Скиллы цитируют идентификаторы, агент читает `spec.md` нужного домена.
- **У каждого требования сказано, чем оно ловится.** Поле «Гейт» называет проверку либо честно говорит `ревью`; поле «Не ловит» — что проскакивает мимо. Это главное отличие корпуса от обычного свода правил.
- **Скиллы** — короткие инструкции для агента: что проверить, как отчитаться.

## Формат требования

```markdown
### Requirement: Nested-выборка через multiset

Вложенные коллекции SHALL читаться одним запросом; цикл с отдельным
запросом на элемент SHALL NOT применяться.

**Почему**: сто первый запрос вместо одного не виден в коде и не роняет тест —
он проявляется ростом задержки на боевом объёме.
**ID**: jooq/nested-collections-in-one-query
**Код**: R-JOOQ-MS-1, R-JOOQ-MS-X2
**Гейт**: ревью
**Покрытие**: нет
**Не ловит**: догрузка в цикле — обычный код с верным результатом;
число запросов видно только в журнале базы.

#### Scenario: маппер догружает позиции для каждого заказа
- **WHEN** список из ста заказов
- **THEN** выполняется сто первый запрос, результат верный
```

| Поле | Что означает |
| --- | --- |
| **ID** | адрес требования: `<домен>/<имя>`, уникален по корпусу |
| **Почему** | последствие в терминах прода: что ломается и для кого, если требование не выполнено; обязательное |
| **Код** | старый код правила — чтобы ссылки из архива ревью и подавлений находились грепом |
| **Гейт** | вид проверки (`checkstyle:X`, `archunit:Y`, `script:ddl-check`, `ci:...`) или `ревью`; у кросс-языковых доменов — по языкам через `·` |
| **Покрытие** | `полное` / `частичное` / `нет`; считается для проекта по `ucp-bootstrap-design` и **по худшему языку** |
| **Не ловит** | что проходит мимо гейта; при неполном покрытии заполнено обязательно |

**Читай эти поля первыми.** Сегодня 59 % требований корпуса держатся ревью —
там единственная защита — внимательность читающего.

| Покрытие | Требований |
| --- | --- |
| полное | 20 |
| частичное | 367 |
| нет | 560 |

## Гейты проекта

Часть проверок методология определяет сама, и `ucp-*-bootstrap-design` заводит
их в сервисе. Каталог — `.claude/docs/_meta/project-gates.md`: 155 собственных
проверок плюс 120 имён правил чужих анализаторов.

| Скрипт | Что читает | Примеры проверок |
| --- | --- | --- |
| `ddl-check` | миграции | деньги не плавающей точкой, момент с зоной, ограничение ожидания блокировки, индекс без параллельного режима |
| `config-check` | конфигурацию по профилям | идемпотентный отправитель, ручное подтверждение обработки, срок жизни у каждого кеша, порог утечек соединений |
| `manifest-check` | манифесты развёртывания | бюджет остановки, пауза перед ней, раздельные пробы, запуск не от суперпользователя |
| `test-lint` | тесты | ожидания и опрос в цикле, контейнер брокера в подготовке, подмена портов в интеграционном тесте |

Плюс структурные правила по языкам — 84 штуки, каждое названо по требованию,
которое закрывает: 68 архитектурных тестов в Java, 8 контрактов импортов
в Python, 8 правил зависимостей в Node.

**Если проверка в проекте не заведена**, требования, ссылающиеся на неё,
фактически держатся ревью. Ревью-скиллы это проверяют и сообщают отдельной
находкой.

**Правила чужих анализаторов** (`ruff`, `eslint`, `checkstyle`, `squawk`, …)
вынесены в каталоге отдельной таблицей — 120 имён в десяти инструментах. Имя,
которого нет в пинуемой версии, делает требование ложно закрытым: сверьте
таблицу со своими конфигами прежде, чем опираться на такой гейт. Имена правил
линтера миграций помечены как несверенные.

## Workflow: как пользоваться скиллами

Скиллы UCP — атомарные операции «сделай один артефакт по правилам». Для небольших задач этого хватает: открыл `ucp-pattern-design`, описал команду, получил `UseCase + Handler + контроллер`. Для **целого сервиса от спеки до прода** нужен оркестратор — эту роль играет [плагин `superpowers`](https://github.com/anthropics/skills/tree/main/skills/superpowers).

```
1. ИНПУТ — спецификация
   ucp-spec-design                              (если спеки ещё нет)
   ucp-spec-change                              (если спека есть и меняется контракт)
   ucp-spec-review / ucp-spec-change-review     (валидация дизайна — до кода!)
      ▸ замечания → правки → review (fast) → 0 Критично

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
          ucp-caching-design                    (Spring Cache + Redis: CacheManager, TTL, @Cacheable, invalidation)
          ucp-kafka-design                      (Kafka producer/consumer: idempotent, outbox, retry-topic, eventId-dedup)
          ucp-observability-design              (logging JSON + Micrometer + OTel + Actuator + MDC + TaskDecorator)
          ucp-cqrs-design                       (Command/Query маркеры, ViewRepository, read-model, sync через outbox)
          ucp-hexagonal-design                  (multi-module skeleton core/adapter/bootstrap + ArchUnit-тесты)
          ucp-distributed-design                (saga, idempotency, compensation, без 2PC/JTA)
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
   ucp-caching-review                           (при ревью CacheConfig, @Cacheable / @CacheEvict, application.yml cache-блок)
   ucp-kafka-review                             (при ревью KafkaListener, KafkaConfig, application.yml kafka-блок, outbox-relay)
   ucp-observability-review                     (при ревью logback-spring.xml, MdcFilter, MetricsConfig, application.yml management.*)
   ucp-cqrs-review                              (при ревью Command/Query handler-классов, ViewRepository, read-model, outbox-sync)
   ucp-hexagonal-review                         (при ревью multi-module gradle, core/adapter направления зависимостей, ArchUnit)
   ucp-distributed-review                       (при ревью saga, idempotency, compensation, multi-datasource configs)
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
- `ucp-spec-change` ↔ `ucp-spec-change-review` (изменение живущей спеки: причина, класс, миграция, слияние в спеку и архив)
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
- `ucp-caching-design` ↔ `ucp-caching-review` (Spring Cache + Redis: CacheManager, ключи, TTL, invalidation, паттерны, stampede)
- `ucp-kafka-design` ↔ `ucp-kafka-review` (Kafka producer/consumer: idempotent, outbox publishing, retry-topic+DLQ, idempotent consumer, event design)
- `ucp-observability-design` ↔ `ucp-observability-review` (logging structured JSON + Micrometer metrics + OpenTelemetry tracing + Actuator health + MDC propagation + SLO)
- `ucp-cqrs-design` ↔ `ucp-cqrs-review` (Command/Query разделение, ViewRepository, read-model, sync через outbox)
- `ucp-hexagonal-design` ↔ `ucp-hexagonal-review` (multi-module gradle layout, core без Spring/JOOQ, ports в core, ArchUnit-тесты)
- `ucp-distributed-design` ↔ `ucp-distributed-review` (saga orchestration/choreography, idempotency, compensation, запрет 2PC/JTA)
- `ucp-bootstrap-design`, `ucp-test-design`, `ucp-java-style-review`, `ucp-pg-explain-review` — без пары

**`ucp-pg-schema-review` — обязательный шаг ПРОВЕРКИ.** Любой PR, который трогает DDL (`db/changelog/**`, `db/migration/**`, `*.sql` с `CREATE TABLE`/`ALTER TABLE`), должен пройти через `ucp-pg-schema-review` до code-review. Скилл проверяет типы (`PG-T-NNN`): `bigint IDENTITY` для PK, `timestamptz` для бизнес-времени, `numeric(p,s)` для денег, `uuid` для UUID, антипаттерны (`varchar(255)`, `varchar(36)`, `float` для денег, `timestamp` без TZ). Без этого ревью DDL не уходит в merge.

**После выкатки — регресс.** `ucp-e2e-pipeline-design` заводит смоук, который
идёт после каждого деплоя и блокирует продвижение сборки, и полный регресс по
расписанию. Набор растёт не по интуиции: каждый инцидент закрывается сценарием
через `ucp-e2e-regression-grow`, и сценарий обязан падать на неисправленном коде.

**Frontend-трек — другая механика.** Своих правил у трека нет: источник правды —
`openspec/specs` в шаблоне проекта (`<репозиторий шаблонов фронтенда>`, шаблон `next-ssr`).
Скиллы читают требования оттуда, поэтому цепочка короче:

```
1. ЗАДАЧА
   ucp-fe-new-project        (проект из шаблона: выбор, старт, демо, гейты)
   ucp-fe-screen-design      (экран/маршрут)
   ucp-fe-form-design        (форма + серверное действие)
   ucp-fe-service-design     (доступ к данным)
   ucp-fe-auth-design        (вход, сессия, защита маршрутов)
   ucp-fe-test-design        (тесты)

2. РЕВЬЮ — по областям openspec, каждая своим скиллом
   ucp-fe-architecture-review · ucp-fe-api-review · ucp-fe-auth-review
   ucp-fe-design-system-review · ucp-fe-content-review
   ucp-fe-test-review · ucp-fe-tooling-review
```

Если в проекте нет каталога `openspec/`, скиллы говорят об этом прямо и не
подставляют правила из головы: проверять нечем — это находка, а не мелочь.

**Когда нужна вся связка:** новый сервис с нуля, миграция с классической слоёной архитектуры на UCP, большой рефакторинг с переходом на новый Tier.

**Когда `superpowers` избыточен:** одна операция, один UseCase, добавить эндпоинт в существующий сервис. Дёргай `ucp-*-design` напрямую. Но `ucp-pg-schema-review` всё равно вызывай, если меняется DDL.

`superpowers` ставится отдельно (см. [skills marketplace](https://github.com/anthropics/skills)), не зависит от этого репозитория.

## Скиллы

### `/ucp-api-review`

Ревью REST API контракта или кода на соответствие требованиям `rest-api/*` (`.claude/docs/backend/rest-api/spec.md`).

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

Проектирование новых REST API эндпоинтов по требованиям `rest-api/*`. Генерирует OpenAPI-спеку и заметки по реализации.

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

Ревью доменного кода на соответствие тактическим паттернам DDD (`.claude/docs/backend/ddd-tactical/spec.md`, примеры — `references/java/`) и корректное использование библиотеки [`ddd-building-blocks`](https://github.com/remodov/ddd-building-blocks).

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

Ревью Java/Spring-кода на соответствие методологии Use Case Pattern (`.claude/docs/backend/usecase-pattern/spec.md`) и корректное использование библиотеки [`usecase-pattern`](https://github.com/remodov/usecase-pattern).

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

Написание Use Case спецификации (требования `spec-format/*`, скелеты — `.claude/docs/shared/spec-format/references/`) сервиса по бизнес-описанию. Сам определяет нужный Tier (A — классическая слоёная, B — UCP L1–2, C — DDD/Hexagonal) и заполняет 16 разделов с правильной глубиной.

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

### `/ucp-spec-change` · `/ucp-spec-change-review`

Спека описывает контекст **как есть сейчас**. Правка её напрямую даёт результат, но не оставляет причины — через полгода никто не помнит, почему статус меняется именно так. Пара ведёт изменение живущего сервиса отдельным артефактом: он живёт, пока изменение делается, вливается в спеку и уходит в архив. Формат — `.claude/docs/shared/spec-change/spec.md`, коды ревью — `SC-*`.

**Что проверяет ревью:** есть ли причина, а не пересказ решения (`SC-WHY`); полнота «было → станет» по всем затронутым разделам, не только очевидному (`SC-DIFF`); класс изменения `compatible` / `breaking` / `semantic-break` и поимённые потребители (`SC-IMP`); expand-contract и `vN+1` для событий (`SC-MIG`); задачи вертикальными срезами со ссылкой на скилл (`SC-TASK`); приёмка GWT (`SC-ACR`); готовность к слиянию (`SC-MRG`).

**Использование:**

```
/ucp-spec-change Отмена заказа после отгрузки  # написать документ изменения
/ucp-spec-change-review                        # гейт перед реализацией
/ucp-spec-change-review merge                  # гейт перед слиянием
/ucp-spec-change merge                         # влить в спеку и заархивировать
```

**Типичный цикл:**

```
ucp-spec-change (propose)  →  docs/spec/changes/<дата>-<slug>.md
                                        ↓
                            ucp-spec-change-review
                                        ↓
                    design-скиллы по разделу «Задачи» → реализация
                                        ↓
                    ucp-spec-change-review merge → ucp-spec-change merge
                                        ↓
                            спека обновлена, документ в changes/archive/
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

Ревью Java-кода на соответствие требованиям домена `java-style` (`.claude/docs/backend/java/java-style/spec.md`) — именование, импорты, выражения, отступы. Каждое нарушение цитируется идентификатором требования (`java-style/no-star-imports`), код правила (`JS-2.5`) — рядом.

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

Ревью persistence-слоя (модуль `persistence/`) на соответствие требованиям домена `jooq` (`.claude/docs/backend/java/jooq/spec.md`) — repository-pattern, multiset, фильтры, маппинг record↔domain, SelectMode, view-репозитории, transaction boundaries. Каждое нарушение цитируется идентификатором требования; старый код правила — в поле **Код**.

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

Ревью защиты сервиса от отказов внешних систем на соответствие требованиям домена `resilience` (`.claude/docs/backend/resilience/spec.md`) — timeouts, circuit breaker, retry, bulkhead, fallback, health checks, связка с OpenAPI generator. Каждое нарушение цитируется идентификатором требования; старый код правила — в поле **Код**.

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

Генерирует **полный скелет outbound-интеграции** с новой внешней системой под требования `resilience/*`. Создаёт:
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

**Парный к `/ucp-jooq-review`.** Генерирует persistence-слой на jOOQ из доменного `<X>Repository` интерфейса под требования `jooq/*`. Создаёт:
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

**Парный к `/ucp-pg-schema-review`.** Генерирует Liquibase changeset (YAML) для нового агрегата под требования `pg-types/*` (коды `PG-T-*`) и `pg-naming/*` (`PG-N-*`):
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

**Парный к `/ucp-pg-migration-review`.** Генерирует **безопасные** expand-contract Liquibase changeset'ы для типовых breaking changes по требованиям `pg-migrations/*` (коды `PG-M-*`):
- `RENAME COLUMN` — 3 фазы (add new + sync trigger → deploy code → drop trigger + drop old).
- `ALTER TYPE` — 2-3 фазы через теневую колонку + swap.
- `ADD CONSTRAINT FK` — 2 фазы (`NOT VALID` + отдельный `VALIDATE`).
- `SET NOT NULL` — через `CHECK NOT VALID + VALIDATE + SET NOT NULL` (PG12+).
- `CREATE INDEX` — `CONCURRENTLY` + `runInTransaction: false` + `VACUUM` после.
- Удаление значения enum — через теневой тип.

Каждая phase имеет `SET LOCAL lock_timeout = '3s'`. Все операции обеспечивают **N-1 совместимость** (миграция работает с предыдущей версией кода). Без down-rollback'ов: требования `pg-migrations/*` знают только forward fix, не rollback.

**Использование:**

```
/ucp-pg-migration-design RENAME COLUMN customer.email → primary_email
/ucp-pg-migration-design SET NOT NULL для order.confirmed_at, таблица 50M строк
/ucp-pg-migration-design Добавить FK order.customer_id → customer.id в проде
```

### `/ucp-pg-runtime-design`

**Парный к `/ucp-pg-runtime-review`.** Генерирует runtime-инфраструктуру для четырёх типовых PG-сценариев по требованиям `pg-runtime/*`:

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

Ревью валидации входных данных (Jakarta Validation) на соответствие требованиям домена `validation` (`.claude/docs/backend/validation/spec.md`) — где валидируем, какие constraints, custom-валидаторы, validation groups, cross-field, OpenAPI integration. Каждое нарушение цитируется идентификатором требования; старый код правила — в поле **Код**.

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

**Парный к `/ucp-validation-review`.** Генерирует кастомный Jakarta Validation constraint, validation group или cross-field-валидатор по требованиям `validation/*`:
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

### `/ucp-caching-review`

Ревью кеширования (Spring Cache + Redis) на соответствие требованиям домена `caching` (`.claude/docs/backend/caching/spec.md`) — где кешируем, конфигурация, ключи, TTL, invalidation, паттерны, stampede, observability. Каждое нарушение цитируется идентификатором требования; старый код правила — в поле **Код**.

**Что проверяет:**
- `@Cacheable` только на read-методах, не на write (`R-CACHE-WHERE-X1`); не на доменном агрегате целиком (`R-CACHE-WHERE-X2`); money-кеш с TTL ≤ 30s + строгий evict (`R-CACHE-WHERE-X3`).
- Конфигурация: `RedisCacheManager` (не `ConcurrentMapCacheManager` в проде); `GenericJackson2JsonRedisSerializer` (не JDK — security CVE); per-cache TTL через `withInitialCacheConfigurations`; `@EnableCaching` + явный CacheManager bean (иначе silent NoOp).
- Ключи: `cacheNames` slug per-entity; `key = "..."` SpEL явно для multi-arg методов; нет PII / токенов в plain-text.
- TTL: explicit, ≤ 24h для бизнес-данных, ≤ 30s для money.
- Invalidation: `@CacheEvict` на write-методах того же агрегата; `@Caching` композит для нескольких; `@EventListener + @CacheEvict` для domain-events; не `allEntries=true` без причины.
- Паттерны: cache-aside дефолт; write-through через `@CachePut`; refresh-ahead для hot keys; не write-behind для money; не mix паттернов в одном cache.
- Stampede: `sync=true` для local; distributed lock (Redisson) для Redis hot keys.
- Metrics: cache hit rate включён, не отключён.

Связь с `R-RES-FB-1` (Resilience): cache как fallback при отказе внешней системы — отдельная политика invalidation. Связь с `AUTH-16`: PII в кеше требует TTL и encryption.

**Использование:**

```
/ucp-caching-review                              # ревью изменений из git diff
/ucp-caching-review src/main/java/.../CacheConfig.java
/ucp-caching-review src/main/resources/application.yml
```

### `/ucp-caching-design`

**Парный к `/ucp-caching-review`.** Генерирует кеш-обвязку под требования `caching/*`:
- `CacheSettings` (`@ConfigurationProperties` + `@Validated`) с per-cache TTL.
- `CacheConfiguration` (`@Configuration` + `@EnableCaching`) с `RedisCacheManager` + `GenericJackson2JsonRedisSerializer` + `withInitialCacheConfigurations`.
- `application.yml` patch — `spring.data.redis.*`, `spring.cache.type: redis`, `cache.caches.<name>.ttl`.
- `@Cacheable` / `@CacheEvict` / `@CachePut` на конкретных методах с правильным `key` SpEL.
- `@EventListener + @CacheEvict` invalidator для domain-events (если есть).
- `@Scheduled` refresh-ahead для hot keys.

Решает по входным параметрам:
- **Тип данных** → TTL (static/profile/feature-flag/aggregation/money).
- **Money** → cache-aside с TTL ≤ 30s + явный evict; альтернатива «не кешировать вообще» если возможно.
- **Hot key** → refresh-ahead через `@Scheduled` каждые `TTL × 0.7`.
- **Доменный агрегат целиком** → отказ генерировать (`R-CACHE-WHERE-X2`); кешируй read-проекцию.

**Использование:**

```
/ucp-caching-design Кеш для UserProfile, TTL 15 мин, evict на UpdateProfile
/ucp-caching-design Refresh-ahead для top-100 продуктов, hot key
/ucp-caching-design Money-кеш для UserBalance, TTL 30s, evict на каждой charge
```

### `/ucp-kafka-review`

Ревью работы с Kafka на соответствие требованиям домена `kafka` (`.claude/docs/backend/kafka/spec.md`) — producer (idempotence, partition key), consumer (manual ack, idempotent dedup), outbox publishing, retry topic + DLQ, event design, security. Каждое нарушение цитируется идентификатором требования; старый код правила — в поле **Код**.

**Что проверяет:**
- Producer: `enable.idempotence: true`, `acks: all`, partition key явный (aggregate id), `KafkaTemplate.send` НЕ из `@Transactional` с DB-операцией.
- Consumer: уникальный `groupId` per-purpose, manual ack (`MANUAL_IMMEDIATE`), `auto-offset-reset: earliest` для critical, idempotent через `processed_event` таблицу, нет `Thread.sleep`, HTTP-вызовы под `@CircuitBreaker`.
- Outbox publishing: domain events через outbox-relay, не `@TransactionalEventListener` напрямую; `outbox_event` с partial-индексом `WHERE published_at IS NULL`.
- Retry topic + DLQ: `@RetryableTopic` с явным max-attempts, `@DltHandler`, retry только на transient (5xx/IOException), не на 4xx/runtime; alert на DLQ-size.
- Event design: имя в past tense (`OrderConfirmed`, не `ConfirmOrder`), `eventId` UUID v7, версионированный `eventType.v1`, без PII в широковещательных топиках.
- Конфигурация: `@Validated KafkaSettings`, `spring.json.trusted.packages` explicit (не `*`), `missing-topics-fatal: true`, env-substitution для `bootstrap-servers`.
- Security: TLS/SASL для прода, ACL'ы per-сервис, PII через restricted-topic.
- Observability: consumer lag alerts, OTel `traceparent` через headers.

Связь с `PG-L-021` (outbox-relay через SKIP LOCKED), `AUTH-19` (money через Idempotency-Key + eventId двойная защита), `R-EVT-*` (DDD: domain events).

**Использование:**

```
/ucp-kafka-review                                # ревью изменений из git diff
/ucp-kafka-review src/main/java/.../OrderConfirmedListener.java
/ucp-kafka-review src/main/resources/application.yml
```

### `/ucp-kafka-design`

**Парный к `/ucp-kafka-review`.** Генерирует Kafka-обвязку под требования `kafka/*`:
- `KafkaSettings` (`@ConfigurationProperties` + `@Validated`) с topics + retry-policy.
- `application.yml` patch — producer/consumer/listener с правильными defaults (idempotent, manual-ack, trusted-packages explicit).
- Event-record в `core/<bc>/domain/event/` — `record OrderConfirmedEvent` с `eventId` UUID v7, `eventType` версионированный, `aggregateType`/`aggregateId`, бизнес-полями.
- Producer через outbox (домен) или direct (только для технических audit/metrics).
- Consumer (`@KafkaListener` + `@RetryableTopic` + `@DltHandler`) с idempotent-dedup через `processed_event` таблицу.
- DDL `processed_event` (Liquibase YAML).
- Custom exception hierarchy (`RetryableException` / `NonRetryableException`).

Решает по входным параметрам:
- **Domain event** → outbox publishing (не direct send из `@Transactional`).
- **Money / critical** → двойная защита (eventId + Idempotency-Key для downstream HTTP).
- **Long-running consumer task** → выделить в task-queue вместо blocking listener.
- **Topic name** — конвенция `<service>.<aggregate>.<event-name>`.

Зависит от `ucp-pg-runtime-design` для outbox-relay реализации (отдельный сценарий) и `ucp-ddd-tactical-design` для domain events.

**Использование:**

```
/ucp-kafka-design Producer для OrderConfirmedEvent через outbox
/ucp-kafka-design Listener billing-service на orders.confirmed с retry-topic
/ucp-kafka-design Event-driven flow для PaymentFailed → notification
```

### `/ucp-observability-review`

Ревью наблюдаемости на соответствие требованиям домена `observability` (`.claude/docs/backend/observability/spec.md`) — structured logging с MDC, Micrometer-метрики, OpenTelemetry tracing, Actuator health, context propagation, SLO. Каждое нарушение цитируется идентификатором требования; старый код правила — в поле **Код**.

**Что проверяет:**
- Logging: JSON в проде, `@Slf4j` через Lombok, `{}`-placeholders (не string-concat), правильные log-уровни, MDC fields в каждой записи, **PII запрещены** (см. `AUTH-16`), нет `System.out`/`printStackTrace`, ERROR с stack trace.
- Metrics: Micrometer + Prometheus registry; стандартизованные dimensions (service/env/version) через `management.metrics.tags`; RED/USE auto; custom business metrics через MeterRegistry; **низкая cardinality tags** (не user_id/request_id — Prometheus OOM).
- Tracing: OTel автоинструментация; `traceparent` propagation; manual spans с try-finally; span attributes без PII; **sampling 1-10%** (не 100% в проде); `traceId` в MDC.
- Health: separate liveness/readiness; custom HealthIndicator с TTL; нет business-state; **liveness не зависит от внешних** (иначе K8s restart loop).
- Config: отдельный management port; exposure explicit list (не `*`); не exposed `/actuator/env` без auth.
- Context: MdcFilter с **обязательным `MDC.clear()` в finally** (без него — leaked context cross-request); TaskDecorator для `@Async` (иначе traces разрываются).
- SLO: defined для critical endpoints; multi-window burn-rate alerts; error budget; alerts с runbook'ами.

Связь с `R-RES-OBS-*` (Resilience metrics), `R-CACHE-OBS-*` (Cache hit rate), `R-KFK-OBS-*` (Kafka lag), `AUTH-16` (PII), `R-HDR-4` (traceparent).

**Использование:**

```
/ucp-observability-review                       # ревью изменений из git diff
/ucp-observability-review src/main/java/.../MdcFilter.java
/ucp-observability-review src/main/resources/logback-spring.xml
/ucp-observability-review src/main/resources/application.yml
```

### `/ucp-observability-design`

**Парный к `/ucp-observability-review`.** Генерирует observability-инфраструктуру под требования `observability/*`:
- `logback-spring.xml` с двумя профилями (text dev / JSON prod через `LogstashEncoder`).
- `application.yml` patch — `management.*` (отдельный port, explicit exposure, стандартизованные tags, liveness/readiness probes), `otel.*` (sampling 10%, OTLP endpoint), `logging.*`.
- `MdcFilter` (Spring `@Component` + `OncePerRequestFilter`) с `MDC.clear()` в `finally`.
- `UserIdMdcFilter` (если есть Spring Security) — populates `userId` после JWT.
- `AsyncConfig` с `TaskDecorator` для MDC propagation в `@Async` / `CompletableFuture`.
- Custom business metrics через MeterRegistry (если требуются — Counter/Timer/DistributionSummary).
- `git-commit-id-plugin` + `springBoot.buildInfo()` для `/actuator/info`.
- Зависимости: `spring-boot-starter-actuator`, `micrometer-registry-prometheus`, `opentelemetry-spring-boot-starter`, `opentelemetry-logback-mdc-1.0`, `logstash-logback-encoder`.

Решает по входным параметрам:
- **Tracing backend** (Jaeger/Tempo/Datadog) → `otel.exporter.otlp.endpoint`.
- **Logging backend** (Loki/ELK/Datadog) → `LogstashEncoder` (универсальный) или `EcsEncoder` (Elastic).
- **Sampling rate** — 10% дефолт; для money/critical — выше.
- **Custom business metrics** — нужны или нет.

**Использование:**

```
/ucp-observability-design Настрой observability в order-service
/ucp-observability-design Только MdcFilter и TaskDecorator (logging уже есть)
/ucp-observability-design Backend: Loki + Tempo + Prometheus, sampling 5%
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

Ревью кода на соответствие паттернам авторизации (`.claude/docs/backend/auth-patterns/spec.md`) — JWT + RBAC + ABAC + S2S + audit + PII / секреты + идемпотентность. Каждое нарушение цитируется идентификатором требования, код правила (`AUTH-9`) — рядом.

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

Проектирование интеграционных и unit-тестов под стратегию тестов (`.claude/docs/backend/java/test-strategy/spec.md`): синхронные, только PostgreSQL + WireMock, без Kafka/Redis в базовом классе, события через in-memory publisher.

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

Ревью PostgreSQL-схемы и миграций (DDL Liquibase / Flyway / сырой SQL) против требований `pg-types/*` (коды `PG-T-NNN`).

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

Ревью индексов и плана запроса PostgreSQL против требований `pg-indexes/*` (коды `PG-I-NNN`, `PG-E-NNN`).

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

Ревью runtime-аспектов PostgreSQL против требований `pg-runtime/*` (коды `PG-W-NNN`, `PG-V-NNN`, `PG-L-NNN`).

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

Ревью PostgreSQL миграций (Liquibase / Flyway / сырой SQL) на безопасность для прода против требований `pg-migrations/*` (коды `PG-M-NNN`).

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

### Frontend-скиллы

Ставятся при `UCP_TRACK=frontend`. Design-скиллы разрезаны **по задачам**
(экран, форма, доступ к данным, вход, тесты), review-скиллы — **по областям
openspec** шаблона, чтобы находка ссылалась на требование, которое живёт
в проекте, а не в этом репозитории.

| Скилл | О чём |
| --- | --- |
| `/ucp-fe-new-project` | завести проект из шаблона: выбор шаблона, `new-project.sh`, `demo:remove`, первый прогон гейтов |
| `/ucp-fe-screen-design` | экран или маршрут: серверные и клиентские компоненты, состояния загрузки и ошибки |
| `/ucp-fe-form-design` | форма: схема данных, серверное действие, ошибки полей |
| `/ucp-fe-service-design` | доступ к данным: слой сервисов, кеширование, поведение при отказе |
| `/ucp-fe-auth-design` | вход, сессия, защита маршрутов |
| `/ucp-fe-test-design` | тесты по областям openspec |
| `/ucp-fe-architecture-review` | структура слоёв, границы модулей, направления импортов |
| `/ucp-fe-api-review` | клиент API, работа с данными, обработка отказов |
| `/ucp-fe-auth-review` | аутентификация и доступ |
| `/ucp-fe-design-system-review` | компоненты и оформление |
| `/ucp-fe-content-review` | тексты, локализация, доступность |
| `/ucp-fe-test-review` | тесты |
| `/ucp-fe-tooling-review` | сборка, линтеры, окружение |

**Использование:**

```
/ucp-fe-new-project Админка для операторов
/ucp-fe-screen-design Список заказов с фильтром по статусу
/ucp-fe-form-design Форма оформления заказа
/ucp-fe-architecture-review          # из git diff
/ucp-fe-api-review src/services/
```

### e2e-скиллы

Ставятся при `UCP_TRACK=e2e`. Трек отвечает на два вопроса, которые обычно
нигде не записаны: что происходит сразу после деплоя и откуда в регрессе
берутся новые сценарии.

| Скилл | О чём |
| --- | --- |
| `/ucp-e2e-design` | сценарии по спеке сервиса: бизнес-пути, свои данные, устойчивые селекторы, разметка на смоук и регресс |
| `/ucp-e2e-pipeline-design` | прогон вокруг выкатки: смоук после деплоя с блокировкой продвижения, регресс по расписанию, карантин, отчёт с владельцем |
| `/ucp-e2e-regression-grow` | рост регресса по инцидентам: путь вместо симптома, сценарий, падающий на неисправленном коде |
| `/ucp-e2e-review` | ревью набора и конвейера, включая отсутствие джоб как отдельную находку |

**Использование:**

```
/ucp-e2e-design Оформление заказа с оплатой картой
/ucp-e2e-pipeline-design                       # завести смоук и ночной регресс
/ucp-e2e-regression-grow INC-482               # закрыть инцидент сценарием
/ucp-e2e-review e2e/                           # ревью набора
```

**Требования трека:** `e2e-suite/*` — из чего состоит набор; `e2e-pipeline/*` —
когда он гоняется и как растёт. Обе джобы (`ci:e2e-smoke`, `ci:e2e-regression`)
описаны в каталоге проверок `_meta/project-gates.md`.

## Подключение к проекту

Три способа, от простого к ручному. Все ставят только **нужный срез** (язык × специализация × профиль).

```bash
git clone https://github.com/remodov/usecase-pattern-skills.git ~/projects/claude-code-java
cd ~/projects/claude-code-java
```

#### A. Через Claude — диалогом (рекомендуется)

Скажите Claude в любой сессии: **«поставь UCP-скиллы в ./my-project»**. Скилл `ucp-install` сам определит язык и
специализацию из проекта (`pyproject.toml`→python, `build.gradle`→java, `go.mod`→go, …), подтвердит у вас, спросит
профиль и запустит установку с проверкой. Помнить env-переменные не нужно.

> Чтобы это работало в проекте, где скиллов ещё нет (холодный старт), поставьте `ucp-install` в личные скиллы один раз:
> ```bash
> ln -s ~/projects/claude-code-java/.claude/skills/ucp-install ~/.claude/skills/ucp-install
> ```

#### B. Интерактивный мастер (без Claude)

```bash
./install.sh --wizard         # спросит специализацию (track) → язык → профиль → каталог
```

#### C. Вручную через env-переменные

```bash
./install.sh ~/my-project                                    # срез по стеку проекта, backend, java (дефолты)
UCP_DESIGN=chain ./install.sh ~/my-project                   # review для всех concern'ов, design — только цепочка
UCP_CONCERNS_ON='caching' UCP_CONCERNS_OFF='cqrs' ./install.sh ~/p  # ручные поправки к auto-срезу
UCP_PROFILE=full ./install.sh ~/my-project                   # всё без детекта
UCP_LANG=python ./install.sh ~/my-svc                        # python-срез (FastAPI/SQLAlchemy/…)
UCP_LANG=python UCP_PROFILE=rest ./install.sh ~/my-svc       # python REST/UCP-сервис
UCP_PROFILE=data ./install.sh ~/my-java-project              # data-heavy: pg+persistence+caching+observability
UCP_TRACK=backend,e2e UCP_LANG=go ./install.sh ~/my-go-svc   # несколько специализаций
UCP_SKILLS='ucp-py-pattern-* ucp-py-api-*' ./install.sh ~/p  # произвольный набор (перекрывает профиль)
```

Оси установки (ортогональны, композируются):

| Переменная | Значения | Назначение |
|---|---|---|
| `UCP_TRACK` | `backend` (деф.) `frontend` `e2e` (список через запятую) | специализация — фильтр по frontmatter `track:`; `frontend` тянет `ucp-fe-*` |
| `UCP_LANG` | `java` (деф.) `python` `node` `go` | язык — фильтр скиллов по `lang:` и примеров по `<домен>/references/<lang>/` |
| `UCP_PROFILE` | `auto` (деф.) `full` `rest` `data` | `auto` — срез по стеку: concern включается по маркеру в проекте (таблица ниже); `rest`/`data` — фиксированные наборы, **lang-aware** |
| `UCP_DESIGN` | `all` (деф.) `chain` | в `auto`-срезе: design-скиллы для всех включённых concern'ов или только для цепочки `ucp-new-service`; review ставится всегда |
| `UCP_CONCERNS_ON` / `UCP_CONCERNS_OFF` | список через пробел | ручные поправки к `auto`-срезу; причина попадает в таблицу среза |
| `UCP_SKILLS` | глоб-список | произвольный набор, перекрывает `UCP_PROFILE` |

Срез `auto` считается по маркерам в build-файлах, исходниках и раскладке; результат пишется таблицей «Установленный срез»
в managed-блок `CLAUDE.md` (что стоит, что выключено и почему) и печатается в `--check`. Спеки всех доменов ставятся
независимо от среза — выключается только упакованный скилл, не правила.

| Concern | Маркер |
|---|---|
| pattern, ddd-tactical, bootstrap, test, style, error-handling, security, shutdown | всегда |
| spec | есть `docs/spec/`, или нет `openspec/` (проект на OpenSpec спековые скиллы не получает) |
| arch | `architecture/services/_registry.yaml` |
| hexagonal | модули `core/` и `*-adapter/` |
| api · validation · persistence · pg-* | web-стек / библиотека валидации / слой хранения / PostgreSQL и миграции |
| cqrs · kafka · scheduler · integration · resilience · auth · observability · caching · streaming | зависимость или класс-маркер (usecase-pattern, Kafka, ShedLock/`@Scheduled`, out-adapter или HTTP-клиент, Resilience4j, Spring Security/OAuth2, Micrometer/Actuator, Redis/Caffeine, Kafka Streams) |
| distributed · payment-integration · meta | только вручную через `UCP_CONCERNS_ON` |

Скрипт создаёт симлинки на `.claude/skills/*`, `.claude/docs/` и `.claude/rules/ucp-<lang>-core.md` — обновления в репо автоматически прилетят в проект.
При повторном запуске с другим срезом лишние ucp-симлинки чистятся (смена языка/трека корректна). `install.sh --check
<project>` — диагностика без модификаций.

После установки в проекте появятся:

- `.claude/skills/ucp-*/` — все скиллы (`ucp-pattern-review`, `ucp-api-design` и т.д.)
- `.claude/docs/**/spec.md` — корпус требований, который скиллы читают как input
- `.claude/docs/<домен>/references/` — примеры под выбранный язык
- `.claude/docs/_meta/project-gates.md` — каталог проверок, которые заводит bootstrap
- `.claude/rules/ucp-java-core.md` — **always-loaded ядро** языка: Claude Code грузит `.claude/rules/*.md` в каждую
  сессию, поэтому базовые решения (раскладка модулей, чистота core, команды и запросы, фабрики агрегатов,
  семейства исключений, источник времени) попадают в контекст без вызова скилла. Источник —
  `.claude/docs/backend/java/java-core.md`: выжимка ≤ 200 строк со ссылками на ID требований, новых правил не вводит

Python-тулинг корпуса (`spec_check.py` и соседи) в проект **не** ставится:
`install.sh` симлинкует только `*.md`.

Корпус требований — **инструментальный** документ, не часть проектной
документации. Поэтому он живёт под `.claude/docs/`, а не в пользовательской
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

### Хуки

`install.sh` ставит детерминированные обработчики событий в `.claude/hooks/`
проекта и регистрирует их в `.claude/settings.json`. Хуки выполняются на
стороне harness до модели — закрывают зазоры, где модель может проигнори-
ровать инструкцию из CLAUDE.md.

| Хук | Событие | Назначение |
|---|---|---|
| `ucp-session-check.sh` | `SessionStart` | Проверяет, что `ucp-*` симлинки не broken; если broken — инжектит warning с командой починки. |
| `ucp-trigger-detect.sh` | `UserPromptSubmit` | Ловит триггер-фразы цепочки (`«сделай сервис»`, `«пишем сервис»` и т.п.) и инжектит инструкцию запустить `/ucp-new-service`, чтобы модель не пошла писать код от руки. |
| `impl-task-detect.sh` | `UserPromptSubmit` | Гибридный детектор задач реализации (`«реализуй контроллер»`, `«добавь хендлер»`, `«напиши repository»` и т.п.). Pass 1 — regex; Pass 2 — Haiku-классификатор на «сомнительных» промптах с code-индикаторами. Инжектит reminder со списком `/ucp-*-design` скиллов + TDD. Срабатывает только в UCP-проектах. |
| `ucp-post-skill-review.sh` | `PostToolUse` (matcher: `Skill`) | После `ucp-pg-schema-design` / `ucp-pg-migration-design` напоминает запустить парный review (для DDL/миграций ревью обязателен). |

`install.sh --check` проверяет, что все 4 хука зарегистрированы в
`settings.json` проекта. Пользовательские хуки сохраняются — managed-блок
вычищает только наши `ucp-*.sh` / `impl-task-detect.sh` при reinstall.

Hook `impl-task-detect.sh` опционально вызывает `claude -p --model
claude-haiku-4-5` для классификации (Pass 2). Это +2-4с latency и
~$0.0001-0.001 на промпт, **только** когда Pass 1 промахнулся И в промпте
есть code-индикаторы. На большинстве промптов LLM не вызывается. Чтобы
отключить Pass 2 целиком — закомментируй последний `claude -p` блок в
`.claude/hooks/impl-task-detect.sh` (это симлинк, правка применится ко всем
проектам).

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
# backend/java-набор; для python — аналоги `ucp-py-<concern>-{design,review}`,
# node/go — пилот; frontend — 12 скиллов (ниже). Плюс тулинг: `ucp-install/`,
# `ucp-new-service/`. install.sh ставит срез по UCP_TRACK × UCP_LANG × UCP_PROFILE.
├── ucp-install/                    # установить/обновить UCP-скиллы в проект (диалогом)
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
├── ucp-pg-schema-design/   # Liquibase changeset для нового агрегата (pg-types/*, pg-naming/*)
├── ucp-pg-migration-design/ # expand-contract шаблоны для breaking changes (pg-migrations/*)
├── ucp-pg-runtime-design/  # outbox-relay, task-queue, advisory-lock, optimistic-lock (pg-runtime/*)
├── ucp-validation-review/  # ревью Jakarta Validation (validation/*)
├── ucp-validation-design/  # генерация custom constraints, groups, cross-field
├── ucp-caching-review/     # ревью Spring Cache + Redis (caching/*)
├── ucp-caching-design/     # генерация CacheManager, @Cacheable, @CacheEvict, refresh-ahead
├── ucp-kafka-review/       # ревью Kafka producer/consumer/outbox (kafka/*)
├── ucp-kafka-design/       # генерация Producer/Listener/Event/processed_event с idempotent-dedup и retry-topic
├── ucp-observability-review/  # ревью logging/metrics/tracing/health/MDC (observability/*)
├── ucp-observability-design/  # генерация Logback + Micrometer + OTel + Actuator + MdcFilter + TaskDecorator
├── ucp-cqrs-review/        # ревью CQRS-разделения (cqrs/*)
├── ucp-cqrs-design/        # генерация Command/Query + ViewRepository + read-model + sync
├── ucp-hexagonal-review/   # ревью Hexagonal multi-module layout (hexagonal/*)
├── ucp-hexagonal-design/   # генерация multi-module skeleton + ArchUnit-тесты
├── ucp-distributed-review/ # ревью distributed patterns (distributed-patterns/*)
├── ucp-distributed-design/ # генерация saga + idempotency-инфра + compensation
├── ucp-resilience-review/  # ревью защиты от отказов внешних систем (CB, retry, bulkhead, OpenAPI generator)
├── ucp-integration-design/ # генерация ПОЛНОГО скелета новой outbound-интеграции (port + client-generator + out-adapter)
├── ucp-resilience-design/  # миграция existing out-adapter под resilience/* (без создания модулей)
├── ucp-test-design/        # проектирование интеграционных и unit-тестов
├── ucp-auth-review/        # ревью авторизации (JWT, RBAC, ABAC, audit, PII)
├── ucp-auth-design/        # scaffold Spring Security + OAuth2 для UCP-сервиса
│
│   # e2e-трек (UCP_TRACK=e2e)
├── ucp-e2e-design/         # сценарии по спеке сервиса
├── ucp-e2e-pipeline-design/ # смоук после деплоя, регресс по расписанию, карантин
├── ucp-e2e-regression-grow/ # рост набора по инцидентам
├── ucp-e2e-review/         # ревью набора и конвейера
│
│   # frontend-трек (UCP_TRACK=frontend): правила берутся из openspec/specs шаблона
├── ucp-fe-new-project/     # проект из шаблона: выбор, старт, удаление демо, гейты
├── ucp-fe-screen-design/   # экран/маршрут: серверные и клиентские компоненты, состояния загрузки
├── ucp-fe-form-design/     # форма: схема, серверное действие, ошибки полей
├── ucp-fe-service-design/  # доступ к данным: слой сервисов, кеширование, обработка отказов
├── ucp-fe-auth-design/     # вход, сессия, защита маршрутов
├── ucp-fe-test-design/     # тесты по областям openspec
├── ucp-fe-architecture-review/  # структура слоёв и границы модулей
├── ucp-fe-api-review/      # клиент API и работа с данными
├── ucp-fe-auth-review/     # аутентификация и доступ
├── ucp-fe-design-system-review/ # компоненты и оформление
├── ucp-fe-content-review/  # тексты, локализация, доступность
├── ucp-fe-test-review/     # тесты
└── ucp-fe-tooling-review/  # сборка, линтеры, окружение

.claude/docs/
#
# Каждый домен — папка `<домен>/`:
#   <домен>/spec.md              — требования: SHALL / SHALL NOT + ID + Код + Гейт +
#                                  Покрытие + Не ловит + сценарии. Рабочий вход скиллов:
#                                  review цитирует ID, design сверяется по требованиям.
#   <домен>/references/          — реализация и примеры, читаются on-demand:
#                                  implementation.md (у кросс-языкового домена —
#                                  references/<lang>/implementation.md), recipes.md.
#                                  Имя файла фиксировано: домен уже в пути.
# Требование язык-нейтрально; язык различает только поле **Гейт** (`java: archunit:X ·
# python: ревью`) и каталог примеров. install.sh ставит spec.md всегда + references
# только выбранного UCP_LANG, и симлинкует только `*.md` — тулинг в проекты не уезжает.
# Языко-специфичные домены (java/jooq, python/sqlalchemy, *-style, *-bootstrap,
# *-test-strategy) лежат под `<lang>/` и references не разделяют.
├── backend/rest-api/              # REST API: URL, методы, ответы, ошибки, OpenAPI
├── backend/usecase-pattern/       # Use Case Pattern: UseCase, Handler, слои
├── backend/ddd-tactical/          # тактические паттерны DDD: сущность, агрегат, VO, событие
├── backend/java/jooq/             # jOOQ: конфигурация, репозиторий, multiset, фильтры
├── backend/resilience/            # защита от отказов: CB, retry, bulkhead, fallback
├── backend/validation/            # валидация входных данных
├── backend/caching/               # кеширование: ключи, TTL, инвалидация, stampede
├── backend/kafka/                 # Kafka: producer, consumer, outbox, retry-topic
├── backend/observability/         # журналы, метрики, трассировка, health, SLO
├── backend/cqrs/                  # CQRS: команды, запросы, read-model, синхронизация
├── backend/hexagonal/             # многомодульная раскладка, направления зависимостей
├── backend/distributed-patterns/  # saga, идемпотентность, компенсации, запрет 2PC
├── backend/error-handling/        # иерархия ошибок, где ловим, как отображаем
├── backend/graceful-shutdown/     # корректное завершение: HTTP, Kafka, БД, планировщик
├── backend/security/              # SAST, зависимости, секреты, образы, криптография
├── backend/scheduler/             # планировщик задач
├── backend/streaming/             # потоковая обработка
├── backend/payment-integration/   # платёжная интеграция
├── backend/auth-patterns/         # авторизация: JWT, RBAC, ABAC, S2S, audit, PII
├── backend/pg-types/              # PostgreSQL: типы
├── backend/pg-naming/             # PostgreSQL: нейминг
├── backend/pg-indexes/            # PostgreSQL: индексы и план запроса
├── backend/pg-partitioning/       # PostgreSQL: партиционирование
├── backend/pg-migrations/         # PostgreSQL: миграции expand-contract
├── backend/pg-runtime/            # PostgreSQL: транзакции, блокировки, пул, изоляция
├── backend/java/{java-style,spring-bootstrap,test-strategy}/
├── backend/python/{python-style,python-bootstrap,python-test-strategy,sqlalchemy,async,codegen}/
├── backend/node/{node-style,nest-bootstrap,node-test-strategy,typeorm}/
├── backend/go/{go-style,go-bootstrap,go-test-strategy,sqlc}/
├── shared/arch/                   # платформенная согласованность
├── frontend/_index.md             # тонкая привязка: правила — в openspec/specs шаблона
├── _meta/authoring-contract.md    # контракт на форму требования (как писать)
├── _meta/project-gates.md         # каталог проверок, которые заводит bootstrap
├── _meta/rule-code-registry.md    # карта «старый код → ID требования»
├── _meta/migrated-domains.md      # реестр доменов в форме spec.md
├── shared/review-format/          # формат находки и протокол локализации
├── shared/spec-format/            # формат Use Case спецификации + скелеты разделов
└── shared/spec-change/            # формат изменения живущей спеки
```

### Шаблоны

Заготовки под форму требований — в `templates/openspec/`:

| Файл | Когда берут |
| --- | --- |
| `domain-spec.md` | новый домен корпуса — копируется в `.claude/docs/<трек>/<домен>/spec.md` |
| `requirement.md` | требование в существующий `spec.md` — вставляется блоком |
| `change/proposal.md` + `change/tasks.md` | изменение отдельным артефактом — каталог `openspec/changes/<id>/` |

`domain-spec.md` — валидный документ, а не набор скобок: он целиком проходит
`spec_check`, и тест следит, чтобы проходил и дальше. Форма и раскладка те же,
что в `<репозиторий шаблонов фронтенда>` (`templates/next-ssr/openspec/`), — трек
меняется, стиль требования нет.

### Тулинг корпуса

Живёт в `_meta/` самого репозитория и в проекты не устанавливается:

| Команда | Что делает |
| --- | --- |
| `python3 .claude/docs/_meta/spec_check.py` | гейт корпуса: форма требований, уникальность ID и кодов, согласованность реестров, мёртвые ссылки, гейты вне каталога |
| `python3 .claude/docs/_meta/spec_sync.py` | перегенерирует сводные таблицы в `_index.md` и `rule-code-registry.md` |
| `python3 .claude/docs/_meta/check-shared-neutral.py` | ловит framework-специфичные токены в язык-нейтральном тексте |
| `python3 tools/fe_audit.py <клон frontend-templates>` | сверяет скиллы фронта с эталонным репозиторием: живые ссылки на требования, покрытие областей |
| `python3 -m unittest discover -s tools/tests` | 85 тестов: тулинг, шаблоны, числа в README, сверка с фронт-шаблонами |

Все три проверки прогоняются в CI (`.gitlab-ci.yml`). Правило про гейты
рекурсивно: собственная проверка, не описанная в `_meta/project-gates.md`,
роняет `spec_check` — иначе имена гейтов расходятся с реальностью так же
незаметно, как имена правил чужих анализаторов.


## Связанные библиотеки

- [`ddd-building-blocks`](https://github.com/remodov/ddd-building-blocks) — Java-библиотека базовых DDD-абстракций, на которой опираются скиллы DDD.
- [`usecase-pattern`](https://github.com/remodov/usecase-pattern) — Java-библиотека UseCase / UseCaseHandler / UseCaseDispatcher.
- [`hexagonal-architecture`](https://github.com/remodov/hexagonal-architecture) — Java-библиотека для Hexagonal-разделения (`core` ↔ `adapter-in/out`) на Уровне 4.

Все основные домены покрыты. Дальнейшее расширение — по конкретным запросам команды.

## Лицензия

MIT
