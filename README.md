# usecase-pattern-skills

Скиллы (slash-команды) для Claude Code, привязанные к статьям [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/) о методологии Use Case Pattern. Каждый скилл — компактный чек-лист для агента; полное описание правил с диаграммами и примерами — на сайте.

## Принцип

- **Сайт vikulin-va.ru — единственный источник истины.** Если правила в скилле и в статье расходятся, прав сайт.
- **Локальный `docs/*.md`** — снапшот соответствующей статьи (агент читает его быстро, без сетевого вызова).
- **Скиллы** — короткие инструкции для агента: что проверить, как отчитаться.

## Скиллы

### `/ucp-api-review`

Ревью REST API контракта или кода на соответствие [REST API Style Guide](https://vikulin-va.ru/rest-api-style-guide/).

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

Ревью доменного кода на соответствие [тактическим паттернам DDD](https://vikulin-va.ru/domain-driven-design/tactical-patterns/) и корректное использование библиотеки [`ddd-building-blocks`](https://github.com/remodov/ddd-building-blocks).

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

Ревью Java/Spring-кода на соответствие [методологии Use Case Pattern](https://vikulin-va.ru/use-case-pattern/) и корректное использование библиотеки [`usecase-pattern`](https://github.com/remodov/usecase-pattern).

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

Написание [Use Case спецификации](https://vikulin-va.ru/use-case-pattern/spec-template/) сервиса по бизнес-описанию. Сама определяет нужный Tier (A — legacy, B — UCP L1–2, C — DDD/Hexagonal) и заполняет 16 разделов с правильной глубиной.

**Что генерирует:**
- Markdown-файл спеки в `docs/spec.md`
- 16 разделов: Bounded Context, глоссарий, доменная модель, состояния, роли, бизнес-правила, команды, события, queries, use cases, UI, саги, ошибки, интеграции, критерии приёмки, НФТ
- Frontmatter с `tier`, `service`, `last_updated`
- Кросс-ссылки между разделами (BR ↔ commands ↔ errors)

**Использование:**

```
/ucp-spec-design Сервис заказов: бизнес-описание в docs/case.md
/ucp-spec-design Tier C, Order Service, см. case.md и текущие агрегаты в src/
```

### `/ucp-java-style-review`

Ревью Java-кода на соответствие [Java Style Guide](https://vikulin-va.ru/java-style-guide/) — именование, импорты, выражения, отступы. Каждое нарушение цитируется кодом правила (`JS-2.5`, `JS-4.7` и т.д.).

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

### `/ucp-test-design`

Проектирование интеграционных и unit-тестов под [стратегию тестов](https://vikulin-va.ru/test-strategy/): синхронные, только PostgreSQL + WireMock, без Kafka/Redis в базовом классе, события через in-memory publisher.

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

## Подключение к проекту

### Симлинк всех скиллов (рекомендуется)

```bash
git clone https://github.com/remodov/usecase-pattern-skills.git ~/projects/usecase-pattern-skills

# из своего Java-проекта
mkdir -p .claude/skills
ln -s ~/projects/usecase-pattern-skills/.claude/skills/* .claude/skills/

# и скопировать или симлинк style guide:
mkdir -p docs
ln -s ~/projects/usecase-pattern-skills/docs/rest-api-style-guide.md docs/
```

### Глобально для всех проектов

```bash
mkdir -p ~/.claude/skills
ln -s ~/projects/usecase-pattern-skills/.claude/skills/* ~/.claude/skills/
```

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
└── ucp-test-design/        # проектирование интеграционных и unit-тестов

docs/
├── rest-api-style-guide.md          # снапшот vikulin-va.ru/rest-api-style-guide/
├── usecase-pattern-style-guide.md   # снапшот vikulin-va.ru/use-case-pattern/
├── ddd-tactical-style-guide.md      # снапшот vikulin-va.ru/domain-driven-design/tactical-patterns/
├── usecase-spec-template.md         # снапшот vikulin-va.ru/use-case-pattern/spec-template/
├── java-style-guide.md              # снапшот vikulin-va.ru/java-style-guide/
└── test-strategy.md                 # снапшот vikulin-va.ru/test-strategy/
```

## Связанные статьи и библиотеки

- [REST API Style Guide](https://vikulin-va.ru/rest-api-style-guide/) — свод правил с диаграммами.
- [Тактические паттерны DDD](https://vikulin-va.ru/domain-driven-design/tactical-patterns/) — Entity, Value Object, Aggregate, Domain Event, Repository.
- [`ddd-building-blocks`](https://github.com/remodov/ddd-building-blocks) — Java-библиотека базовых DDD-абстракций, на которой опираются скиллы DDD.
- [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/) — методология, объединяющая всё вместе.

В планах — скиллы для остальных статей сайта (CQRS, Hexagonal, Distributed Patterns, Resilience, Kafka, Auth Patterns).

## Лицензия

MIT
