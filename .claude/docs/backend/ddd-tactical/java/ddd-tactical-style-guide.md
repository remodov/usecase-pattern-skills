# DDD Tactical Patterns — Style Guide

Тактические паттерны DDD как они применяются в проектах с библиотекой
[`ru.vikulinva:ddd-building-blocks`](https://github.com/remodov/ddd-building-blocks)
(пакет `ru.vikulinva.ddd`).

Этот документ — единственный источник правды для скиллов
`ddd-tactical-review` и `ddd-tactical-design`. Любые расхождения с этим
гайдом — нарушение, требующее исправления или явного отступления с
комментарием в коде.


---

## Используемые абстракции из `ddd-building-blocks`

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

## 1. Entity

### `R-ENT-1` — Сущность наследует `Entity<ID>` или живёт внутри агрегата

Без наследования — только если это `ValueObject` или примитив.

### `R-ENT-2` — `getId()` возвращает стабильный неизменяемый идентификатор

ID присваивается в конструкторе и не меняется в течение жизни объекта.

### `R-ENT-3` — Поле `id` объявлено `final`

Setter для `id` запрещён.

### `R-ENT-4` — Equals/hashCode наследуются из `Entity<ID>`

Не переопределяются в наследниках. Базовый класс делает `final equals/hashCode` по `id`.

### `R-ENT-5` — Конструктор валидирует обязательные поля и инварианты

`Objects.requireNonNull` или явные `IllegalArgumentException`. Невалидная сущность не должна существовать.

### `R-ENT-X1` — Антипаттерн: переопределять `equals` или `hashCode` в наследниках

В `Entity<ID>` они `final`. Любая попытка — ошибка компиляции, которая сигнализирует о неправильном дизайне.

### `R-ENT-X2` — Антипаттерн: сравнивать сущности по полям

Только по ID — через `equals`. Сравнение по всем полям ломается на любых изменениях состояния.

### `R-ENT-X3` — Антипаттерн: публичные сеттеры для всех полей

Изменение состояния — только через бизнес-методы (`changeEmail`, `deactivate` и т.п.).

### `R-ENT-X4` — Антипаттерн: ссылки на другие агрегаты как объекты

Только по ID (`CustomerId`, `OrderId`).

### `R-ENT-X5` — Антипаттерн: анемичная модель

Класс с одними геттерами/сеттерами без бизнес-поведения. Логика должна жить в Entity, не в сервисах.

---

## 2. Value Object

### `R-VO-1` — Класс реализует маркер `ValueObject`

### `R-VO-2` — Класс immutable

`final class`, все поля `final`, никаких сеттеров.

### `R-VO-3` — Equals/hashCode сравнивают **все** значимые поля

Java `record`, реализующий `ValueObject`, удовлетворяет правилу автоматически.

### `R-VO-4` — Конструктор/фабрика проверяет инварианты

Невалидный VO не должен существовать.

### `R-VO-5` — Мутирующие операции возвращают новый экземпляр

`add`, `multiply`, `with...`. Никогда не модифицировать существующий VO.

### `R-VO-X1` — Антипаттерн: иметь поле `id` или жизненный цикл

Создан/изменён/удалён — это признаки Entity, не VO.

### `R-VO-X2` — Антипаттерн: «primitive obsession»

Передавать примитивы там, где есть подходящий VO: `String email` → `Email`, `BigDecimal amount` → `Money`.

### `R-VO-X3` — Антипаттерн: мутабельные коллекции внутри VO без обёртки

`List.copyOf` / `Collections.unmodifiableList` обязательны.

---

## 3. Aggregate Root

### `R-AGG-1` — Корень агрегата наследует `AggregateRoot<ID>`

### `R-AGG-2` — Все внешние операции — через методы корня

Внутренние Entity недоступны снаружи без обёртки или возвращаются как unmodifiable view.

### `R-AGG-3` — Корень регистрирует доменные события через `registerEvent(...)`

В момент изменения состояния, а не в репозитории.

### `R-AGG-4` — Транзакционная граница = граница агрегата

Один use-case изменяет один агрегат. Другие — только через события.

### `R-AGG-5` — Ссылки на другие агрегаты — только по ID

`CustomerId`, `OrderId`. Не объекты.

### `R-AGG-X1` — Антипаттерн: «God aggregate»

Содержит десятки несвязанных entity. Корень должен быть выделен по бизнес-инварианту.

### `R-AGG-X2` — Антипаттерн: возвращать наружу мутабельные коллекции

`return lines;` без обёртки → клиент мутирует внутреннее состояние агрегата напрямую.

### `R-AGG-X3` — Антипаттерн: изменять чужой агрегат напрямую

Транзакция изменяет только свой агрегат, остальное — через `DomainEvent`.

### `R-AGG-X4` — Антипаттерн: регистрировать события вне корня

В сервисах, репозиториях, контроллерах — нельзя. Только в самом корне агрегата.

---

## 4. Domain Event

### `R-EVT-1` — Событие наследует `DomainEvent`

И вызывает `super(aggregateType, aggregateId)` в конструкторе.

### `R-EVT-2` — Имя класса — глагол в прошедшем времени

`OrderPaid`, `UserRegistered`. Не `PayOrder` и не `OrderPaymentEvent`.

### `R-EVT-3` — Класс immutable

`final class`, все поля `final`, без сеттеров.

### `R-EVT-4` — Несёт бизнес-контекст

ID агрегата, ключевые значения на момент события (`amount`, `paidAt`). Не `Order order` целиком.

### `R-EVT-5` — Публикация — через `DomainEventPublisher.publishAll(...)`

В репозитории после сохранения, либо через адаптер `ApplicationEventPublisher`. После публикации — `clearDomainEvents()`.

### `R-EVT-X1` — Антипаттерн: изменять поля события после создания

Событие — факт в прошлом. Иммутабельность обязательна.

### `R-EVT-X2` — Антипаттерн: ссылка на агрегат или сущности в событии

Только примитивы и Value Objects. Иначе подписчик «доберётся» до изменяемого состояния агрегата.

### `R-EVT-X3` — Антипаттерн: публиковать событие из контроллера или сервиса

Только корень агрегата публикует свои события.

### `R-EVT-X4` — Антипаттерн: `@TransactionalEventListener(AFTER_COMMIT)` для критичных эффектов

Списание со склада, начисление денег — синхронный `@EventListener` в одной транзакции либо Outbox. AFTER_COMMIT теряется при падении после commit.

---

## 5. Repository

### `R-REP-1` — Интерфейс репозитория наследует `AggregateRepository<T, ID>`

И живёт в пакете домена (`domain/repository`).

### `R-REP-2` — Реализация — в адаптере (`adapter/out/...`)

Не в доменном пакете. Домен не знает про SQL/jOOQ/JPA.

### `R-REP-3` — Один репозиторий = один корень агрегата

Не «универсальные» репозитории для произвольных сущностей.

### `R-REP-4` — `save` атомарно сохраняет агрегат целиком

Публикует собранные `DomainEvent` через `DomainEventPublisher`, затем вызывает `clearDomainEvents()` на корне.

### `R-REP-5` — Методы названы в терминах домена

`findActiveByCustomerId`, не `selectFromOrders`.

### `R-REP-X1` — Антипаттерн: возвращать DAO/инфраструктурные типы

`Page<OrderEntity>`, `OrderRecord` (jOOQ) и т.п. наружу — нельзя. Только доменные объекты.

### `R-REP-X2` — Антипаттерн: методы, специфичные для одной таблицы

`updateStatusInDb` — это деталь хранения, не доменная операция.

### `R-REP-X3` — Антипаттерн: `Specification<T>` в Repository, генерирующая SQL

Это путает Repository и Query Side. Для чтений — отдельный Query/Read Model.

---

## 6. Domain Service

### `R-DS-1` — Domain Service создаётся, **только если** логика касается ≥ 2 агрегатов

И не помещается в один корень. Сначала пытаемся положить правило в Entity / AggregateRoot.

### `R-DS-2` — Класс stateless и принимает доменные объекты

Entity, Value Object — не DTO и не репозитории.

### `R-DS-3` — Имя выражает доменную операцию

`TransferService`, `PricingService`, не `OrderHelper` или `BusinessLogicManager`.

### `R-DS-X1` — Антипаттерн: оркестрация в Domain Service

Загрузка из репозитория, транзакции, отправка событий — это Application Service.

### `R-DS-X2` — Антипаттерн: Domain Service как «свалка» для всей логики

Оставляет агрегаты анемичными.

---

## 7. Factory

### `R-FAC-1` — Factory вводится только когда конструктор не справляется

Валидация требует другого агрегата, сборка из нескольких частей, политика выбора подкласса.

### `R-FAC-2` — Factory возвращает уже валидный агрегат

Включая зарегистрированные начальные события (`OrderCreated`).

### `R-FAC-X1` — Антипаттерн: Factory ради Factory

Если хватает `new Order(...)` — не плодить лишний слой.

---

## 8. Specification

### `R-SPEC-1` — Спецификация наследует `Specification<T>` и реализует `isSatisfiedBy`

### `R-SPEC-2` — Используется только когда правило применяется в ≥ 2 местах

Либо требуется комбинация `and/or/not`.

### `R-SPEC-X1` — Антипаттерн: `Specification` для генерации SQL

Это Query-side, не доменное правило.

### `R-SPEC-X2` — Антипаттерн: Specification для одного `if` в одном месте

Преждевременная абстракция.

---

## 9. Module (структура пакетов)

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

### `R-MOD-1` — Запрещено `entity/`, `service/`, `repository/` на верхнем уровне

Группировка по типу — антипаттерн. Только по домену (Bounded Context).

### `R-MOD-2` — Доменные пакеты не зависят от `adapter/*` и от Spring/JPA/jOOQ

Чистая Java + `ddd-building-blocks`. Никаких `@Component`, `@Entity`, `@Table` в `domain/`.

---

## 10. Что проверять — чек-лист обзора

При ревью обязательно убедиться:

1. Каждая Entity → `Entity<ID>`. ID `final`. Equals не переопределён.
2. Каждый VO → `ValueObject` + immutable + equals по значениям.
3. Корни агрегатов → `AggregateRoot<ID>`, события только в корне.
4. Все события → `DomainEvent` (super-вызов с aggregateType/aggregateId), immutable, имя в прошедшем времени.
5. Репозитории → `AggregateRepository<T, ID>`, реализация публикует события и чистит их.
6. Ссылки между агрегатами — только по ID.
7. Доменный пакет не импортирует Spring/jOOQ/JPA.
8. Структура пакетов сгруппирована по домену.
