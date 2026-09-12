---
lang: any
name: ucp-pg-schema-design
description: Сгенерировать Liquibase changeset для нового агрегата (требования pg-types/*, pg-naming/*) — CREATE TABLE с правильными типами (bigint IDENTITY, numeric, timestamptz, uuid, text, JSONB), FK с CASCADE, индексы, audit-колонки.
when_to_use: После ucp-ddd-tactical-design, до ucp-jooq-design. Триггеры — «сделай DDL для агрегата X», «нужна миграция под Order».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# PostgreSQL Schema — проектирование

Ты генерируешь Liquibase changeset для нового агрегата по `backend/pg-types/spec.md` (`PG-T-*`) и `backend/pg-naming/spec.md` (`PG-N-*`). Цель — DDL, который сразу проходит `ucp-pg-schema-review` без findings.

## Инструкции

1. **Прочитай требования:**
   - `.claude/docs/backend/pg-types/spec.md` — выбор типов колонок (`PG-T-*`).
   - `.claude/docs/backend/pg-naming/spec.md` — naming convention (`PG-N-*`).
   - `.claude/docs/backend/ddd-tactical/spec.md` — для понимания Aggregate Root, Entity, VO.
   - `.claude/docs/backend/pg-migrations/spec.md` `PG-M-*` — лёгкая часть (для нового агрегата это просто `CREATE TABLE`, без expand-contract).

2. **Уточни параметры:**
   - **Aggregate Root** — имя (`Order`), Java-поля и их типы (включая VO). Если домен ещё не написан — это для `ucp-ddd-tactical-design`.
   - **Child entities** в агрегате — `OrderItem`, `OrderShipment`. Каждый = отдельная таблица с FK на parent.
   - **Value Objects** — `Money`, `Address`, `DeliveryWindow`. Решение для каждого: inline-колонки (`amount`, `currency`) или JSONB (`address` как полный объект).
   - **Enum'ы** — `OrderStatus`, `PaymentMethod`. PG-enum vs textual + CHECK (`pg-types/enum-vs-reference-table`).
   - **Связь PK** — `bigint IDENTITY` (`pg-types/pk-bigint-identity`–`pg-types/pk-bigint-identity`) или `uuid v7` (`pg-types/uuid-is-uuid-type`–`pg-types/uuid-only-when-justified`)?
     - `bigint IDENTITY` — дефолт. Дешевле, быстрее (`pg-types/uuid-only-when-justified`).
     - `uuid v7` — если нужно генерить ID на стороне приложения до INSERT (event sourcing, distributed insert).
   - **Запросные сценарии** — какие фильтры из `<X>Filter`? Какие сортировки? → определяет индексы.
   - **Soft-delete нужен?** Если да — `deleted_at timestamptz` (`pg-naming/soft-delete-keeps-moment`).

3. **Принципы выбора типов:**

   | Поле в Java | PG-тип | Правило |
   |---|---|---|
   | `Long id` (PK) | `bigint GENERATED ALWAYS AS IDENTITY` | `pg-types/pk-bigint-identity`, `pg-types/pk-bigint-identity` |
   | `UUID id` (PK) — если нужен | `uuid` | `pg-types/uuid-is-uuid-type`, `pg-types/uuid-v7-for-keys` (v7) |
   | `Money amount` | `numeric(19, 2)` | `pg-types/money-is-numeric` |
   | `BigDecimal rate` (проценты) | `numeric(p, s)` под точность | `pg-types/money-is-numeric` |
   | `OffsetDateTime createdAt` | `timestamptz` | `pg-types/business-time-is-timestamptz`, `pg-types/time-mapping-keeps-zone` |
   | `LocalDate dateOf` | `date` | |
   | `String name` (без бизнес-ограничения) | `text` | `pg-types/text-by-default` |
   | `String code` (точно `varchar(N)` по бизнесу) | `varchar(N)` | `pg-types/varchar-when-domain-rule` |
   | `boolean isActive` | `boolean` | `pg-types/boolean-is-boolean` |
   | `OrderStatus` (Java enum) | PG enum либо `text` + CHECK | `pg-types/boolean-is-boolean`–`pg-types/typed-enum-in-code` |
   | `Address` (Value Object с 5+ полями) | `jsonb` | (custom; `pg-types/array-for-simple-scalars`+) |
   | `Address` (VO с 2-3 полями) | inline-колонки | (для индексируемости) |
   | `Map<String, String> metadata` | `jsonb` | |
   | `List<String> tags` | `text[]` | |

4. **Принципы naming (`PG-N-*`):**
   - Таблицы — единственное число, snake_case (`order`, не `orders`). Кроме junction (`order_item`).
   - PK всегда `id` (`pg-naming/pk-named-id`).
   - FK — `<parent>_id` (`pg-naming/fk-column-names-parent`): `customer_id`, `order_id`.
   - Boolean — префикс `is_` / `has_` / `can_` (`pg-naming/boolean-column-prefix`).
   - Время — глагол + `_at` для `timestamptz`, `_on` для `date` (`pg-naming/time-column-suffix`): `created_at`, `birth_on`.
   - Деньги — суффикс по назначению (`pg-naming/money-column-suffix`): `total_amount`, `tax_amount`, `discount_percent`.
   - Длительности — суффикс с единицей (`pg-naming/duration-unit-in-name`): `timeout_seconds`, `delay_minutes`.
   - Перечисления — без префикса/суффикса (`pg-naming/enum-column-plain-name`): `status`, `priority`.
   - Audit (`pg-naming/audit-columns-set`): `created_at timestamptz NOT NULL DEFAULT now()`, `updated_at timestamptz`.
   - Soft-delete (`pg-naming/soft-delete-keeps-moment`): `deleted_at timestamptz NULL`, не `is_deleted`.

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
   - FK — **обязательно** отдельный индекс (`pg-types/index-fk-under-uuid-pk` для UUID, общая практика для всех FK).
   - Поля из `<X>Filter` — индексировать. Композитные индексы под типичные запросы (см. `backend/pg-indexes/spec.md`).
   - Если есть `status` + сортировка по `created_at` → composite `(status, created_at DESC)`.
   - Soft-delete (`deleted_at`) — partial index `WHERE deleted_at IS NULL` если большинство запросов «активные».

7. **Решения по child-таблицам агрегата:**
   - Каждая child-Entity → отдельная таблица с FK на parent (`order_id` BIGINT NOT NULL).
   - `ON DELETE CASCADE` если child не существует без parent (типично для агрегата).
   - Индекс по `<parent>_id` — для multiset eager-fetch в `Jooq<X>Repository` (`jooq/nested-collections-in-one-query`).

8. **Решения по Value Objects:**
   - **Inline-колонки** (`address_street`, `address_city`, `address_zip`):
     - Если поля VO часто фильтруются/сортируются.
     - Если ≤ 3 полей.
   - **JSONB** (`address jsonb`):
     - Если 4+ полей и фильтрация по ним не нужна.
     - Если структура VO может меняться (forward-compat).
     - Цена: `pg-runtime/toast-large-values-separately` — горячие поля + holod в одном JSONB провоцируют full re-write при UPDATE.

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

10. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

## Что НЕ делает

- Не меняет существующие таблицы (это `ucp-pg-migration-design` — expand-contract под `PG-M-*`).
- Не пишет Aggregate Root / VO / Domain Event — это `ucp-ddd-tactical-design`.
- Не пишет JOOQ-репозиторий — это `ucp-jooq-design` (после `liquibaseUpdate` + `generateJooq`).
- Не настраивает Liquibase plugin / changelog-master — это `ucp-bootstrap-design`.

После — обязательно `ucp-pg-schema-review` для верификации DDL.

$ARGUMENTS
