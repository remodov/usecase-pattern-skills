# claude-code-java

Скиллы (slash-команды) для Claude Code по методологии Use Case Pattern. Каждый скилл — компактный чек-лист для агента; полные style-guide-снапшоты лежат в `.claude/docs/*.md`.

## Принцип

- **`.claude/docs/*.md` — единственный источник правды.** Скиллы цитируют коды правил (`R-UC-1`, `JS-4.7`, `AUTH-15` и т.д.), агент читает соответствующий гайд при работе.
- **Скиллы** — короткие инструкции для агента: что проверить, как отчитаться.

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

Написание Use Case спецификации (`.claude/docs/usecase-spec-template.md`) сервиса по бизнес-описанию. Сама определяет нужный Tier (A — legacy, B — UCP L1–2, C — DDD/Hexagonal) и заполняет 16 разделов с правильной глубиной.

**Что генерирует:**
- Папка `docs/spec/` с **split-файлами** — один `.md` на каждый из 16 разделов плюс консолидированный `<service>.md` для шаринга. Это инвариант — single-file спеки скилл больше не делает.
- 16 разделов: Bounded Context, глоссарий, доменная модель, состояния, роли, бизнес-правила, команды, события, queries, use cases, UI, саги, ошибки, интеграции, критерии приёмки, НФТ
- Frontmatter с `tier`, `service`, `last_updated`
- Кросс-ссылки между разделами (BR ↔ commands ↔ errors)

**Использование:**

```
/ucp-spec-design Сервис заказов: бизнес-описание в docs/case.md
/ucp-spec-design Tier C, Order Service, см. case.md и текущие агрегаты в src/
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

## Workflow: маленькая задача vs целый сервис

Скиллы UCP — атомарные операции «сделай один артефакт по правилам». Для
небольших задач этого хватает: открыл `ucp-pattern-design`, описал команду,
получил `UseCase + Handler + контроллер`. Дальше человек читает результат и
коммитит.

Для **целого сервиса от спеки до прода** одних `ucp-*`-скиллов мало — нужен
оркестратор, который держит контекст плана между шагами и не теряет инварианты.
Эту роль играет [плагин `superpowers`](https://github.com/anthropics/skills/tree/main/skills/superpowers).
`superpowers` ничего не знает про UCP — это general-purpose дисциплина «брейнсторм → план →
исполни → проверь → закрой». UCP-скиллы ничего не знают про `superpowers` — они умеют
делать ровно один артефакт. Когда они встречаются, получается полный pipeline.

```
1. ИНПУТ — спецификация
   ucp-spec-design                              (если спеки ещё нет)

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
          ucp-test-design                       (тесты на UC + BR)
   superpowers:test-driven-development          (TDD-дисциплина по ходу)
   superpowers:subagent-driven-development      (параллельно независимые шаги)

4. ПРОВЕРКА
   superpowers:verification-before-completion   (compileJava, test — всё зелёное)
   ucp-pattern-review + ucp-api-review +        (методология)
   ucp-ddd-tactical-review + ucp-java-style-review + ucp-auth-review
   superpowers:requesting-code-review           (внешний review)

5. ЗАВЕРШЕНИЕ
   superpowers:using-git-worktrees              (изоляция от main)
   superpowers:finishing-a-development-branch
```

**Когда нужна связка:** новый сервис с нуля, миграция с легаси на UCP, большой
рефакторинг с переходом на новый Tier. Везде, где «забыть шаг» = баг в проде.

**Когда `superpowers` оверкилл:** одна операция, один UseCase, добавить
endpoint в существующий сервис. Дёргайте `ucp-*-design` напрямую без
оркестратора.

`superpowers` ставится отдельно (см. [skills marketplace](https://github.com/anthropics/skills)),
не зависит от этого репозитория и нужен только когда требуется orchestration.

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

Скилл `ucp-spec-design` опционально использует:

- **`superpowers`** — для общих практик планирования и работы с TodoWrite.
  Установка: `claude plugins install superpowers`
- **`context7`** (MCP) — для подтягивания актуальной документации библиотек
  (Spring Boot, jOOQ и т.п.) в выходную спеку.
  Установка: `claude mcp add context7`

Без них `ucp-spec-design` всё равно работает — просто без TodoWrite-планирования
и без проверки актуальности версий библиотек. Остальные 11 скиллов их не
требуют вообще.

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
├── ucp-test-design/        # проектирование интеграционных и unit-тестов
├── ucp-auth-review/        # ревью авторизации (JWT, RBAC, ABAC, audit, PII)
└── ucp-auth-design/        # scaffold Spring Security + OAuth2 для UCP-сервиса

.claude/docs/
├── rest-api-style-guide.md          # REST API Style Guide
├── usecase-pattern-style-guide.md   # Use Case Pattern
├── ddd-tactical-style-guide.md      # тактические паттерны DDD
├── usecase-spec-template.md         # шаблон Use Case спецификации
├── java-style-guide.md              # Java Style Guide
├── test-strategy.md                 # стратегия тестов
└── auth-patterns-style-guide.md     # паттерны авторизации
```

## Связанные библиотеки

- [`ddd-building-blocks`](https://gitlab.mosmetro.tech/common/ddd-building-blocks) — Java-библиотека базовых DDD-абстракций, на которой опираются скиллы DDD.
- [`usecase-pattern`](https://gitlab.mosmetro.tech/common/usecase-pattern) — Java-библиотека UseCase / UseCaseHandler / UseCaseDispatcher.
- [`hexagonal-architecture`](https://gitlab.mosmetro.tech/common/hexagonal-architecture) — Java-библиотека для Hexagonal-разделения (`core` ↔ `adapter-in/out`) на Уровне 4.

В планах — скиллы для CQRS, Hexagonal, Distributed Patterns, Resilience, Kafka.

## Лицензия

MIT
