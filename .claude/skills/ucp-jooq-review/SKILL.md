---
name: ucp-jooq-review
description: Ревью persistence-слоя на jOOQ — repository-pattern, multiset для nested-fetch, filter-builders, record→domain маппинг, SelectMode, view-репозитории, transaction boundaries. Проверяет Jooq<X>Repository, конструкторное внедрение DSLContext, alias-keys для multiset, SelectMode + applyLock, plain-Java *DomainRecordMapper (не MapStruct), @Transactional на handler (не на репозитории). Вызывается при ревью кода в persistence/ модуле, новых JooqXRepository, *DomainRecordMapper, *FilterConditionBuilder. Опирается на коды R-JOOQ-*.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью jOOQ persistence

Ты ревьюишь Java-код persistence-слоя (модуль `persistence/` в hexagonal-проекте) на соответствие jOOQ Style Guide. Главные точки контроля: репозиторий-паттерн, multiset, фильтры, маппинг record↔domain, SelectMode, транзакционные границы.

## Зависимости

- **`.claude/docs/jooq-style-guide.md`** — единственный источник правил. Каждое нарушение цитируется кодом из подгрупп: `R-JOOQ-CFG-*` (codegen), `R-JOOQ-REPO-*` (репозиторий), `R-JOOQ-CTX-*` (DSLContext), `R-JOOQ-QRY-*` (запросы), `R-JOOQ-MS-*` (multiset), `R-JOOQ-FLT-*` (filter-builders), `R-JOOQ-MAP-*` (mapper), `R-JOOQ-PAG-*` (пагинация), `R-JOOQ-LCK-*` (locks), `R-JOOQ-TX-*` (транзакции), `R-JOOQ-VIEW-*` (view-репо).
- Парные документы: `pg-runtime-style-guide.md` (PG-L-040/041 для locks), `spring-bootstrap-style-guide.md` (BS-17/18/19/20 для «только jOOQ + generated»).

## Инструкции

1. **Прочти style guide** из `.claude/docs/jooq-style-guide.md`. Цитируй конкретные коды правил в каждой находке (`R-JOOQ-MS-1`, `R-JOOQ-LCK-X1`, не «нарушение раздела 5»).

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые файлы в модуле `persistence/`.
   - Найди новые/изменённые `Jooq<X>Repository`, `<X>DomainRecordMapper`, `<X>FilterConditionBuilder`, `*ViewRepository`.
   - Найди build.gradle.kts с jOOQ codegen-конфигом, если он попал в diff.

3. **Прогон по подгруппам кодов.** Проверяй каждое применимое правило:
   - **`R-JOOQ-CFG-*`** — codegen: `setDaos(false)`, `setImmutablePojos(false)`, forced types на `OffsetDateTime` для timestamptz, `<enumConverter>true</enumConverter>` для domain-enum'ов.
   - **`R-JOOQ-REPO-*`** — `Jooq<X>Repository implements <X>Repository`; `<X>Repository` — interface в `core/`; конструкторная инъекция через `@RequiredArgsConstructor`; public-методы возвращают domain-типы, не POJO; параметр `SelectMode mode`; private helpers (`buildChildrenSelect()`, `applyLock()`, `toSortFields()`).
   - **`R-JOOQ-CTX-*`** — `DSLContext` — Spring-bean, не `DSL.using(...)`.
   - **`R-JOOQ-QRY-*`** — fetch-методы под цель (`fetchOptional`, `fetchExists`, не `fetchOne` где возможен null, не `fetchCount() > 0`); UPDATE через `dslContext.update().set().where()`, не через `record.set...().store()`; bind-параметры через DSL, не plain SQL.
   - **`R-JOOQ-MS-*`** — alias-keys в `SelectMultisetAliasKeys` (нет magic-strings); `RecordMappingUtils.getPojoList/getRecordList` для извлечения; multiset вкладывается в multiset для 2-уровневой иерархии; batch-fetch при много parents.
   - **`R-JOOQ-FLT-*`** — `<X>FilterConditionBuilder` Spring-bean; `Condition c = noCondition()` + `andIfNotNull/Empty/True` через `FilterConditionHelper`; EXISTS для cross-table; нет inline if-цепочек в репозитории.
   - **`R-JOOQ-MAP-*`** — plain Java mapper (Spring `@Component`), не MapStruct; bidirectional `toDomain` / `fromDomain` / `assembleAggregate`; enum через `OrderStatus.fromValue()` или `forcedType`; JSONB через `JooqJsonbHelper`.
   - **`R-JOOQ-PAG-*`** — `PaginationView<T>` возвращается из репозитория; offset 0-based на уровне репо (контракт API — 1-based); cursor через keyset-пагинацию `(createdAt, id)`.
   - **`R-JOOQ-LCK-*`** — `SelectMode` enum в `core/domain/repository/`; `applyLock()` switch; `forUpdate()` всегда внутри `@Transactional` (см. `PG-L-041`); optimistic — через `version`-колонку, не `Settings`.
   - **`R-JOOQ-TX-*`** — `@Transactional` на handler, не на репозитории; `readOnly = true` для query-handler'ов.
   - **`R-JOOQ-VIEW-*`** — `<X>ViewRepository` отдельно от `<X>Repository`, если read-проекция отличается от агрегата.

4. **При ревью кода ищи паттерны-нарушения:**
   - `dslContext.fetch("SELECT ...")` — `R-JOOQ-QRY-X1` (plain SQL, риск injection).
   - `record.set...().store()` для UPDATE — `R-JOOQ-QRY-X3`.
   - `.fetchOne()` где запись может отсутствовать — `R-JOOQ-QRY-X4`.
   - `.fetchCount() > 0` — `R-JOOQ-QRY-X5` (тяжелее `.fetchExists()`).
   - `.as("tickets")` строкой вместо константы — `R-JOOQ-MS-X1`.
   - inline-цепочки `if (filter.x != null) c = c.and(...)` в репозитории — `R-JOOQ-FLT-X1`.
   - Возврат POJO/Record из public-метода репозитория — `R-JOOQ-MAP-X1`.
   - `@Mapper(componentModel = "spring")` для record→domain с assemble-логикой — `R-JOOQ-MAP-X3`.
   - `DSL.using(connection, ...)` — `R-JOOQ-CTX-X1`.
   - `forUpdate()` без `@Transactional` на вызывающем методе — `R-JOOQ-LCK-X1`.
   - `@Transactional` на классе `Jooq<X>Repository` — `R-JOOQ-TX-X1`.
   - `dslContext.transaction(...)` внутри `@Transactional`-метода — `R-JOOQ-TX-X3`.
   - findSummaries/findForExport в основном `<X>Repository` — `R-JOOQ-VIEW-X1`.
   - `JdbcTemplate`, `JpaRepository`, `EntityManager` — `R-JOOQ-REPO-X3` + `BS-17`.

5. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-JOOQ-MS-1`, `R-JOOQ-LCK-X1`), не префикс.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — нарушения, которые вылазят под нагрузкой: plain SQL (injection), `forUpdate()` без TX, lazy-fetch вместо multiset (N+1), `@Transactional` на репо вместо handler, JdbcTemplate/JPA в обход `BS-17`.
   - **Предупреждение** — отклонения от конвенций: `fetchOne` где допустим null, magic-string alias, MapStruct с assemble-логикой, отсутствие `<X>ViewRepository` для тяжёлых read-проекций.
   - **Замечание** — стилистика: имена private-helper'ов, расположение mapper'а вне `persistence/<entity>/`.

## Что не входит

- Доменная логика, агрегаты, value-objects — `ucp-ddd-tactical-review`.
- UseCase + Handler + контроллер, `@Transactional`-границы со стороны handler — `ucp-pattern-review`.
- Сама схема PG (типы колонок, naming) — `ucp-pg-schema-review`.
- Индексы и `EXPLAIN` — `ucp-pg-explain-review`.
- Locking/WAL/autovacuum/connection pool со стороны runtime — `ucp-pg-runtime-review` (этот скилл проверяет только jOOQ-фасад над locking, не настройки PG).
- DDL-миграции (expand-contract, lock-safety) — `ucp-pg-migration-review`.
- Java-стиль (нейминг, импорты) — `ucp-java-style-review`.

$ARGUMENTS
