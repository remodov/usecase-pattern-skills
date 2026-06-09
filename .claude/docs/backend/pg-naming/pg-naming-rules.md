# PostgreSQL Naming — индекс правил

> **Что это.** Сжатый индекс правил `pg-naming-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами и таблицами префиксов — `pg-naming-style-guide.md`**; открывай её точечно по разделу.
> Коды: `PG-N-<NNN>`. X-кодов нет; сводные антипаттерны — `PG-N-09X` в разделе 9.

Базовый принцип: **именование — самая дешёвая дисциплина с долгим эффектом** — через два года команда читает чужой код, DBA не путается в `EXPLAIN`.

## 1. Регистр и стиль
**MUST:**
- **PG-N-001.** `snake_case` для всего (таблицы, колонки, индексы, constraints, sequences, views); без camelCase/PascalCase.
- **PG-N-002.** Никаких кавычек в идентификаторах (`"OrderDoc"` принуждает сохранять регистр и требует кавычек везде).

## 2. Таблицы
**MUST:**
- **PG-N-010.** Существительные в единственном числе (`order_doc`, `customer`); выбрать одно соглашение (singular/plural) и не смешивать.
- **PG-N-011.** Junction-таблицы — обе сущности по порядку (`order_item`, `product_tag`).
- **PG-N-012.** Префикс домена или отдельный schema для крупных схем (`order.doc`, `catalog.product`) — 200 таблиц в одном `public` нечитаемо.

## 3. Колонки
**MUST:**
- **PG-N-020.** id-колонка таблицы — `id` (не `customer_id` в таблице `customer`).
- **PG-N-021.** Foreign key — `<parent>_id` (`customer_id`, `order_id`) — документирует родителя.
- **PG-N-022.** Boolean — с префиксом `is_`/`has_`/`can_` (`is_active`, `has_avatar`).
- **PG-N-023.** Время — глагол прош. времени + `_at` для timestamp (`created_at`, `expires_at`), `_on` для date (`born_on`).
- **PG-N-024.** Денежные — суффикс по назначению: `_amount` (суммы), `_price` (цены), `_rate` (курсы/проценты).
- **PG-N-025.** Длительности — суффикс с явной единицей: `_seconds`/`_ms`/`_days`/`_hours`.
- **PG-N-026.** Перечисления — без префикса/суффикса (`status`, `type`, `role`, `currency`); мапятся на одноимённый Java enum.
- **PG-N-027.** Размер коллекции — `_count` (`view_count`, `items_count`).

## 4. Audit-колонки
**MUST:**
- **PG-N-030.** Стандартный набор: `created_at`, `updated_at` (`timestamptz NOT NULL DEFAULT now()`), `created_by`/`updated_by`, `version bigint` (optimistic locking).
- **PG-N-031.** Soft-delete — `deleted_at timestamptz`, не `is_deleted boolean` (boolean теряет момент удаления).

## 5. Индексы и constraints
**MUST:**
- **PG-N-040.** Префикс по типу + таблица + колонки: `ix_` (индекс), `uk_` (уникальный), `fk_` (FK), `ck_` (check), `tr_` (trigger).
- **PG-N-041.** Composite-индекс — поля в порядке индекса (`ix_order_status_created_at` для `(status, created_at)`).
- **PG-N-042.** Functional index — суффикс с операцией (`ix_account_email_lower`, `ix_event_log_payload_gin`).
- **PG-N-043.** Partial index — суффикс с фильтром (`ix_order_active_customer`).
- **PG-N-044.** FK constraint — `fk_<child>_<column>` (без явного имени PG генерит длинное `<child>_<col>_fkey`).
- **PG-N-045.** Check constraint — `ck_<table>_<rule>` (`ck_order_total_positive`) — в ошибке сразу видно правило.

## 6. Зарезервированные слова
**MUST:**
- **PG-N-050.** Не использовать имена-зарезервированные слова (`user`, `order`, `group`, `type`, `value`, `name`, `desc`, `end`, …); брать `customer`/`account`, `order_doc`/`purchase`. Список: `pg_get_keywords() WHERE catcode IN ('R','T')`.

## 7. Длина
**MUST:**
- **PG-N-060.** Лимит PG — 63 символа (`NAMEDATALEN-1`), PG молча обрежет длиннее.
- **PG-N-061.** Целевая длина — до 30 символов (видны в `EXPLAIN`, логах, кодогенерации клиента).
- **PG-N-062.** Сокращения — единые по проекту (решили `usr` → везде `usr`).

## 8. View и MV
**MUST:**
- **PG-N-080.** View — суффикс `_v`, materialized view — `_mv` (`customer_active_v`, `order_stats_mv`).

## 9. Антипаттерны
**MUST NOT:**
- **PG-N-090.** `tbl_`/`t_` префикс на таблицах — избыточно.
- **PG-N-091.** `<column>_<datatype>` суффикс (`name_varchar`, `created_timestamp`) — тип в DDL, имя про смысл.
- **PG-N-092.** `"user"`, `"order"` в кавычках — переименовать.
- **PG-N-093.** `deleted` boolean без `_at` — теряется момент.
- **PG-N-094.** `data`/`info`/`details` jsonb — имя должно говорить о содержимом (`attributes`, `payload`, `metadata`, `config`).
- **PG-N-095.** Сокращения по вкусу (`cust_id`, `usr_nm`, `cnt`) — полные имена короче не делают, читаются хуже.
