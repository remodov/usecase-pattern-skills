# DDD Tactical Patterns — реализация

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

### `ddd-tactical/entity-equality-by-identity` — Сущность наследует `Entity<ID>` или живёт внутри агрегата

Без наследования — только если это `ValueObject` или примитив.

### `ddd-tactical/identity-is-immutable` — `getId()` возвращает стабильный неизменяемый идентификатор

ID присваивается в конструкторе и не меняется в течение жизни объекта.

### `ddd-tactical/identity-is-immutable` — Поле `id` объявлено `final`

Setter для `id` запрещён.

### `ddd-tactical/entity-equality-by-identity` — Equals/hashCode наследуются из `Entity<ID>`

Не переопределяются в наследниках. Базовый класс делает `final equals/hashCode` по `id`.

### `ddd-tactical/entity-constructor-validates` — Точка создания валидирует обязательные поля и инварианты

У агрегатов и сущностей эту роль играет фабрика `create(...)` (`ddd-tactical/factory-only-when-needed`): проверки — до сборки builder'ом, сгенерированный конструктор логики не несёт. У VO-record'ов — компактный конструктор. Невалидная сущность не должна существовать.

### `ddd-tactical/entity-equality-by-identity` — Антипаттерн: переопределять `equals` или `hashCode` в наследниках

В `Entity<ID>` они `final`. Любая попытка — ошибка компиляции, которая сигнализирует о неправильном дизайне.

### `ddd-tactical/entity-equality-by-identity` — Антипаттерн: сравнивать сущности по полям

Только по ID — через `equals`. Сравнение по всем полям ломается на любых изменениях состояния.

### `ddd-tactical/entity-constructor-validates` — Антипаттерн: публичные сеттеры для всех полей

Изменение состояния — только через бизнес-методы (`changeEmail`, `deactivate` и т.п.).

### `ddd-tactical/no-object-references-across-aggregates` — Антипаттерн: ссылки на другие агрегаты как объекты

Только по ID (`CustomerId`, `OrderId`).

### `ddd-tactical/model-is-not-anemic` — Антипаттерн: анемичная модель

Класс с одними геттерами/сеттерами без бизнес-поведения. Логика должна жить в Entity, не в сервисах.

---

## 2. Value Object

### `ddd-tactical/value-object-is-immutable` — Класс реализует маркер `ValueObject`

### `ddd-tactical/value-object-is-immutable` — Класс immutable

`final class`, все поля `final`, никаких сеттеров.

### `ddd-tactical/value-equality-by-all-fields` — Equals/hashCode сравнивают **все** значимые поля

Java `record`, реализующий `ValueObject`, удовлетворяет правилу автоматически.

### `ddd-tactical/value-validates-on-creation` — Конструктор/фабрика проверяет инварианты

Невалидный VO не должен существовать.

### `ddd-tactical/value-object-is-immutable` — Мутирующие операции возвращают новый экземпляр

`add`, `multiply`, `with...`. Никогда не модифицировать существующий VO.

### `ddd-tactical/value-has-no-identity` — Антипаттерн: иметь поле `id` или жизненный цикл

Создан/изменён/удалён — это признаки Entity, не VO.

### `ddd-tactical/no-primitive-obsession` — Антипаттерн: «primitive obsession»

Передавать примитивы там, где есть подходящий VO: `String email` → `Email`, `BigDecimal amount` → `Money`.

### `ddd-tactical/collections-in-values-are-protected` — Антипаттерн: мутабельные коллекции внутри VO без обёртки

`List.copyOf` / `Collections.unmodifiableList` обязательны.

---

## 3. Aggregate Root

### `ddd-tactical/aggregate-root-is-single-entry` — Корень агрегата наследует `AggregateRoot<ID>`

### `ddd-tactical/aggregate-root-is-single-entry` — Все внешние операции — через методы корня

Внутренние Entity недоступны снаружи без обёртки или возвращаются как unmodifiable view.

### `ddd-tactical/events-registered-by-root` — Корень регистрирует доменные события через `registerEvent(...)`

В момент изменения состояния, а не в репозитории.

### `ddd-tactical/transaction-boundary-equals-aggregate` — Транзакционная граница = граница агрегата

Один use-case изменяет один агрегат. Другие — только через события.

### `ddd-tactical/domain-does-not-know-operations` — Метод корня принимает доменные типы, не команду

`domain` не импортирует `usecase`: команду разбирает handler, в агрегат приходят значения.

```java
// нет: агрегат зависит от слоя операций
public boolean update(UpdateManagerCommand command) { ... }

// да: значение домена, собранное маппером адаптера
public boolean apply(ManagerSnapshot snapshot) {
    if (snapshot.updatedAt().isBefore(updatedAt)) {
        return false;
    }
    ...
}
```

Когда набор атрибутов приходит как одно целое — снимок сущности из внешней системы, — он выражается
записью `<Aggregate>Snapshot implements ValueObject` в `domain/valueobject/`: одна форма и для создания
через фабрику, и для обновления. Отдельные переходы состояния (`confirm()`, `cancel(Reason)`) остаются
методами с доменными параметрами. Гейт — `archunit:DomainDoesNotDependOnUseCasesTest`.

### `ddd-tactical/no-object-references-across-aggregates` — Ссылки на другие агрегаты — только по ID

`CustomerId`, `OrderId`. Не объекты.

### `ddd-tactical/aggregate-stays-small` — Антипаттерн: «God aggregate»

Содержит десятки несвязанных entity. Корень должен быть выделен по бизнес-инварианту.

### `ddd-tactical/aggregate-root-is-single-entry` — Антипаттерн: возвращать наружу мутабельные коллекции

`return lines;` без обёртки → клиент мутирует внутреннее состояние агрегата напрямую.

### `ddd-tactical/transaction-boundary-equals-aggregate` — Антипаттерн: изменять чужой агрегат напрямую

Транзакция изменяет только свой агрегат, остальное — через `DomainEvent`.

### `ddd-tactical/events-registered-by-root` — Антипаттерн: регистрировать события вне корня

В сервисах, репозиториях, контроллерах — нельзя. Только в самом корне агрегата.

---

## 4. Domain Event

### `ddd-tactical/event-is-immutable-record` — Событие наследует `DomainEvent`

И вызывает `super(aggregateType, aggregateId)` в конструкторе.

### `ddd-tactical/event-named-in-past-tense` — Имя класса — глагол в прошедшем времени

`OrderPaid`, `UserRegistered`. Не `PayOrder` и не `OrderPaymentEvent`.

### `ddd-tactical/event-is-immutable-record` — Класс immutable

`final class`, все поля `final`, без сеттеров.

### `ddd-tactical/event-carries-business-context` — Несёт бизнес-контекст

ID агрегата, ключевые значения на момент события (`amount`, `paidAt`). Не `Order order` целиком.

### `ddd-tactical/events-published-after-save` — Публикация — через `DomainEventPublisher.publishAll(...)`

В репозитории после сохранения, либо через адаптер `ApplicationEventPublisher`. После публикации — `clearDomainEvents()`.

### `ddd-tactical/event-is-immutable-record` — Антипаттерн: изменять поля события после создания

Событие — факт в прошлом. Иммутабельность обязательна.

### `ddd-tactical/event-carries-business-context` — Антипаттерн: ссылка на агрегат или сущности в событии

Только примитивы и Value Objects. Иначе подписчик «доберётся» до изменяемого состояния агрегата.

### `ddd-tactical/events-published-after-save` — Антипаттерн: публиковать событие из контроллера или сервиса

Только корень агрегата публикует свои события.

### `ddd-tactical/no-after-commit-for-critical-effects` — Антипаттерн: `@TransactionalEventListener(AFTER_COMMIT)` для критичных эффектов

Списание со склада, начисление денег — синхронный `@EventListener` в одной транзакции либо Outbox. AFTER_COMMIT теряется при падении после commit.

---

## 5. Repository

### `ddd-tactical/repository-port-in-domain` — Интерфейс репозитория наследует `AggregateRepository<T, ID>`

И живёт в `core/port/out/repository/` — порт, типизированный агрегатом; реализация — в persistence-адаптере.

### `ddd-tactical/repository-port-in-domain` — Реализация — в адаптере (`adapter/out/...`)

Не в доменном пакете. Домен не знает про SQL/jOOQ/JPA.

### `ddd-tactical/repository-per-aggregate-root` — Один репозиторий = один корень агрегата

Не «универсальные» репозитории для произвольных сущностей.

### `ddd-tactical/repository-per-aggregate-root` — `save` атомарно сохраняет агрегат целиком

Публикует собранные `DomainEvent` через `DomainEventPublisher`, затем вызывает `clearDomainEvents()` на корне.

### `ddd-tactical/repository-speaks-domain` — Методы названы в терминах домена

`findActiveByCustomerId`, не `selectFromOrders`.

### `ddd-tactical/repository-speaks-domain` — Антипаттерн: возвращать DAO/инфраструктурные типы

`Page<OrderEntity>`, `OrderRecord` (jOOQ) и т.п. наружу — нельзя. Только доменные объекты.

### `ddd-tactical/repository-speaks-domain` — Антипаттерн: методы, специфичные для одной таблицы

`updateStatusInDb` — это деталь хранения, не доменная операция.

### `ddd-tactical/specification-is-not-a-query-builder` — Антипаттерн: `Specification<T>` в Repository, генерирующая SQL

Это путает Repository и Query Side. Для чтений — отдельный Query/Read Model.

---

## 6. Domain Service

### `ddd-tactical/domain-service-only-across-aggregates` — Domain Service создаётся, **только если** логика касается ≥ 2 агрегатов

И не помещается в один корень. Сначала пытаемся положить правило в Entity / AggregateRoot.

### `ddd-tactical/domain-service-only-across-aggregates` — Класс stateless и принимает доменные объекты

Entity, Value Object — не DTO и не репозитории.

### `ddd-tactical/domain-service-only-across-aggregates` — Имя выражает доменную операцию

`TransferService`, `PricingService`, не `OrderHelper` или `BusinessLogicManager`.

### `ddd-tactical/domain-service-only-across-aggregates` — Антипаттерн: оркестрация в Domain Service

Загрузка из репозитория, транзакции, отправка событий — это Application Service.

### `ddd-tactical/domain-service-only-across-aggregates` — Антипаттерн: Domain Service как «свалка» для всей логики

Оставляет агрегаты анемичными.

---

## 7. Factory

### `ddd-tactical/factory-only-when-needed` — Единственная точка создания агрегата — `<X>Factory`

У каждого корня агрегата и сущности есть фабрика в `core/domain/factory/` — `@UtilityClass` со статическим `create(...)`: проверяет инварианты создания, собирает объект через `<X>.builder()`, регистрирует начальные события и возвращает валидный агрегат. Как в эталоне: 25 фабрик на 19 агрегатов и 12 сущностей.

```java
@UtilityClass
public class OrderFactory {

    public Order create(UUID orderId, CustomerId customerId, List<OrderLine> lines, UUID createdBy) {
        if (lines.isEmpty()) {
            throw new OrderException.LinesRequired(orderId);
        }
        OffsetDateTime now = DateTimeUtil.currentDateTime();
        Order order = Order.builder()
            .id(orderId)
            .customerId(customerId)
            .status(OrderStatus.DRAFT)
            .lines(new ArrayList<>(lines))
            .createdBy(createdBy)
            .createdAt(now)
            .updatedAt(now)
            .build();
        order.markCreated();
        return order;
    }
}
```

### `ddd-tactical/factory-only-when-needed` — `@Builder` агрегата — проводка, не API

Публичного конструктора у агрегата нет: `@Builder` генерирует package-private all-args конструктор и `builder()`, которым пользуются ровно два места — фабрика при создании и `<X>DomainRecordMapper.toDomain(...)` при восстановлении из БД. ArchUnit `AggregateBuildersUsedOnlyByFactoriesTest` держит оба условия:

```java
@ArchTest
static final ArchRule aggregatesHaveNoPublicConstructors = classes()
        .that().areAssignableTo(Entity.class)
        .should(notHavePublicConstructors());

@ArchTest
static final ArchRule aggregateBuildersUsedOnlyByFactoriesAndMappers = noClasses()
        .that().resideOutsideOfPackages("<root>.core.domain.factory..", "<root>.adapter.out.postgres..")
        .should().callMethodWhere(target(name("builder"))
                .and(target(owner(assignableTo(Entity.class)))));
```

`notHavePublicConstructors()` — своё `ArchCondition`: у класса нет конструктора с модификатором `PUBLIC`. `Entity` из `ddd-building-blocks` покрывает и `AggregateRoot`.

### `ddd-tactical/factory-only-when-needed` — Антипаттерн: сборка агрегата «на месте»

Обработчик или сервис, который зовёт `Order.builder()` или `new Order(...)` сам, обходит проверки создания. Единственный вход — фабрика; тест выше красный.

---

## 8. Specification

### `ddd-tactical/specification-for-reuse` — Спецификация наследует `Specification<T>` и реализует `isSatisfiedBy`

### `ddd-tactical/specification-for-reuse` — Используется только когда правило применяется в ≥ 2 местах

Либо требуется комбинация `and/or/not`.

### `ddd-tactical/specification-is-not-a-query-builder` — Антипаттерн: `Specification` для генерации SQL

Это Query-side, не доменное правило.

### `ddd-tactical/specification-for-reuse` — Антипаттерн: Specification для одного `if` в одном месте

Преждевременная абстракция.

---

## 9. Module (структура пакетов)

Группировка — по домену, не по типу:

```
core/
  domain/
    aggregate/        # AggregateRoot
    entity/           # внутренние Entity агрегата
    valueobject/      # Value Object (+ enumeration/)
    event/            # DomainEvent
    factory/          # фабрики агрегатов и сущностей
    service/          # Domain Service (опционально)
    specification/    # Specification (опционально)
  usecase/
    command/<фича>/   # CQRS команды
    query/<фича>/     # CQRS запросы
  port/
    out/repository/   # interface AggregateRepository
adapter/
  in/rest/
  out/postgres/<bc>/  # границы контекстов — здесь и в docs/domain/
```

### `ddd-tactical/packages-grouped-by-domain` — Раскладка core по роли элемента, контексты — вне core

Верхний уровень `core/` — `domain/`, `usecase/`, `port/`, `view/`, `service/` (схема — `hexagonal/core-structure`, R-HEX-CORE-2). Bounded context'ы не образуют слоя пакетов в `core/`: их границы — в `docs/domain/bounded-contexts.md` и в пакетах persistence-адаптера `adapter/out/postgres/<bc>/`. Адреса агрегатов, сущностей и портов держит ArchUnit `CoreStructureTest`.

### `ddd-tactical/packages-grouped-by-domain` — Доменные пакеты не зависят от `adapter/*` и от JPA/jOOQ

Чистая Java + `ddd-building-blocks`. Никаких `@Entity`, `@Table`, jOOQ-типов в `domain/`; DI-стереотип допустим только на доменном сервисе (`domain/service`).

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
