# jOOQ Style Guide

Свод правил использования jOOQ в Java-сервисах команды UCP. Каждое правило идентифицируется кодом (`R-JOOQ-CFG-1`, `R-JOOQ-QRY-X2` и т. п.) — скиллы `ucp-jooq-design` и `ucp-jooq-review` цитируют эти коды в findings.

Гайд опирается на:
- `BS-17`/`BS-18`/`BS-19`/`BS-20` (см. `spring-bootstrap-style-guide.md`) — почему jOOQ и только generated классы.
- `PG-L-040`/`PG-L-041` (см. `pg-runtime-style-guide.md`) — locking-синтаксис и обязательность `@Transactional`.

Этот документ — runtime-слой над схемой: **как** писать репозитории и запросы, не **что** использовать.

---

## Содержание

1. [Конфигурация codegen — `R-JOOQ-CFG-*`](#1-конфигурация-codegen)
2. [Repository-pattern — `R-JOOQ-REPO-*`](#2-repository-pattern)
3. [DSLContext — `R-JOOQ-CTX-*`](#3-dslcontext)
4. [Построение запросов — `R-JOOQ-QRY-*`](#4-построение-запросов)
5. [Multiset для nested-fetch — `R-JOOQ-MS-*`](#5-multiset-для-nested-fetch)
6. [Filter-builders — `R-JOOQ-FLT-*`](#6-filter-builders)
7. [Маппинг record ↔ domain — `R-JOOQ-MAP-*`](#7-маппинг-record--domain)
8. [Пагинация — `R-JOOQ-PAG-*`](#8-пагинация)
9. [Lock-режимы — `R-JOOQ-LCK-*`](#9-lock-режимы)
10. [Транзакции — `R-JOOQ-TX-*`](#10-транзакции)
11. [View-репозитории — `R-JOOQ-VIEW-*`](#11-view-репозитории)
12. [Антипаттерны — сводка `R-JOOQ-*-X*`](#12-антипаттерны)

---

## 1. Конфигурация codegen

### 1.1 Обязательно

- **R-JOOQ-CFG-1.** Codegen запускается **поверх живой схемы PostgreSQL**, поднятой через Testcontainers и накаченной Liquibase-миграциями. Не используется ни статический xml, ни ddl-файлы. Это даёт единый источник правды: `migrations/` → Liquibase → PG → jOOQ.
  ```
  generateJooqWithPostgres:
    1. start Testcontainers postgres
    2. ./gradlew liquibaseUpdate
    3. introspect via PostgresDatabase
    4. generate POJO + Record + Tables
  ```
- **R-JOOQ-CFG-2.** В команде есть собственный gradle-плагин `jooq-postgresql-generator-plugin`, который инкапсулирует Testcontainers + Liquibase + codegen. Сервис подключает его и не дублирует Testcontainers-конфигурацию вручную.
- **R-JOOQ-CFG-3.** Generated POJO именуются по паттерну `<Table>_Pojo` (через `MatcherStrategy`/PASCAL).
- **R-JOOQ-CFG-4.** TIMESTAMP/TIMESTAMPTZ-колонки маппятся на `java.time.OffsetDateTime` через `forcedTypes`. `LocalDateTime` запрещён для persistent-полей (см. `R-JOOQ-CFG-X3`).
- **R-JOOQ-CFG-5.** Generated код кладётся в `build/generated/sources/jooq/main`, не коммитится в VCS. Регенерируется на каждом `./gradlew compileJava`.
- **R-JOOQ-CFG-6.** Forced types для domain-enum'ов настраиваются через `<enumConverter>true</enumConverter>` если java enum уже существует в `core/`. Иначе jOOQ сам генерирует enum (см. `BS-19`).
  ```xml
  <forcedType>
    <userType>ru.example.OrderStatus</userType>
    <enumConverter>true</enumConverter>
    <includeExpression>.*\.STATUS</includeExpression>
  </forcedType>
  ```
- **R-JOOQ-CFG-7.** `setFluentSetters(true)` — generated setters возвращают `this`, чтобы поддержать chained-builder в маппере.

### 1.2 Запрещено

- **R-JOOQ-CFG-X1.** `setDaos(true)` — generated DAO в репозитории не используются (см. `R-JOOQ-REPO-X1`). Генерация лишних классов.
- **R-JOOQ-CFG-X2.** `setImmutablePojos(true)` — POJO мутабельны, иначе ломается chained-set в маппере. Иммутабельность обеспечивается на уровне domain-entity, не POJO.
- **R-JOOQ-CFG-X3.** `LocalDateTime` в forced types для timestamptz-колонок. Не несёт zone-информации, провоцирует bag-в-bag ошибки. Только `OffsetDateTime`.
- **R-JOOQ-CFG-X4.** Codegen из xml/ddl-файлов вместо живой схемы. Расходится с реальной БД.

---

## 2. Repository-pattern

### 2.1 Обязательно

- **R-JOOQ-REPO-1.** Domain-репозиторий — interface в `core/domain/repository/`. jOOQ-имплементация — в модуле `persistence/`, имя класса `Jooq<X>Repository implements <X>Repository`.
  ```java
  // core/domain/repository/OrderRepository.java
  public interface OrderRepository {
      Optional<Order> findById(Long id, SelectMode mode);
      PaginationView<Order> findAll(OrderFilter filter, int page, int size);
      void save(Order order);
  }

  // persistence/.../order/JooqOrderRepository.java
  @Repository
  @RequiredArgsConstructor
  public class JooqOrderRepository implements OrderRepository {
      private final DSLContext dslContext;
      private final OrderDomainRecordMapper mapper;
      private final OrderFilterConditionBuilder conditionBuilder;
  }
  ```
- **R-JOOQ-REPO-2.** Конструкторное внедрение через Lombok `@RequiredArgsConstructor`. Поля `private final`. Никакого `@Autowired` на полях.
- **R-JOOQ-REPO-3.** Public методы репозитория принимают и возвращают **domain-объекты** (entity, value-object, `PaginationView<T>`), не jOOQ Record и не POJO. POJO — деталь реализации.
- **R-JOOQ-REPO-4.** Все public read-методы принимают параметр `SelectMode mode` (см. раздел 9). По умолчанию `SelectMode.NO_LOCK` для query-handler'ов.
- **R-JOOQ-REPO-5.** Сложные части запроса (multiset-сборка, сортировка, лок) выносятся в `private` методы того же класса: `buildChildrenSelect()`, `toSortFields()`, `applyLock()`. Public-метод читается линейно, без вложенных DSL-выражений.
- **R-JOOQ-REPO-6.** Каждый репозиторий покрыт интеграционным тестом против Testcontainers PostgreSQL — без mock'ов `DSLContext`.

### 2.2 Запрещено

- **R-JOOQ-REPO-X1.** Использование jOOQ Generated DAO (`*Dao`) — запрещено `BS-18` и `R-JOOQ-CFG-X1`. Вместо них пишутся свои репозитории.
- **R-JOOQ-REPO-X2.** Прямой `JooqOrderRepository` injected в use-case handler. Хендлеры зависят от **domain-интерфейса**, не от persistence-имплементации.
- **R-JOOQ-REPO-X3.** Spring Data JDBC, JPA, Hibernate, MyBatis, JdbcTemplate в любой форме — нарушение `BS-17`.
- **R-JOOQ-REPO-X4.** Бизнес-логика в репозитории. Репозиторий — query/persistence operator, без `if (order.status == ...) ...`.

---

## 3. DSLContext

### 3.1 Обязательно

- **R-JOOQ-CTX-1.** `DSLContext` — Spring-bean (поднимается стартером `spring-boot-starter-jooq`). Инжектится в репозиторий через конструктор. Один на ApplicationContext.
- **R-JOOQ-CTX-2.** `DSLContext` потокобезопасен при условии, что `Configuration` иммутабельна. Кеши внутри (reflection lookup для record-mapping) разделяются между потоками — поэтому **переиспользуем singleton**, не создаём новый на запрос.
- **R-JOOQ-CTX-3.** Если нужна модифицированная конфигурация (`Settings`, `RecordMapperProvider`), создаётся **production-grade Bean**, не локальный `DSL.using(...)` на ходу.

### 3.2 Запрещено

- **R-JOOQ-CTX-X1.** `DSL.using(connection, ...)` или `DSL.using(dataSource)` в коде репозитория. Spring-bean уже сконфигурирован, вручную создавать не надо.
- **R-JOOQ-CTX-X2.** Хранение `Connection` или `DSLContext` в state'е репозитория и переиспользование между методами вне Spring-проводки.

---

## 4. Построение запросов

### 4.1 Обязательно

- **R-JOOQ-QRY-1.** Static imports для DSL-функций (`select`, `selectFrom`, `noCondition`, `multiset`, `field`, `case_`):
  ```java
  import static org.jooq.impl.DSL.*;
  import static ru.example.adapter.out.postgres.SelectMultisetAliasKeys.*;
  ```
  В каждом файле репозитория. Делает запросы читаемыми, как SQL.
- **R-JOOQ-QRY-2.** `selectFrom(TABLE)` — для fetch'а полной строки с последующим `.fetchInto(Pojo.class)`.
  `select(TABLE.FIELD1, TABLE.FIELD2, multiset(...))` — когда проектируем отдельные колонки или собираем multiset.
- **R-JOOQ-QRY-3.** Fetch-методы под цель:
  - `.fetchOptional()` / `.fetchOptionalInto(X.class)` — single-row, который может отсутствовать.
  - `.fetchOne()` — single-row, отсутствие = баг (бросит `NoDataFoundException`/`TooManyRowsException`).
  - `.fetch()` / `.fetchInto(X.class)` — список.
  - `.fetchExists()` — для проверки существования. Не `.fetchCount() > 0`.
  - `.fetchCount()` — только если число действительно нужно (для пагинации).
- **R-JOOQ-QRY-4.** Insert/Update/Delete — через DSL: `dslContext.insertInto(...)`, `update(...).set(...)`, `deleteFrom(...).where(...)`. Либо через `executeInsert(record)` если нужен auto-generated id.
- **R-JOOQ-QRY-5.** Bind-параметры — позиционные через DSL (`.where(ID.eq(id))`), не строковые через `condition("id = ?")`.
- **R-JOOQ-QRY-6.** Сортировка — отдельный private helper `toSortFields(Sort<X> sort) → List<SortField<?>>`, переключающий поля domain-enum'а на jOOQ-колонки.
  ```java
  private List<SortField<?>> toSortFields(Sort<OrderSortField> sort) {
      return sort.fields().stream()
          .map(f -> switch (f.field()) {
              case CREATED_AT -> orders.CREATED_AT.sort(f.direction());
              case TOTAL_AMOUNT -> orders.TOTAL_AMOUNT.sort(f.direction());
          })
          .toList();
  }
  ```
- **R-JOOQ-QRY-7.** EXISTS-подзапросы для related-таблиц через `DSL.exists(select(...).from(other).where(...))`. Не делаем join + group by ради проверки наличия.

### 4.2 Запрещено

- **R-JOOQ-QRY-X1.** `dslContext.fetch("SELECT ... FROM ...")` — plain SQL. Помечено `@PlainSQL` в jOOQ — риск SQL-injection и обход type-safety.
- **R-JOOQ-QRY-X2.** `condition("status = " + value)` — конкатенация в plain SQL. Прямой SQL-injection.
- **R-JOOQ-QRY-X3.** `record.set...(); record.store()` для UPDATE существующих записей. Скрывает что и где обновляется. Используй `dslContext.update(table).set(field, value).where(...)`.
- **R-JOOQ-QRY-X4.** `.fetchOne()` когда отсутствие записи — нормальный кейс. Используй `.fetchOptional()`, чтобы не ловить `NoDataFoundException`.
- **R-JOOQ-QRY-X5.** `.fetchCount() > 0` для проверки существования. Тяжелее `.fetchExists()` на больших таблицах.
- **R-JOOQ-QRY-X6.** `.into(...)` после `.fetch()` без типобезопасной проекции. Используй `.fetchInto(Pojo.class)`.

---

## 5. Multiset для nested-fetch

`multiset()` — стандартный паттерн eager-loading вложенных коллекций одним SQL-запросом. Заменяет N+1 и lazy-инициализацию из JPA.

### 5.1 Обязательно

- **R-JOOQ-MS-1.** Каждая alias-key для `.as("...")` живёт в одном месте — `SelectMultisetAliasKeys` в модуле `persistence/`. Константа на ключ, без magic strings:
  ```java
  public final class SelectMultisetAliasKeys {
      public static final String TICKETS = "tickets";
      public static final String INSURANCES = "insurances";
      public static final String RECEIPTS = "receipts";
      private SelectMultisetAliasKeys() {}
  }
  ```
- **R-JOOQ-MS-2.** Извлечение nested-коллекций из result-record — через утилиту `RecordMappingUtils`:
  ```java
  List<TicketsPojo> tickets = RecordMappingUtils.getPojoList(record, TICKETS, TicketsPojo.class);
  Result<?> insuranceRecords = RecordMappingUtils.getRecordList(record, INSURANCES);
  ```
  Никакого `(Result<?>) record.get(TICKETS, Result.class)` напрямую — теряется типобезопасность и читаемость.
- **R-JOOQ-MS-3.** Multiset вкладывается в multiset для eager-fetch'а 2-уровневой иерархии (Order → Ticket → Insurance):
  ```java
  multiset(
      select(
          tickets.asterisk(),
          multiset(selectFrom(insurances).where(insurances.TICKET_ID.eq(tickets.ID)))
              .as(INSURANCES)
      )
      .from(tickets)
      .where(tickets.ORDER_ID.eq(orders.ID))
  ).as(TICKETS)
  ```
- **R-JOOQ-MS-4.** Если parents много (batch find), вместо multiset делаем **два запроса**: parent-IDs → children `WHERE parent_id IN (...)` + ручная зашивка через `fetchMap`. Multiset на тысячах parent'ов даёт большие result-row'ы и медленные транспорт.

### 5.2 Запрещено

- **R-JOOQ-MS-X1.** Magic-string как alias: `.as("tickets")` непосредственно в коде запроса. Только из `SelectMultisetAliasKeys`.
- **R-JOOQ-MS-X2.** Lazy-fetch nested-коллекции отдельным запросом из маппера. N+1 запросов = регресс производительности. Multiset или batch-fetch.

---

## 6. Filter-builders

### 6.1 Обязательно

- **R-JOOQ-FLT-1.** Сложные WHERE-условия выносятся в `<X>FilterConditionBuilder` — Spring `@Component`, не статическая утилита (нужны зависимости — `DSLContext` для подзапросов).
  ```java
  @Component
  @RequiredArgsConstructor
  public class OrderFilterConditionBuilder {
      private final DSLContext dslContext;

      public Condition buildCondition(OrderFilter filter) {
          Condition c = noCondition();
          c = andIfNotNull(c, filter.id(), orders.ID::eq);
          c = andIfNotNull(c, filter.statusFrom(), s -> orders.STATUS.in(s));
          c = andIfNotEmpty(c, filter.customerIds(), orders.CUSTOMER_ID::in);
          return c;
      }
  }
  ```
- **R-JOOQ-FLT-2.** `<X>Filter` — record/POJO в `core/domain/repository/filter/`, иммутабельный. Поля nullable, чтобы фильтр игнорировался если значение не задано.
- **R-JOOQ-FLT-3.** Условие начинается с `Condition c = noCondition()`. Это нейтральный элемент — если ни один if не сработает, WHERE будет полным `1=1`.
- **R-JOOQ-FLT-4.** Чейнинг через утилиту `FilterConditionHelper`:
  ```java
  public final class FilterConditionHelper {
      public static <T> Condition andIfNotNull(Condition c, T value, Function<T, Condition> mapper) { ... }
      public static <T> Condition andIfNotEmpty(Condition c, Collection<T> coll, Function<Collection<T>, Condition> mapper) { ... }
      public static Condition andIfTrue(Condition c, boolean cond, Supplier<Condition> mapper) { ... }
  }
  ```
- **R-JOOQ-FLT-5.** EXISTS для cross-table фильтров (заказ имеет платёж, тикет имеет страховку):
  ```java
  c = andIfNotNull(c, filter.sberId(), sid ->
      exists(select(payment.ID).from(payment)
          .where(payment.ORDER_ID.eq(orders.ID).and(payment.SBER_ID.eq(sid)))));
  ```
- **R-JOOQ-FLT-6.** `<X>FilterConditionBuilder` — единственное место, где знание о `<X>Filter` встречается с jOOQ-таблицами. Из репозитория передаём filter, обратно получаем `Condition`.

### 6.2 Запрещено

- **R-JOOQ-FLT-X1.** Inline if-цепочки внутри метода репозитория, ветвящие WHERE. На третьем поле фильтра нечитаемо.
- **R-JOOQ-FLT-X2.** Конкатенация SQL-фрагментов через String — теряется type-safety и есть риск SQL-injection.

---

## 7. Маппинг Record ↔ Domain

### 7.1 Обязательно

- **R-JOOQ-MAP-1.** Маппер — **plain Java class** (Spring `@Component`), не MapStruct interface. Причина: маппинг между jOOQ POJO и domain entity содержит ручную логику (assemble aggregate, разворачивать multiset-result, конвертировать enum), которую MapStruct не покрывает удобно.
  ```java
  @Component
  @RequiredArgsConstructor
  public class OrderDomainRecordMapper {
      private final TicketDomainRecordMapper ticketMapper;
      private final JooqJsonbHelper jsonb;

      public Order toDomain(OrdersPojo pojo) { ... }
      public OrdersPojo fromDomain(Order entity) { ... }
      public Order assembleAggregate(OrdersPojo header, List<TicketsPojo> tickets) { ... }
  }
  ```
- **R-JOOQ-MAP-2.** Двусторонний маппинг: `toDomain(pojo)` и `fromDomain(entity)`. Для сборки агрегата из плоских POJO — отдельный `assembleAggregate(...)`, принимающий все части агрегата как параметры.
- **R-JOOQ-MAP-3.** Enum-перевод — через generated jOOQ enum + domain enum:
  ```java
  // jooq → domain
  status = pojo.getStatus() != null
      ? OrderStatus.fromValue(pojo.getStatus().getLiteral())
      : null;
  // domain → jooq
  pojo.setStatus(ru.example.jooq.enums.OrderStatus.lookupLiteral(domainStatus.getValue()));
  ```
  Или через `forcedType` с `<enumConverter>true</enumConverter>` — тогда конвертация автоматическая (см. `R-JOOQ-CFG-6`).
- **R-JOOQ-MAP-4.** JSONB-колонки — через `JooqJsonbHelper` (Spring-bean с инжектируемым `ObjectMapper`):
  ```java
  public <T> T deserialize(JSONB jsonb, Class<T> clazz) { ... }
  public JSONB serialize(Object value) { ... }
  ```
- **R-JOOQ-MAP-5.** Timestamp-конверсия не делается в маппере вручную — `forcedType OffsetDateTime` (см. `R-JOOQ-CFG-4`) делает это в codegen-time.
- **R-JOOQ-MAP-6.** Каждый child-маппер инжектится в parent (`OrderDomainRecordMapper` зависит от `TicketDomainRecordMapper`). Делегация — не наследование, не статика.
- **R-JOOQ-MAP-7.** Маппер расположен рядом с репозиторием в `persistence/.../<entity>/`, не в `core/`. Это persistence-деталь.

### 7.2 Запрещено

- **R-JOOQ-MAP-X1.** Возврат POJO/Record из public-метода репозитория. POJO — внутренний тип, наружу только domain.
- **R-JOOQ-MAP-X2.** Создание domain-entity напрямую из generated record без маппера. Логика конструирования размазывается.
- **R-JOOQ-MAP-X3.** MapStruct-interface для record→domain, если у маппинга есть assemble-логика или enum-конверсия. MapStruct ок, только если оба типа — POJO с одинаковыми полями (бывает редко в этом слое).

---

## 8. Пагинация

### 8.1 Обязательно

- **R-JOOQ-PAG-1.** Domain-репозиторий возвращает `PaginationView<T>` — record/POJO в `core/domain/repository/`:
  ```java
  public record PaginationView<T>(
      List<T> items, long total, int count, int page, int size
  ) {
      public int getTotalPages() {
          return (int) Math.ceil((double) total / size);
      }
  }
  ```
- **R-JOOQ-PAG-2.** Offset-based пагинация в репозитории:
  - `query.offset((long) page * size).limit(size).fetch(...)` — items.
  - Отдельный `fetchCount` query для total.
  - Контракт API — `R-QRY-4` (page 1-based в публичном REST). В репозитории — 0-based, конвертируется на handler-уровне.
- **R-JOOQ-PAG-3.** Cursor-based (keyset) пагинация — для часто меняющихся данных (ленты, уведомления):
  ```java
  query.where(orders.CREATED_AT.lt(cursor.createdAt())
          .or(orders.CREATED_AT.eq(cursor.createdAt()).and(orders.ID.lt(cursor.id()))))
       .orderBy(orders.CREATED_AT.desc(), orders.ID.desc())
       .limit(size + 1)  // +1 чтобы определить hasNext
       .fetch(...);
  ```
  Total не вычисляется (дорого + не нужен).
- **R-JOOQ-PAG-4.** Cursor — непрозрачный токен на уровне API (см. `R-QRY-5` в REST guide). На уровне репозитория cursor — record `(createdAt, id)` или подобный composite-key.
- **R-JOOQ-PAG-5.** Total для коллекции — через `.fetchCount()`, не через получение всех записей и `.size()`.

### 8.2 Запрещено

- **R-JOOQ-PAG-X1.** `fetchAll()` без `LIMIT`/`OFFSET` для UI-эндпоинтов. На большой таблице — OOM или таймаут.
- **R-JOOQ-PAG-X2.** Использование `count(*)` (через query builder) на больших таблицах в горячем пути — sequential scan. Если нужен appromix-count — использовать оценки PG (`pg_class.reltuples`).

---

## 9. Lock-режимы

### 9.1 Обязательно

- **R-JOOQ-LCK-1.** В `core/domain/repository/SelectMode.java` — domain-enum:
  ```java
  public enum SelectMode {
      NO_LOCK,                    // обычный SELECT
      FOR_UPDATE,                 // SELECT FOR UPDATE
      FOR_UPDATE_SKIP_LOCKED      // FOR UPDATE SKIP LOCKED для batch-схедулеров
  }
  ```
  Каждый репозиторный метод чтения принимает `SelectMode mode` и применяет.
- **R-JOOQ-LCK-2.** `applyLock(query, mode)` — private helper в репозитории:
  ```java
  private <Q extends SelectForUpdateOfStep<?>> Q applyLock(Q query, SelectMode mode) {
      return switch (mode) {
          case NO_LOCK -> query;
          case FOR_UPDATE -> (Q) query.forUpdate();
          case FOR_UPDATE_SKIP_LOCKED -> (Q) query.forUpdate().skipLocked();
      };
  }
  ```
- **R-JOOQ-LCK-3.** Любой `forUpdate()`/`skipLocked()`-запрос — внутри `@Transactional`-метода (см. `PG-L-041`). Иначе jOOQ откроет/закроет соединение, лок отпустится мгновенно.
- **R-JOOQ-LCK-4.** Для optimistic locking используется `version`-колонка в схеме (см. `PG-L-051`), а не `withExecuteWithOptimisticLocking(true)` в `Settings`. Причина: `version`-колонка явная и видима всем (миграциям, debug, ручным правкам), `Settings` — скрытая магия.

### 9.2 Запрещено

- **R-JOOQ-LCK-X1.** `forUpdate()` без `@Transactional` на вызывающем методе. Лок не удержится — баг под нагрузкой.
- **R-JOOQ-LCK-X2.** `withExecuteWithOptimisticLocking(true)` глобально в `Settings`. Делает поведение запросов скрытым; конфликт-error из ниоткуда.
- **R-JOOQ-LCK-X3.** Использование `forUpdate()` для read-only query — лишнее блокирование. `NO_LOCK` для запросов из query-handler'ов.

---

## 10. Транзакции

### 10.1 Обязательно

- **R-JOOQ-TX-1.** `@Transactional` ставится на **handler** (`UseCaseHandler.handle()`), не на репозиторий. Граница транзакции — бизнес-операция.
  ```java
  @Component
  @Transactional   // RW по умолчанию
  public class CreateOrderCommandHandler implements UseCaseHandler<CreateOrderCommand, Order> { ... }

  @Component
  @Transactional(readOnly = true)
  public class GetOrdersQueryHandler implements UseCaseHandler<GetOrdersQuery, PaginationView<Order>> { ... }
  ```
- **R-JOOQ-TX-2.** `@Transactional(readOnly = true)` обязателен на query-handler'ах. Spring/JOOQ передадут это в драйвер — PG может отдать запрос на standby.
- **R-JOOQ-TX-3.** Если в одном handler нужны изоляция или propagation отличные от дефолтных — указываются явно: `@Transactional(isolation = Isolation.REPEATABLE_READ)`. Default — `READ_COMMITTED` (PG default).

### 10.2 Запрещено

- **R-JOOQ-TX-X1.** `@Transactional` на репозитории. Репозиторий — query/persistence operator без знания о бизнес-границах. Граница — handler.
- **R-JOOQ-TX-X2.** `@Transactional` на сервисном слое в обход handler'ов. У UCP — handler единственная точка транзакции (см. `usecase-pattern-style-guide.md` § Handlers).
- **R-JOOQ-TX-X3.** Программное управление транзакцией через `dslContext.transaction(...)` если уже есть Spring `@Transactional`. Возникает вложенная TX через Savepoint — ненужная сложность.

---

## 11. View-репозитории

### 11.1 Обязательно

- **R-JOOQ-VIEW-1.** Если read-проекция отличается от агрегата (флаговый список, сводка, отчёт), вводится **отдельный** интерфейс `<X>ViewRepository` рядом с `<X>Repository`:
  ```java
  // core/domain/repository/
  public interface OrderRepository {           // CRUD агрегата
      Optional<Order> findById(Long id, SelectMode mode);
      void save(Order order);
  }

  public interface OrderViewRepository {        // оптимизированные read-проекции
      PaginationView<OrderSummary> findSummaries(OrderFilter filter, int page, int size);
      List<OrderRow> findExport(OrderFilter filter);
  }
  ```
- **R-JOOQ-VIEW-2.** View-репозиторий читает только то, что нужно (без full multiset, без heavy joins). Возвращает domain-friendly read-DTO (`OrderSummary`, `OrderRow`), не агрегат.
- **R-JOOQ-VIEW-3.** Read-DTO — record в `core/domain/repository/view/` или `core/dto/view/`. Иммутабельный, без бизнес-логики.

### 11.2 Запрещено

- **R-JOOQ-VIEW-X1.** Перегружать `<X>Repository` отдельными методами вида `findSummaries`, `findForExport`. Это раздувает основной интерфейс и смешивает write-aggregate и read-projection — два разных контракта.

---

## 12. Антипаттерны

Сводка ссылок на запрещающие правила (X-коды) — единая точка для быстрой проверки.

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Generated DAO в репозитории | `R-JOOQ-CFG-X1`, `R-JOOQ-REPO-X1` | `Jooq<X>Repository implements <X>Repository` |
| Plain SQL `dslContext.fetch("...")` | `R-JOOQ-QRY-X1` | DSL: `selectFrom(...)` |
| Конкатенация в condition | `R-JOOQ-QRY-X2` | bind через `.eq(value)` |
| `record.set...().store()` для UPDATE | `R-JOOQ-QRY-X3` | `update(table).set(...)` |
| `.fetchOne()` где допустим null | `R-JOOQ-QRY-X4` | `.fetchOptional()` |
| `.fetchCount() > 0` | `R-JOOQ-QRY-X5` | `.fetchExists()` |
| Magic-string alias в multiset | `R-JOOQ-MS-X1` | константа из `SelectMultisetAliasKeys` |
| Lazy-fetch nested через отдельный запрос | `R-JOOQ-MS-X2` | `multiset()` или batch-fetch |
| Inline ветвящийся WHERE | `R-JOOQ-FLT-X1` | `<X>FilterConditionBuilder` + `andIfNotNull` |
| POJO/Record возвращается наружу | `R-JOOQ-MAP-X1` | mapper → domain |
| `MapStruct` с assemble-логикой | `R-JOOQ-MAP-X3` | plain Java mapper |
| `DSL.using(...)` вручную | `R-JOOQ-CTX-X1` | Spring-bean `DSLContext` |
| `LocalDateTime` для timestamptz | `R-JOOQ-CFG-X3` | `OffsetDateTime` |
| `setImmutablePojos(true)` | `R-JOOQ-CFG-X2` | мутабельные POJO |
| Codegen из xml/ddl | `R-JOOQ-CFG-X4` | Liquibase + Testcontainers + introspection |
| `forUpdate()` без `@Transactional` | `R-JOOQ-LCK-X1`, `PG-L-041` | `@Transactional` на handler'е |
| Глобальный optimistic-locking через `Settings` | `R-JOOQ-LCK-X2` | `version`-колонка, `PG-L-051` |
| `@Transactional` на репозитории | `R-JOOQ-TX-X1` | на handler'е |
| Вложенные read-методы в основном `<X>Repository` | `R-JOOQ-VIEW-X1` | отдельный `<X>ViewRepository` |
| `fetchAll()` без LIMIT в UI-эндпоинте | `R-JOOQ-PAG-X1` | `LIMIT/OFFSET` или cursor |
| JdbcTemplate / JPA / MyBatis | `R-JOOQ-REPO-X3`, `BS-17` | jOOQ |

Финальная сводка: правил «Обязательно» — около 50, «Запрещено» — около 25. Findings ревью цитируют конкретный код (`R-JOOQ-MS-1`, `R-JOOQ-LCK-X1`).
