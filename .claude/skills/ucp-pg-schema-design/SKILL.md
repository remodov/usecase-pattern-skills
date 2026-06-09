---
lang: any
name: ucp-pg-schema-design
description: Сгенерировать Liquibase changeset для нового агрегата (коды PG-T-*, PG-N-*) — CREATE TABLE с правильными типами (bigint IDENTITY, numeric для денег, timestamptz, uuid, text, JSONB для VO), FK с CASCADE-стратегией, индексы, audit-колонки.
when_to_use: После ucp-ddd-tactical-design, до ucp-jooq-design. Триггеры — «сделай DDL для агрегата X», «нужна миграция под Order».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# PostgreSQL Schema — проектирование

Ты генерируешь Liquibase changeset для нового агрегата по `backend/pg-types/pg-types-rules.md` (`PG-T-*`) и `backend/pg-naming/pg-naming-rules.md` (`PG-N-*`). Цель — DDL, который сразу проходит `ucp-pg-schema-review` без findings.

## Инструкции

1. **Прочитай style guide'ы:**
   - `.claude/docs/backend/pg-types/pg-types-rules.md` — выбор типов колонок (`PG-T-*`).
   - `.claude/docs/backend/pg-naming/pg-naming-rules.md` — naming convention (`PG-N-*`).
   - `.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md` — для понимания Aggregate Root, Entity, VO.
   - `.claude/docs/backend/pg-migrations/pg-migrations-rules.md` `PG-M-*` — лёгкая часть (для нового агрегата это просто `CREATE TABLE`, без expand-contract).

2. **Уточни параметры:**
   - **Aggregate Root** — имя (`Order`), Java-поля и их типы (включая VO). Если домен ещё не написан — это для `ucp-ddd-tactical-design`.
   - **Child entities** в агрегате — `OrderItem`, `OrderShipment`. Каждый = отдельная таблица с FK на parent.
   - **Value Objects** — `Money`, `Address`, `DeliveryWindow`. Решение для каждого: inline-колонки (`amount`, `currency`) или JSONB (`address` как полный объект).
   - **Enum'ы** — `OrderStatus`, `PaymentMethod`. PG-enum vs textual + CHECK (`PG-T-051`).
   - **Связь PK** — `bigint IDENTITY` (`PG-T-010`–`PG-T-012`) или `uuid v7` (`PG-T-040`–`PG-T-043`)?
     - `bigint IDENTITY` — дефолт. Дешевле, быстрее (`PG-T-043`).
     - `uuid v7` — если нужно генерить ID на стороне приложения до INSERT (event sourcing, distributed insert).
   - **Запросные сценарии** — какие фильтры из `<X>Filter`? Какие сортировки? → определяет индексы.
   - **Soft-delete нужен?** Если да — `deleted_at timestamptz` (`PG-N-031`).

3. **Принципы выбора типов:**

   | Поле в Java | PG-тип | Правило |
   |---|---|---|
   | `Long id` (PK) | `bigint GENERATED ALWAYS AS IDENTITY` | `PG-T-010`, `PG-T-012` |
   | `UUID id` (PK) — если нужен | `uuid` | `PG-T-040`, `PG-T-041` (v7) |
   | `Money amount` | `numeric(19, 2)` | `PG-T-013` |
   | `BigDecimal rate` (проценты) | `numeric(p, s)` под точность | `PG-T-013` |
   | `OffsetDateTime createdAt` | `timestamptz` | `PG-T-030`, `PG-T-031` |
   | `LocalDate dateOf` | `date` | |
   | `String name` (без бизнес-ограничения) | `text` | `PG-T-020` |
   | `String code` (точно `varchar(N)` по бизнесу) | `varchar(N)` | `PG-T-021` |
   | `boolean isActive` | `boolean` | `PG-T-016` |
   | `OrderStatus` (Java enum) | PG enum либо `text` + CHECK | `PG-T-050`–`PG-T-052` |
   | `Address` (Value Object с 5+ полями) | `jsonb` | (custom; `PG-T-070`+) |
   | `Address` (VO с 2-3 полями) | inline-колонки | (для индексируемости) |
   | `Map<String, String> metadata` | `jsonb` | |
   | `List<String> tags` | `text[]` | |

4. **Принципы naming (`PG-N-*`):**
   - Таблицы — единственное число, snake_case (`order`, не `orders`). Кроме junction (`order_item`).
   - PK всегда `id` (`PG-N-020`).
   - FK — `<parent>_id` (`PG-N-021`): `customer_id`, `order_id`.
   - Boolean — префикс `is_` / `has_` / `can_` (`PG-N-022`).
   - Время — глагол + `_at` для `timestamptz`, `_on` для `date` (`PG-N-023`): `created_at`, `birth_on`.
   - Деньги — суффикс по назначению (`PG-N-024`): `total_amount`, `tax_amount`, `discount_percent`.
   - Длительности — суффикс с единицей (`PG-N-025`): `timeout_seconds`, `delay_minutes`.
   - Перечисления — без префикса/суффикса (`PG-N-026`): `status`, `priority`.
   - Audit (`PG-N-030`): `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz`.
   - Soft-delete (`PG-N-031`): `deleted_at timestamptz NULL`, не `is_deleted`.

5. **Произведи Liquibase changeset.** Формат — YAML (более читабельный, чем XML). Структура по `migrations/db/changelog/v-1.x/`:

   ```yaml
   # migrations/db/changelog/v-1.0/0042-create-order.yaml
   databaseChangeLog:
     - changeSet:
         id: 0042-create-order
         author: <автор>
         comment: 'Order aggregate: CREATE TABLE order, order_item, order_shipment + indexes + FK'
         changes:
           - createTable:
               tableName: order
               columns:
                 - column:
                     name: id
                     type: bigint
                     autoIncrement: true
                     constraints:
                       primaryKey: true
                       primaryKeyName: order_pk
                 - column:
                     name: customer_id
                     type: bigint
                     constraints:
                       nullable: false
                 - column:
                     name: status
                     type: text
                     constraints:
                       nullable: false
                 - column:
                     name: total_amount
                     type: numeric(19, 2)
                     constraints:
                       nullable: false
                 - column:
                     name: created_at
                     type: timestamptz
                     defaultValueComputed: now()
                     constraints:
                       nullable: false
                 - column:
                     name: updated_at
                     type: timestamptz

           - addCheckConstraint:
               constraintName: order_status_chk
               tableName: order
               constraintBody: "status IN ('CREATED', 'CONFIRMED', 'PAID', 'SHIPPED', 'CANCELLED')"

           - addForeignKeyConstraint:
               constraintName: order_customer_fk
               baseTableName: order
               baseColumnNames: customer_id
               referencedTableName: customer
               referencedColumnNames: id
               onDelete: RESTRICT
               onUpdate: NO ACTION

           - createIndex:
               tableName: order
               indexName: order_customer_id_idx
               columns:
                 - column: { name: customer_id }

           - createIndex:
               tableName: order
               indexName: order_status_created_at_idx
               columns:
                 - column: { name: status }
                 - column: { name: created_at, descending: true }

         rollback:
           - dropTable:
               tableName: order
   ```

   Подключи changeset в master:
   ```yaml
   # migrations/db/changelog-master.yaml
   databaseChangeLog:
     - include: { file: db/changelog/v-1.0/0042-create-order.yaml }
   ```

6. **Решения по индексам:**
   - PK — автоматически индексируется.
   - FK — **обязательно** отдельный индекс (`PG-T-044` для UUID, общая практика для всех FK).
   - Поля из `<X>Filter` — индексировать. Композитные индексы под типичные запросы (см. `backend/pg-indexes/pg-indexes-rules.md`).
   - Если есть `status` + сортировка по `created_at` → composite `(status, created_at DESC)`.
   - Soft-delete (`deleted_at`) — partial index `WHERE deleted_at IS NULL` если большинство запросов «активные».

7. **Решения по child-таблицам агрегата:**
   - Каждая child-Entity → отдельная таблица с FK на parent (`order_id` BIGINT NOT NULL).
   - `ON DELETE CASCADE` если child не существует без parent (типично для агрегата).
   - Индекс по `<parent>_id` — для multiset eager-fetch в `Jooq<X>Repository` (`R-JOOQ-MS-3`).

8. **Решения по Value Objects:**
   - **Inline-колонки** (`address_street`, `address_city`, `address_zip`):
     - Если поля VO часто фильтруются/сортируются.
     - Если ≤ 3 полей.
   - **JSONB** (`address jsonb`):
     - Если 4+ полей и фильтрация по ним не нужна.
     - Если структура VO может меняться (forward-compat).
     - Цена: `PG-W-030` — горячие поля + holod в одном JSONB провоцируют full re-write при UPDATE.

9. **Самопроверка перед выдачей.** Пройди по `PG-T-*` / `PG-N-*`:
   - PK = `bigint IDENTITY` (или `uuid` v7 если обосновано).
   - Деньги — `numeric(p, s)`, не `float`/`real`/`money`.
   - Время — `timestamptz`, не `timestamp`.
   - UUID-колонка — тип `uuid`, не `varchar(36)`.
   - Строки — `text` (без `varchar(255)`).
   - Все FK имеют отдельный индекс.
   - Naming snake_case, единственное число, FK = `<parent>_id`.
   - `created_at` / `updated_at` — `timestamptz NOT NULL DEFAULT now()` для бизнес-таблиц.
   - `id` колонка PK называется `id` (не `<table>_id`).
   - Boolean — `is_*` / `has_*` / `can_*`.
   - Enum как `text` + CHECK (forward-compat) или PG-enum (если ровный список фиксирован).

10. **Структура вывода:**
    1. **Решения** — таблица «Java тип → PG тип → правило»; решения по VO (inline vs JSONB), enum (text+CHECK vs PG-enum), PK (bigint vs uuid).
    2. **Дерево новых файлов** — путь к changeset.
    3. **Каждый changeset — отдельный code block** с путём.
    4. **Patch master changelog** (`migrations/db/changelog-master.yaml`) с include.
    5. **Заметки по реализации:**
       - Команды: `./gradlew liquibaseUpdate`, `./gradlew generateJooq`.
       - **TODO:** автор changeset (поле `author`), unique business key (если применимо), partial-index'ы (если soft-delete).
    6. **Финальный шаг:** «после `liquibaseUpdate` запусти `ucp-pg-schema-review db/changelog/v-1.0/0042-create-order.yaml` для верификации, потом `ucp-jooq-design` для генерации `JooqOrderRepository`».

## Что НЕ делает

- Не меняет существующие таблицы (это `ucp-pg-migration-design` — expand-contract под `PG-M-*`).
- Не пишет Aggregate Root / VO / Domain Event — это `ucp-ddd-tactical-design`.
- Не пишет JOOQ-репозиторий — это `ucp-jooq-design` (после `liquibaseUpdate` + `generateJooq`).
- Не настраивает Liquibase plugin / changelog-master — это `ucp-bootstrap-design`.

После — обязательно `ucp-pg-schema-review` для верификации DDL.

$ARGUMENTS
