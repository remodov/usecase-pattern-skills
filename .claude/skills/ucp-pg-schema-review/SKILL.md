---
lang: any
name: ucp-pg-schema-review
description: Ревью PostgreSQL-схемы и DDL-миграций (Liquibase/Flyway/сырой SQL) против требований pg-types/* — типы колонок, boolean, enum, антипаттерны varchar(255), timestamp без TZ, float для денег, serial.
when_to_use: Каждый PR с DDL-файлами в db/changelog/, db/migration/, src/main/resources/db/.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью PostgreSQL-схемы

Ты ревьюишь DDL-миграции PostgreSQL на соответствие командному стилю.

## Зависимости

- **`.claude/docs/backend/pg-types/spec.md`** — типы колонок (`PG-T-NNN`).
- **`.claude/docs/backend/pg-naming/spec.md`** — конвенции именования (`PG-N-NNN`).
- **`.claude/docs/backend/pg-partitioning/spec.md`** — партиционирование (`PG-P-NNN`).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/pg-types/spec.md` (полный текст с примерами и таблицами соответствия типов — `backend/pg-types/references/implementation.md`, открывай точечно по разделу). Цитируй коды `PG-T-NNN` в каждой находке.

2. **Определи область ревью.** Если пользователь указал файл — ревью этого файла. Иначе — `git diff` против main / develop, ищи изменения в:
   - `db/changelog/**/*.{xml,sql,yml,json}` (Liquibase)
   - `db/migration/**/V*.sql` (Flyway)
   - `src/main/resources/db/**`
   - Любые `*.sql` с `CREATE TABLE` / `ALTER TABLE`.

3. **Пройди по каждой DDL-операции** и проверь по списку правил (см. ниже). Для каждой находки:
   - Цитируй код правила (`pg-types/money-is-numeric`).
   - Покажи проблемный фрагмент DDL.
   - Покажи как должно быть.

4. **Сгруппируй вывод** по категориям: критично (`pg-types/uuid-is-uuid-type`/`-083`/`-091` — необратимое или ломающее), важно (типы id, время), мелкое (стилистика).

5. **В конце — чек-лист** «всё проверено» (см. в требованиях).

## Чек-лист правил

### Числа (`pg-types/pk-bigint-identity` — `pg-types/boolean-is-boolean`)

- `pg-types/pk-bigint-identity` (`pg-types/pk-bigint-identity`) PK = `bigint GENERATED ALWAYS AS IDENTITY` (или `uuid`). Не `int`/`integer`/`serial`/`bigserial`.
- `pg-types/money-is-numeric` (`pg-types/money-is-numeric`) Денежные колонки = `numeric(p, s)`. Не `float`/`real`/`double precision`/`money`.
- `pg-types/money-is-numeric` (`pg-types/money-is-numeric`) Тип `money` запрещён. → `numeric` + `currency char(3)`.
- `pg-types/boolean-is-boolean` (`pg-types/boolean-is-boolean`) Boolean = `boolean`. Не `smallint 0/1`/`char(1)`/`varchar('Y'/'N')`.

### Строки (`pg-types/text-by-default` — `pg-types/no-premature-column-split`)

- `pg-types/text-by-default` (`pg-types/text-by-default`) Без бизнес-причины — `text`, не `varchar(255)` / `varchar(N)` с произвольным `N`.
- `pg-types/varchar-when-domain-rule` (`pg-types/varchar-when-domain-rule`) `varchar(N)` оправдан только под доменное правило (E.164, ISO-страна, ИНН).
- `pg-types/varchar-when-domain-rule` (`pg-types/varchar-when-domain-rule`) `char(N)` — только строго фиксированная длина из стандарта.
- `pg-types/case-insensitive-via-citext` (`pg-types/case-insensitive-via-citext`) Case-insensitive — `citext` или functional unique index `(lower(...))`.

### Время (`pg-types/business-time-is-timestamptz` — `pg-types/intervals-not-magic-seconds`)

- `pg-types/business-time-is-timestamptz` (`pg-types/business-time-is-timestamptz`) Бизнес-время = `timestamptz`. `timestamp without time zone` / `timestamp` для бизнес-времени = критическая ошибка.
- `pg-types/business-time-is-timestamptz` (`pg-types/business-time-is-timestamptz`) `timestamp` (без TZ) допустим только для локального времени без момента (расписание магазина) — должна быть рядом колонка с зоной.

### UUID (`pg-types/uuid-is-uuid-type` — `pg-types/index-fk-under-uuid-pk`)

- `pg-types/uuid-is-uuid-type` (`pg-types/uuid-is-uuid-type`) UUID = тип `uuid`. Не `varchar(36)`/`char(36)`/`text`.
- `pg-types/index-fk-under-uuid-pk` (`pg-types/index-fk-under-uuid-pk`) При UUID-PK: дочерние таблицы должны иметь индекс по FK.

### Enum (`pg-types/boolean-is-boolean` — `pg-types/typed-enum-in-code`)

- `pg-types/enum-vs-reference-table` (`pg-types/enum-vs-reference-table`) Если перечисление может расти / иметь атрибуты — reference table, не PG `ENUM`.
- `pg-types/enum-vs-reference-table` (`pg-types/enum-vs-reference-table`) Если простое техническое ≤7 значений — `ENUM` или `CHECK IN`.

### JSONB (`pg-types/jsonb-not-json` — `pg-types/no-binary-in-jsonb`)

- `pg-types/jsonb-not-json` (`pg-types/jsonb-not-json`) Всегда `jsonb`, не `json`.
- `pg-types/jsonb-for-peripheral-attributes` (`pg-types/jsonb-for-peripheral-attributes`) Если по полю фильтруют/сортируют/джойнят — выноси в колонку, не оставляй в JSONB.
- `pg-types/no-binary-in-jsonb` (`pg-types/no-binary-in-jsonb`) В JSONB не должно быть бинарей/большого текста/base64.

### Массивы и range (`pg-types/array-for-simple-scalars` — `pg-types/range-for-intervals`)

- `pg-types/array-for-simple-scalars` (`pg-types/array-for-simple-scalars`) Массив объектов с атрибутами (`jsonb[]` для строк заказа) — антипаттерн, нужна отдельная таблица.
- `pg-types/range-for-intervals` (`pg-types/range-for-intervals`) Сущность-интервал (тариф, бронь, период) → range-тип.
- `pg-types/exclude-constraint-for-overlap` (`pg-types/exclude-constraint-for-overlap`) Для непересечения интервалов → `EXCLUDE USING gist` constraint.
- `pg-types/range-for-intervals` (`pg-types/range-for-intervals`) Range с границей `[)` по умолчанию.

### Антипаттерны (сводно — `pg-types/text-by-default` — `pg-types/uuid-v7-for-keys`)

Эти 14 правил повторяют категории выше — используй их когда ссылаешься на «классический» антипаттерн в одном слове.

### Именование (`PG-N-NNN`) — обязательно проверяй на каждом DDL

- `pg-naming/snake-case-no-quotes`/`002` snake_case без двойных кавычек.
- `pg-naming/table-singular-noun` (`pg-naming/table-singular-noun`) Таблицы — едино singular или plural.
- `pg-naming/pk-named-id` (`pg-naming/pk-named-id`) PK — `id`, не `<table>_id`.
- `pg-naming/fk-column-names-parent` (`pg-naming/fk-column-names-parent`) FK — `<parent>_id`.
- `pg-naming/boolean-column-prefix` (`pg-naming/boolean-column-prefix`) Boolean с префиксом `is_`/`has_`/`can_`.
- `pg-naming/time-column-suffix` (`pg-naming/time-column-suffix`) Времена — `_at`/`_on`.
- `pg-naming/money-column-suffix`/`025` Деньги/длительности с осмысленным суффиксом.
- `pg-naming/audit-columns-set` (`pg-naming/audit-columns-set`) Audit-набор: `created_at`, `updated_at`, `version`.
- `pg-naming/soft-delete-keeps-moment` (`pg-naming/soft-delete-keeps-moment`) Soft-delete через `deleted_at`, не `is_deleted`.
- `pg-naming/index-constraint-prefix`–`045` Префиксы `ix_`/`uk_`/`fk_`/`ck_`. CHECK с явным именем.
- `pg-naming/no-reserved-words` (`pg-naming/no-reserved-words`) Не зарезервированные слова.
- `pg-naming/short-names-consistent-abbreviations`/`061` Длина ≤ 30 символов.
- `pg-naming/document-column-meaningful-name` (`pg-naming/document-column-meaningful-name`) Не `data`/`info` jsonb для основной модели.

### Партиционирование (`PG-P-NNN`) — если вижу `PARTITION BY` в DDL

- `pg-partitioning/partition-only-when-justified` (`pg-partitioning/partition-only-when-justified`) Таблица > 50 GB / time-series / multi-tenant — оправдан выбор.
- `pg-partitioning/pk-includes-partition-key` (`pg-partitioning/pk-includes-partition-key`) PK включает ключ партиционирования.
- `pg-partitioning/key-present-in-queries` (`pg-partitioning/key-present-in-queries`) Ключ в `WHERE` большинства запросов.
- `pg-partitioning/partition-size-range` (`pg-partitioning/partition-size-range`) Размер партиции 1–50 GB.
- `pg-partitioning/create-partitions-ahead` (`pg-partitioning/create-partitions-ahead`) Есть план автоматического создания новых партиций.
- `pg-partitioning/partition-key-immutable` (`pg-partitioning/partition-key-immutable`) Partition key не обновляется в типичных операциях.

## Формат вывода

```
[критично] pg-types/time-mapping-keeps-zone (PG-T-091) customer.created_at: timestamp without time zone для бизнес-времени.
   В Java маппинг будет на LocalDateTime → разные значения на UTC-сервере и MSK-разработке.
   Должно быть: created_at timestamptz NOT NULL DEFAULT now()

[важно] pg-types/uuid-is-uuid-type (PG-T-082) customer.public_id: varchar(36) для UUID.
   Размер 36+ байт vs 16, нет валидации формата на вставке, чувствительно к регистру.
   Должно быть: public_id uuid NOT NULL DEFAULT gen_random_uuid()

[мелкое] PG-T-080 customer.full_name: varchar(255) без бизнес-обоснования.
   Должно быть: full_name text NOT NULL
```

В конце:

```
Сводно: 1 критично, 1 важно, 1 мелкое.
Перед merge: исправить критичное (timestamp). Остальное — желательно в этом же PR.
```

## Что не входит

- Производительность запросов и индексы — это `ucp-pg-explain-review`.
- Миграционные операции (`ALTER TABLE` локи, `CONCURRENTLY`, expand-contract) — это `ucp-pg-migration-review` (когда появится).
- Если в PR есть и DDL, и Java-код — для Java вызывай `ucp-pattern-review` отдельно.
