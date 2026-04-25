# DDD Tactical Patterns — Style Guide

Тактические паттерны DDD как они применяются в проектах с библиотекой
[`ru.vikulinva:ddd-building-blocks`](https://github.com/remodov/ddd-building-blocks)
(пакет `ru.badgermock.ddd`).

Этот документ — единственный источник правды для скиллов
`ddd-tactical-review` и `ddd-tactical-design`. Любые расхождения с этим
гайдом — нарушение, требующее исправления или явного отступления с
комментарием в коде.

Базовый материал статьи: <https://vikulin-va.ru/domain-driven-design/tactical-patterns/>.

---

## 1. Используемые абстракции из `ddd-building-blocks`

| Абстракция | Тип | Назначение |
|---|---|---|
| `Entity<ID>` | `abstract class` | Базовый класс для сущностей. Equals/hashCode по `getId()`. |
| `AggregateRoot<ID>` | `abstract class extends Entity<ID>` | Корень агрегата + список `DomainEvent`. |
| `ValueObject` | marker `interface` | Маркер для Value Object. |
| `DomainEvent` | `abstract class` | Базовое доменное событие. Поля: `id`, `createdAt`, `aggregateType`, `aggregateId`. |
| `DomainEventHandler<E>` | `interface` | Обработчик события (`void handle(E event)`). |
| `DomainEventPublisher` | `interface` | `publish(DomainEvent)` / `publishAll(List<?>)`. |
| `AggregateRepository<T, ID>` | `interface` | `findById`, `save`, `delete` агрегата целиком. |
| `Specification<T>` | `abstract class` | `isSatisfiedBy` + комбинаторы `and`/`or`/`not`. |

Все правила ниже формулируются в терминах этих типов.

---

## 2. Entity

### 2.1 Обязательно

- **R-ENT-1.** Сущность наследует `Entity<ID>` (или находится внутри
  агрегата и принадлежит ему). Без наследования — только если это
  ValueObject или примитив.
- **R-ENT-2.** Реализован `getId()` — возвращает стабильный, неизменяемый
  идентификатор. ID присваивается в конструкторе и не меняется.
- **R-ENT-3.** Поле `id` объявлено `final`. Setter для `id` запрещён.
- **R-ENT-4.** Equals/hashCode наследуются из `Entity<ID>` — не
  переопределяются. (Базовый класс делает `final equals/hashCode` по `id`.)
- **R-ENT-5.** Конструктор валидирует все обязательные поля и инварианты
  при помощи `Objects.requireNonNull` или явных `IllegalArgumentException`.

### 2.2 Запрещено

- **R-ENT-X1.** Переопределять `equals` или `hashCode` в наследниках
  `Entity<ID>` (это `final`).
- **R-ENT-X2.** Сравнивать сущности по полям (только по ID — через
  `equals`).
- **R-ENT-X3.** Делать публичные сеттеры для всех полей. Изменение
  состояния — только через бизнес-методы (`changeEmail`, `deactivate` и т.п.).
- **R-ENT-X4.** Хранить ссылки на другие агрегаты как объекты. Только по
  ID.
- **R-ENT-X5.** Анемичная модель: класс с одними геттерами/сеттерами без
  бизнес-поведения.

---

## 3. Value Object

### 3.1 Обязательно

- **R-VO-1.** Класс реализует маркер `ValueObject`.
- **R-VO-2.** Класс immutable: `final class`, все поля `final`, никаких
  сеттеров.
- **R-VO-3.** Equals/hashCode переопределены и сравнивают **все**
  значимые поля. (Java `record`, реализующий `ValueObject`, удовлетворяет
  правилу автоматически.)
- **R-VO-4.** Конструктор/фабрика проверяет инварианты — невалидный VO
  не должен существовать.
- **R-VO-5.** Все мутирующие операции возвращают новый экземпляр
  (`add`, `multiply`, `with...`).

### 3.2 Запрещено

- **R-VO-X1.** Иметь поле `id` или жизненный цикл (создан/изменён/удалён).
- **R-VO-X2.** Передавать примитивы там, где есть подходящий VO
  (`String email` → `Email`, `BigDecimal amount` → `Money`). Это
  «primitive obsession».
- **R-VO-X3.** Хранить мутабельные коллекции внутри без обёртки
  `List.copyOf` / `Collections.unmodifiableList`.

---

## 4. Aggregate Root

### 4.1 Обязательно

- **R-AGG-1.** Корень агрегата наследует `AggregateRoot<ID>`.
- **R-AGG-2.** Все внешние операции выполняются через методы корня. Внутренние
  Entity недоступны снаружи без обёртки или возвращаются как unmodifiable view.
- **R-AGG-3.** Корень регистрирует доменные события через
  `registerEvent(...)` в момент изменения состояния, а не в репозитории.
- **R-AGG-4.** Транзакционная граница = граница агрегата. Один use-case
  изменяет один агрегат (другие — только через события).
- **R-AGG-5.** Ссылки на другие агрегаты — только по ID (`CustomerId`,
  `OrderId`).

### 4.2 Запрещено

- **R-AGG-X1.** «God aggregate», содержащий десятки несвязанных entity.
  Корень должен быть выделен по бизнес-инварианту.
- **R-AGG-X2.** Возвращать наружу мутабельные коллекции внутренних
  Entity (`return lines;` без обёртки).
- **R-AGG-X3.** Изменять чужой агрегат напрямую. Транзакция изменяет
  только свой агрегат, остальное — через `DomainEvent`.
- **R-AGG-X4.** Регистрировать события вне корня агрегата (в сервисах,
  репозиториях, контроллерах).

---

## 5. Domain Event

### 5.1 Обязательно

- **R-EVT-1.** Событие наследует `DomainEvent` и вызывает `super(aggregateType, aggregateId)`.
- **R-EVT-2.** Имя класса — глагол в прошедшем времени: `OrderPaid`,
  `UserRegistered`. Не `PayOrder` и не `OrderPaymentEvent`.
- **R-EVT-3.** Класс immutable: `final class`, все поля `final`, без
  сеттеров.
- **R-EVT-4.** Несёт бизнес-контекст: id-агрегата, ключевые значения
  на момент события (`amount`, `paidAt`). Не `Order order` целиком.
- **R-EVT-5.** Публикация — через `DomainEventPublisher.publishAll(...)`
  в репозитории после сохранения, либо через адаптер
  `ApplicationEventPublisher`. После публикации — `clearDomainEvents()`.

### 5.2 Запрещено

- **R-EVT-X1.** Изменять поля события после создания.
- **R-EVT-X2.** Класть в событие ссылку на сам агрегат или сущности —
  только примитивы и Value Objects.
- **R-EVT-X3.** Публиковать событие из контроллера, application-сервиса
  или handler-а вместо самого корня агрегата.
- **R-EVT-X4.** Использовать `@TransactionalEventListener(AFTER_COMMIT)`
  для критичных побочных эффектов (списание со склада, начисление денег).
  Для них — синхронный `@EventListener` в одной транзакции либо Outbox.

---

## 6. Repository

### 6.1 Обязательно

- **R-REP-1.** Интерфейс репозитория наследует
  `AggregateRepository<T, ID>` и живёт в пакете домена (`domain/repository`).
- **R-REP-2.** Реализация — в адаптере (`adapter/out/...`), а не в
  доменном пакете.
- **R-REP-3.** Один репозиторий = один корень агрегата. Не «универсальные»
  репозитории для произвольных сущностей.
- **R-REP-4.** `save` атомарно сохраняет агрегат целиком и публикует
  собранные `DomainEvent` через `DomainEventPublisher`, затем вызывает
  `clearDomainEvents()` на корне.
- **R-REP-5.** Методы названы в терминах домена (`findActiveByCustomerId`),
  а не SQL (`selectFromOrders`).

### 6.2 Запрещено

- **R-REP-X1.** Возвращать `Page<OrderEntity>`, `OrderRecord` (jOOQ) или
  иные DAO/инфраструктурные типы из методов репозитория. Только
  доменные объекты.
- **R-REP-X2.** Содержать в интерфейсе репозитория методы, специфичные
  для одной таблицы (`updateStatusInDb`).
- **R-REP-X3.** Принимать `Specification<T>` в Repository, если
  фактически генерируется SQL — это путает Repository и Query Side. Для
  чтений — отдельный Query/Read Model.

---

## 7. Domain Service

### 7.1 Обязательно

- **R-DS-1.** Domain Service создаётся, **только если** логика касается
  ≥ 2 агрегатов и не помещается в один корень. Сначала пытаемся положить
  правило в Entity / AggregateRoot.
- **R-DS-2.** Класс stateless и принимает доменные объекты (Entity,
  Value Object) — не DTO и не репозитории.
- **R-DS-3.** Имя выражает доменную операцию (`TransferService`,
  `PricingService`), а не технический слой.

### 7.2 Запрещено

- **R-DS-X1.** Класть в Domain Service оркестрацию (загрузка из
  репозитория, транзакции, отправка событий) — это Application Service.
- **R-DS-X2.** Использовать Domain Service как «свалку» для всей логики,
  оставляя агрегаты анемичными.

---

## 8. Factory

### 8.1 Обязательно

- **R-FAC-1.** Factory вводится только когда конструктор не справляется:
  валидация требует другого агрегата, сборка из нескольких частей,
  политика выбора подкласса.
- **R-FAC-2.** Factory возвращает уже валидный агрегат (включая
  зарегистрированные начальные события — `OrderCreated`).

### 8.2 Запрещено

- **R-FAC-X1.** Создавать Factory ради Factory, если хватает
  `new Order(...)`.

---

## 9. Specification

### 9.1 Обязательно

- **R-SPEC-1.** Спецификация наследует `Specification<T>` и реализует
  `isSatisfiedBy`.
- **R-SPEC-2.** Используется только когда правило применяется в ≥ 2
  местах либо требуется комбинация `and/or/not`.

### 9.2 Запрещено

- **R-SPEC-X1.** Использовать `Specification` для генерации SQL — это
  Query-side, не доменное правило.
- **R-SPEC-X2.** Создавать Specification для одного `if` в одном месте.

---

## 10. Структура пакетов (Module)

Группировка — по домену, не по типу:

```
core/
  <bounded-context>/
    domain/
      aggregate/        # AggregateRoot
      entity/           # внутренние Entity агрегата
      valueobject/      # Value Object
      event/            # DomainEvent
      repository/       # interface AggregateRepository
      service/          # Domain Service (опционально)
      specification/    # Specification (опционально)
    usecase/
      command/          # CQRS команды
      query/            # CQRS запросы
adapter/
  in/rest/
  out/postgres/
```

- **R-MOD-1.** Запрещено `entity/`, `service/`, `repository/` на верхнем
  уровне (группировка по типу).
- **R-MOD-2.** Доменные пакеты не зависят от `adapter/*` и от
  Spring/JPA/jOOQ.

---

## 11. Что проверять — чек-лист обзора

При ревью обязательно убедиться:

1. Каждая Entity → `Entity<ID>`. ID `final`. Equals не переопределён.
2. Каждый VO → `ValueObject` + immutable + equals по значениям.
3. Корни агрегатов → `AggregateRoot<ID>`, события только в корне.
4. Все события → `DomainEvent` (super-вызов с aggregateType/aggregateId),
   immutable, имя в прошедшем времени.
5. Репозитории → `AggregateRepository<T, ID>`, реализация публикует
   события и чистит их.
6. Ссылки между агрегатами — только по ID.
7. Доменный пакет не импортирует Spring/jOOQ/JPA.
8. Структура пакетов сгруппирована по домену.
