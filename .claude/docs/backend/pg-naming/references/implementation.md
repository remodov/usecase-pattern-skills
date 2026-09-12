# PostgreSQL Naming — реализация

Конвенции именования объектов в PostgreSQL для прикладного бэкенда. Каждое правило имеет код `PG-N-NNN` — на эти коды ссылается скилл `ucp-pg-schema-review` при ревью DDL.

Базовый принцип: **именование — самая дешёвая дисциплина с долгим эффектом**. Через два года команда читает чужой код, а DBA не путается в `EXPLAIN`.

---

## 1. Регистр и стиль

### `pg-naming/snake-case-no-quotes` — `snake_case` для всего

: таблицы, колонки, индексы, constraint'ы, sequence'ы, view'ы. Без `camelCase`, без `PascalCase`.

### `pg-naming/snake-case-no-quotes` — Никаких кавычек в идентификаторах

`"OrderDoc"` принуждает PG сохранить регистр и требует кавычек везде. Кавычки нужны только для конфликтов с зарезервированными словами (см. §6 — лучше переименовать).

## 2. Таблицы

### `pg-naming/table-singular-noun` — Существительные в единственном числе:

`order_doc`, `customer`, `product`. Конвенция спорная (Hibernate/JPA-сообщество чаще plural), главное — выбрать одно и не смешивать.

### `pg-naming/junction-table-name` — Junction-таблицы (many-to-many):

обе сущности в порядке — `order_item`, `customer_role`, `product_tag`.

### `pg-naming/domain-schema-split` — Префикс домена для крупных схем

или отдельный schema (`order.doc`, `catalog.product`). Без префиксов 200 таблиц одного `public` нечитаемо.

## 3. Колонки

### `pg-naming/pk-named-id` — id-колонка таблицы — `id`

Не `customer_id` в таблице `customer` — удвоение префикса избыточно.

### `pg-naming/fk-column-names-parent` — Foreign key — `<parent>_id`:

`customer_id`, `order_id`, `product_id`. Автоматически документирует таблицу-родителя.

### `pg-naming/boolean-column-prefix` — Boolean — с префиксом `is_`/`has_`/`can_`:

`is_active`, `is_deleted`, `has_avatar`, `can_login`. Без префикса `active` boolean ↔ `active` enum трудно отличить.

### `pg-naming/time-column-suffix` — Время — глагол прошедшего времени + `_at` для timestamp, `_on` для date:
- `created_at`, `updated_at`, `deleted_at`, `expires_at`, `published_at` — `timestamptz`
- `born_on`, `hired_on` — `date`

### `pg-naming/money-column-suffix` — Денежные — суффикс по назначению:

`_amount` для сумм (`total_amount`), `_price` для цен (`shipping_price`), `_rate` для курсов и процентов (`exchange_rate`, `discount_rate`).

### `pg-naming/duration-unit-in-name` — Длительности — суффикс с явной единицей:

`_seconds`/`_ms`/`_days`/`_hours`. Без неё через год никто не помнит, в чём `delivery_time`.

### `pg-naming/enum-column-plain-name` — Перечисления — без префикса/суффикса:

`status`, `type`, `kind`, `role`, `currency`. В Java мапится на одноимённый `enum`.

### `pg-naming/count-column-suffix` — Размер коллекции — `_count` суффикс:

`view_count`, `likes_count`, `items_count`.

## 4. Audit-колонки

### `pg-naming/audit-columns-set` — Стандартный набор для бизнес-таблицы:
```sql
created_at  timestamptz NOT NULL DEFAULT now(),
updated_at  timestamptz NOT NULL DEFAULT now(),
created_by  bigint REFERENCES customer(id),
updated_by  bigint REFERENCES customer(id),
version     bigint NOT NULL DEFAULT 0   -- для optimistic locking
```

### `pg-naming/soft-delete-keeps-moment` — Soft-delete — `deleted_at timestamptz`, не `is_deleted boolean`

`deleted_at IS NULL` тривиально превращается в boolean, но boolean теряет момент удаления.

## 5. Индексы и constraints

### `pg-naming/index-constraint-prefix` — Префикс по типу + таблица + колонки:

| Тип | Префикс | Пример |
|---|---|---|
| Обычный индекс | `ix_` | `ix_order_status_created_at` |
| Уникальный | `uk_` | `uk_customer_email` |
| Foreign key | `fk_` | `fk_order_item_order_id` |
| Check | `ck_` | `ck_order_total_positive` |
| Trigger | `tr_` | `tr_order_doc_audit` |

### `pg-naming/index-name-reflects-shape` — Composite-индекс

— поля в порядке индекса: `ix_order_status_created_at` для `(status, created_at)`.

### `pg-naming/index-name-reflects-shape` — Functional index

— суффикс с операцией: `ix_account_email_lower`, `ix_event_log_payload_gin`.

### `pg-naming/index-name-reflects-shape` — Partial index

— суффикс с фильтром: `ix_order_active_customer` для `WHERE status IN ('NEW','PAID','SHIPPED')`.

### `pg-naming/index-constraint-prefix` — Foreign key constraint — `fk_<child>_<column>`:

`CONSTRAINT fk_order_item_order_id FOREIGN KEY (order_id) REFERENCES order_doc(id)`. Без явного имени PG генерит длинное `<child>_<col>_fkey`.

### `pg-naming/index-constraint-prefix` — Check constraint — `ck_<table>_<rule>`:

`CONSTRAINT ck_order_total_positive CHECK (total_amount >= 0)`. В сообщении ошибки сразу понятно, какое правило сломано.

## 6. Зарезервированные слова

### `pg-naming/no-reserved-words` — Не используй имена-зарезервированные слова:

`user`, `order`, `group`, `type`, `position`, `value`, `name`, `default`, `desc`, `asc`, `start`, `end`, `class`. Бери `customer`/`account`, `order_doc`/`purchase`, `category`/`group_kind`.

Полный список: `SELECT * FROM pg_get_keywords() WHERE catcode IN ('R', 'T')`.

## 7. Длина

### `pg-naming/short-names-consistent-abbreviations` — Лимит PG — 63 символа

(`NAMEDATALEN - 1`). PG молча обрежет более длинное имя.

### `pg-naming/short-names-consistent-abbreviations` — Целевая длина — до 30 символов

Имена видны в `EXPLAIN`, в логах, в jOOQ-генерации.

### `pg-naming/short-names-consistent-abbreviations` — Сокращения — единые по проекту

Если решили `usr` вместо `user` — везде `usr`.

## 8. View и MV

### `pg-naming/view-suffix` — View — суффикс `_v`. Materialized view — `_mv`:

`customer_active_v`, `order_stats_mv`. Помогает в `EXPLAIN` понять, что это не базовая таблица.

## 9. Антипаттерны

`pg-naming/table-singular-noun` `tbl_`/`t_` префикс на таблицах — избыточно.

`pg-naming/time-column-suffix` `<column>_<datatype>` суффикс — `name_varchar`, `created_timestamp`. Тип в DDL, имя — про смысл.

`pg-naming/snake-case-no-quotes` `"user"`, `"order"` в кавычках — переименовать.

`pg-naming/soft-delete-keeps-moment` `deleted` boolean без `_at` — теряется момент.

`pg-naming/document-column-meaningful-name` `data` / `info` / `details` jsonb — что в нём, никто не помнит. Имя должно говорить о содержимом: `attributes`, `payload`, `metadata`, `config`.

`pg-naming/short-names-consistent-abbreviations` Сокращения по вкусу разработчика — `cust_id`, `usr_nm`, `cnt`. Полные имена короче не делают, читаются хуже.

---

## Чек-лист на ревью

- [ ] Все идентификаторы в `snake_case`, без двойных кавычек.
- [ ] Таблицы — едино singular или едино plural.
- [ ] PK-колонка — `id`. FK — `<parent>_id`.
- [ ] Boolean — с префиксом `is_`/`has_`/`can_`.
- [ ] Времена — `_at` для timestamp, `_on` для date.
- [ ] Деньги — суффикс `_amount`/`_price`/`_rate`.
- [ ] Длительности — суффикс с единицей измерения.
- [ ] Audit: `created_at`, `updated_at`, `version`. Soft-delete через `deleted_at`.
- [ ] Индексы и constraints с префиксами `ix_`/`uk_`/`fk_`/`ck_`.
- [ ] Все CHECK имеют явное имя (`CONSTRAINT ck_...`).
- [ ] Имена ≤ 30 символов, без зарезервированных слов.
- [ ] Нет `data`/`info` jsonb с непонятным содержимым.
