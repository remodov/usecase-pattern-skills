---
name: ucp-jooq-design
description: Сгенерировать persistence-слой на jOOQ (Java) из доменного <X>Repository по требованиям `jooq/*` — Jooq<X>Repository с DSLContext + multiset, <X>DomainRecordMapper, <X>FilterConditionBuilder, Jooq<X>ViewRepository, SelectMode.
when_to_use: После ucp-ddd-tactical-design (есть Aggregate и Repository-интерфейс). Триггеры — «сделай репозиторий для X», «нужна jooq-имплементация Y».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# jOOQ Repository — проектирование

Ты генерируешь persistence-имплементацию на jOOQ для домен-уровневого `<X>Repository` интерфейса по требованиям `jooq/*`. Цель — сервис получает `Jooq<X>Repository` + mapper + (опционально) filter-builder и view-репозиторий, проходящие `ucp-jooq-review` без findings.

## Инструкции

1. **Прочитай требования** в порядке:
   - `.claude/docs/backend/java/jooq/spec.md` — главный (правила `R-JOOQ-*`).
   - `.claude/docs/backend/ddd-tactical/spec.md` — для понимания Aggregate Root, Entity, Value Object: что из агрегата ложится в одну таблицу, что в child-таблицы.
   - `.claude/docs/backend/usecase-pattern/spec.md` §2 — для Уровня 3 (`core/` ↔ `persistence/`).
   - `.claude/docs/backend/pg-runtime/spec.md` `pg-runtime/row-lock-inside-transaction`/`pg-runtime/row-lock-inside-transaction` — для locking-синтаксиса (FOR UPDATE / SKIP LOCKED).

2. **Подтверди наличие зависимостей.** Проверь `bootstrap/build.gradle.kts` на:
   - `spring-boot-starter-jooq` (`spring-bootstrap/single-persistence-mechanism`).
   - `nu.studer.jooq` plugin (или собственный плагин `jooq-postgresql-generator-plugin` если уже есть в проекте — см. `jooq/codegen-from-live-schema`).
   - Generated POJO в `<pkg>.jooq.tables` (запусти `./gradlew generateJooq` если нет).
   Если codegen не настроен — это повод вызвать `ucp-bootstrap-design` сначала, не пиши руками.

3. **Уточни параметры из описания пользователя:**
   - **Aggregate Root и его структура.** Имя (`Order`, `Receipt`), child-сущности (`OrderItem` через `multiset`), value objects, enum'ы. Если домен ещё не написан — это для `ucp-ddd-tactical-design`, не для этого скилла.
   - **`<X>Repository` интерфейс в `core/port/out/repository/`.** Если ещё нет — либо пользователь пишет вместе с тобой (быстрый набросок), либо сначала `ucp-ddd-tactical-design`. Из интерфейса берёшь сигнатуры методов.
   - **Filter-объект (`<X>Filter`).** Сколько полей? Есть ли cross-table EXISTS-условия? `<X>Filter` ≤ 3 простых полей → inline-предикаты в репозитории. > 3 полей или EXISTS → отдельный `<X>FilterConditionBuilder` (`jooq/filters-extracted-to-builder`).
   - **Read-проекции:** есть ли отдельный `<X>ViewRepository` интерфейс, отличающийся от `<X>Repository`? Тогда `Jooq<X>ViewRepository` — отдельный класс (`jooq/view-repository-separate`). Иначе — пропускаем.
   - **Mapper стратегия:**
     - Простые DTO ↔ POJO (нет assemble-логики, нет ручных enum-конверсий, нет JSONB-парсинга) → MapStruct interface.
     - Aggregate с children, ручная реконструкция через `assembleAggregate(...)`, JSONB-парсинг, custom enum mapping → **Plain Java** `@Component` (`jooq/mapper-is-explicit-class`).
   - **SelectMode сценарии:** какие методы могут быть с `FOR UPDATE` (write-handler с pessimistic-lock) или `SKIP LOCKED` (scheduler / outbox)? Read-only query-handler — всегда `NO_LOCK` (default).

4. **Произведи код.** Lombok-defaults обязательны (`java-style/boilerplate-is-generated`–`java-style/builder-used-sparingly`). Не цитируй коды правил в комментариях кода (`java-style/no-rule-codes-or-history-in-code`).

   ### 4.1. Доменный `<X>Repository` (если ещё нет)
   ```java
   // core/port/out/repository/<X>Repository.java
   public interface OrderRepository {
       Optional<Order> findById(Long id, SelectMode mode);
       PaginationView<Order> findAll(OrderFilter filter, int page, int size);
       List<Order> findPending(int batchSize, SelectMode mode);  // для scheduler с SKIP_LOCKED
       void save(Order order);
   }
   ```

   ### 4.2. `SelectMode` и `PaginationView` (если ещё нет в core/)
   Эти классы — общие для всех агрегатов проекта. `SelectMode` — в `core/port/out/`, `PaginationView` — в `core/view/`; создай, если не существуют:
   ```java
   public enum SelectMode {
       NO_LOCK, FOR_UPDATE, FOR_UPDATE_SKIP_LOCKED
   }

   public record PaginationView<T>(
       List<T> items, long total, int count, int page, int size
   ) {
       public int getTotalPages() { return (int) Math.ceil((double) total / size); }
   }
   ```

   ### 4.3. `Jooq<X>Repository.java` — главный артефакт

   Расположение: `persistence/src/main/java/<pkg>/adapter/out/postgres/<x>/Jooq<X>Repository.java`.

   Структура:
   ```java
   @Repository
   @RequiredArgsConstructor
   public class JooqOrderRepository implements OrderRepository {

       private final DSLContext dslContext;
       private final OrderDomainRecordMapper mapper;
       private final OrderFilterConditionBuilder conditionBuilder;  // если фильтр сложный

       @Override
       public Optional<Order> findById(Long id, SelectMode mode) {
           var query = dslContext.select(
                   ORDERS.asterisk(),
                   buildChildrenSelect()    // multiset для child-сущностей
               )
               .from(ORDERS)
               .where(ORDERS.ID.eq(id));
           return applyLock(query, mode)
               .fetchOptional()
               .map(this::mapAggregate);
       }

       @Override
       public PaginationView<Order> findAll(OrderFilter filter, int page, int size) {
           var condition = conditionBuilder.buildCondition(filter);
           var total = dslContext.fetchCount(ORDERS, condition);
           var items = dslContext.select(ORDERS.asterisk(), buildChildrenSelect())
               .from(ORDERS)
               .where(condition)
               .orderBy(toSortFields(filter.sort()))
               .offset((long) page * size)
               .limit(size)
               .fetch()
               .map(this::mapAggregate);
           return new PaginationView<>(items, total, items.size(), page, size);
       }

       @Override
       public void save(Order order) {
           // INSERT/UPDATE через dslContext.update().set() или dslContext.insertInto(),
           // НЕ через record.set...().store() (R-JOOQ-QRY-X3)
           ...
       }

       // ===== private helpers =====

       private Field<Result<Record>> buildChildrenSelect() {
           // R-JOOQ-MS-3: multiset для eager-fetch nested-коллекций
           return multiset(
               selectFrom(ORDER_ITEMS)
                   .where(ORDER_ITEMS.ORDER_ID.eq(ORDERS.ID))
           ).as(ITEMS);   // alias-key из SelectMultisetAliasKeys (R-JOOQ-MS-1)
       }

       @SuppressWarnings("unchecked")
       private <Q extends SelectForUpdateOfStep<?>> Q applyLock(Q query, SelectMode mode) {
           return switch (mode) {
               case NO_LOCK -> query;
               case FOR_UPDATE -> (Q) query.forUpdate();
               case FOR_UPDATE_SKIP_LOCKED -> (Q) query.forUpdate().skipLocked();
           };
       }

       private List<SortField<?>> toSortFields(Sort<OrderSortField> sort) {
           return sort.fields().stream()
               .map(f -> switch (f.field()) {
                   case CREATED_AT -> ORDERS.CREATED_AT.sort(f.direction());
                   case TOTAL_AMOUNT -> ORDERS.TOTAL_AMOUNT.sort(f.direction());
               })
               .toList();
       }

       private Order mapAggregate(Record record) {
           var pojo = record.into(OrdersPojo.class);
           var items = RecordMappingUtils.getPojoList(record, ITEMS, OrderItemsPojo.class);
           return mapper.assembleAggregate(pojo, items);
       }
   }
   ```

   Static imports в начале файла (`jooq/type-safe-query-building`):
   ```java
   import static org.jooq.impl.DSL.*;
   import static <pkg>.adapter.out.postgres.SelectMultisetAliasKeys.*;
   import static <pkg>.jooq.Tables.ORDERS;
   import static <pkg>.jooq.Tables.ORDER_ITEMS;
   ```

   ### 4.4. `<X>DomainRecordMapper.java`

   Plain Java (если есть assemble-логика, enum-translation, JSONB) — **`jooq/mapper-is-explicit-class`**:
   ```java
   @Component
   @RequiredArgsConstructor
   public class OrderDomainRecordMapper {

       private final OrderItemDomainRecordMapper itemMapper;     // child-маппер инжектится (R-JOOQ-MAP-6)
       private final JooqJsonbHelper jsonb;                       // если есть JSONB

       public Order toDomain(OrdersPojo pojo) { ... }
       public OrdersPojo fromDomain(Order entity) { ... }

       // Сборка агрегата из плоских POJO + child-коллекций
       public Order assembleAggregate(OrdersPojo header, List<OrderItemsPojo> items) {
           var domainItems = items.stream().map(itemMapper::toDomain).toList();
           return Order.builder()
               .id(header.getId())
               .status(OrderStatus.fromValue(header.getStatus().getLiteral()))   // enum через jOOQ generated
               .totalAmount(Money.fromKopecks(header.getTotalAmount()))
               .items(domainItems)
               .build();
       }
   }
   ```

   MapStruct interface (если оба типа — POJO с одинаковыми полями, без сборки агрегата):
   ```java
   @Mapper(componentModel = "spring")
   public interface OrderItemDomainRecordMapper {
       OrderItem toDomain(OrderItemsPojo pojo);
       OrderItemsPojo fromDomain(OrderItem entity);
   }
   ```

   ### 4.5. `<X>FilterConditionBuilder.java` (если фильтр > 3 полей)

   ```java
   @Component
   @RequiredArgsConstructor
   public class OrderFilterConditionBuilder {

       private final DSLContext dslContext;

       public Condition buildCondition(OrderFilter filter) {
           Condition c = noCondition();
           c = andIfNotNull(c, filter.id(), ORDERS.ID::eq);
           c = andIfNotEmpty(c, filter.statuses(), s ->
               ORDERS.STATUS.in(s.stream().map(OrderStatus::toJooq).toList()));
           c = andIfNotNull(c, filter.customerId(), ORDERS.CUSTOMER_ID::eq);
           c = andIfNotNull(c, filter.dateFrom(), ORDERS.CREATED_AT::ge);
           c = andIfNotNull(c, filter.dateTo(), ORDERS.CREATED_AT::le);
           // EXISTS для cross-table (R-JOOQ-FLT-5)
           c = andIfNotNull(c, filter.sberId(), sid ->
               exists(select(PAYMENTS.ID).from(PAYMENTS)
                   .where(PAYMENTS.ORDER_ID.eq(ORDERS.ID).and(PAYMENTS.SBER_ID.eq(sid)))));
           return c;
       }
   }
   ```

   `FilterConditionHelper` (`jooq/filters-extracted-to-builder`) — общий для всех фильтров проекта. Создай в `persistence/src/main/java/<pkg>/adapter/out/postgres/`, если не существует:
   ```java
   public final class FilterConditionHelper {
       public static <T> Condition andIfNotNull(Condition c, T value, Function<T, Condition> mapper) {
           return value == null ? c : c.and(mapper.apply(value));
       }
       public static <T> Condition andIfNotEmpty(Condition c, Collection<T> coll, Function<Collection<T>, Condition> mapper) {
           return (coll == null || coll.isEmpty()) ? c : c.and(mapper.apply(coll));
       }
       public static Condition andIfTrue(Condition c, boolean cond, Supplier<Condition> mapper) {
           return cond ? c.and(mapper.get()) : c;
       }
       private FilterConditionHelper() {}
   }
   ```

   ### 4.6. `SelectMultisetAliasKeys` (если ещё нет в `persistence/`)
   Общий — все alias-ключи мульти-сетов проекта в одном месте (`jooq/nested-collections-in-one-query`):
   ```java
   public final class SelectMultisetAliasKeys {
       public static final String ITEMS = "items";
       public static final String INSURANCES = "insurances";
       // добавляй сюда по мере появления новых nested-коллекций
       private SelectMultisetAliasKeys() {}
   }
   ```

   ### 4.7. `Jooq<X>ViewRepository.java` (если есть `<X>ViewRepository` интерфейс с read-проекциями)

   Отдельный класс — не подмешивай view-методы к основному `Jooq<X>Repository` (`jooq/view-repository-separate`):
   ```java
   @Repository
   @RequiredArgsConstructor
   public class JooqOrderViewRepository implements OrderViewRepository {

       private final DSLContext dslContext;

       @Override
       public PaginationView<OrderSummary> findSummaries(OrderFilter filter, int page, int size) {
           // read-DTO `OrderSummary` — record в core/view/
           // Без full multiset, без heavy joins. Минимально что нужно UI.
           ...
       }
   }
   ```

5. **Самопроверка перед выдачей.** Пройди эти пункты (`R-JOOQ-*`):
   - `Jooq<X>Repository implements <X>Repository` (interface в `core/`).
   - Конструкторное внедрение через `@RequiredArgsConstructor`. `private final` поля.
   - Public-методы возвращают domain-типы (entity, value-object, `PaginationView<T>`), не POJO/Record.
   - Каждый read-метод принимает `SelectMode mode`.
   - Static imports `DSL.*` и `Tables.*` в начале файла.
   - Multiset для child-коллекций — alias-ключи только из `SelectMultisetAliasKeys` (нет magic strings).
   - Fetch-методы соответствуют сценарию: `fetchOptional()` для single-row-with-null, `fetchOne()` только если null = баг, `fetchExists()` для проверки наличия.
   - UPDATE через `dslContext.update().set().where()`, не через `record.store()`.
   - Filter условие начинается с `noCondition()`.
   - Mapper — Plain Java если есть assemble-логика; MapStruct только если оба типа POJO без custom-логики.
   - Generated POJO/Record не уходит из public-метода (`jooq/repository-speaks-domain-types`).
   - На `Jooq<X>Repository` нет `@Transactional` — это handler-граница.
   - View-методы не подмешаны к основному репозиторию (если read-проекция нужна — отдельный `<X>ViewRepository`).

6. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

## Что НЕ делает

- Не пишет UseCase / Handler. Это `ucp-pattern-design`.
- Не пишет Aggregate Root, Entity, Value Object, Domain Event. Это `ucp-ddd-tactical-design` — должен быть выполнен ДО этого скилла.
- Не создаёт Liquibase-миграции и DDL. Это `ucp-pg-schema-design` (в планах), либо вручную через `ucp-pg-schema-review` для проверки.
- Не настраивает codegen jOOQ — `ucp-bootstrap-design`.
- Не пишет тесты — `ucp-test-design` (но в выводе указывается чек-лист).

После работы скилла — обязательно `ucp-jooq-review` для верификации.

$ARGUMENTS
