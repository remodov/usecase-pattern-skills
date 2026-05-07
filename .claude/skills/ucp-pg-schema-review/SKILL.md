---
name: ucp-pg-schema-review
description: Ревью PostgreSQL-схемы и миграций (DDL Liquibase / Flyway / сырой SQL) против командного PG Types Style Guide. Проверяет типы колонок (числа, строки, время, UUID, JSONB, массивы, range), boolean, enum, антипаттерны (`varchar(255)`, `timestamp` без TZ, `varchar(36)` для UUID, `float` для денег, `serial`). Вызывается на каждый PR с DDL-файлами в `db/changelog/`, `migrations/`, `src/main/resources/db/`.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью PostgreSQL-схемы

Ты ревьюишь DDL-миграции PostgreSQL на соответствие командному стилю.

## Зависимости

- **`.claude/docs/pg-types-style-guide.md`** в проекте (или из `claude-code-java`) — единственный источник правил. У каждого правила код `PG-T-NNN`.

## Инструкции

1. **Прочти style guide** из `.claude/docs/pg-types-style-guide.md`. Цитируй коды `PG-T-NNN` в каждой находке.

2. **Определи область ревью.** Если пользователь указал файл — ревью этого файла. Иначе — `git diff` против main / develop, ищи изменения в:
   - `db/changelog/**/*.{xml,sql,yml,json}` (Liquibase)
   - `db/migration/**/V*.sql` (Flyway)
   - `src/main/resources/db/**`
   - Любые `*.sql` с `CREATE TABLE` / `ALTER TABLE`.

3. **Пройди по каждой DDL-операции** и проверь по списку правил (см. ниже). Для каждой находки:
   - Цитируй код правила (`PG-T-013`).
   - Покажи проблемный фрагмент DDL.
   - Покажи как должно быть.
   - Дай ссылку: <https://vikulin-va.ru/pg/{section}/>.

4. **Сгруппируй вывод** по категориям: критично (`PG-T-082`/`-083`/`-091` — необратимое или ломающее), важно (типы id, время), мелкое (стилистика).

5. **В конце — чек-лист** «всё проверено» (см. в style guide).

## Чек-лист правил

### Числа (`PG-T-010` — `PG-T-016`)

- `PG-T-010` PK = `bigint GENERATED ALWAYS AS IDENTITY` (или `uuid`). Не `int`/`integer`/`serial`/`bigserial`.
- `PG-T-013` Денежные колонки = `numeric(p, s)`. Не `float`/`real`/`double precision`/`money`.
- `PG-T-014` Тип `money` запрещён. → `numeric` + `currency char(3)`.
- `PG-T-016` Boolean = `boolean`. Не `smallint 0/1`/`char(1)`/`varchar('Y'/'N')`.

### Строки (`PG-T-020` — `PG-T-025`)

- `PG-T-020` Без бизнес-причины — `text`, не `varchar(255)` / `varchar(N)` с произвольным `N`.
- `PG-T-021` `varchar(N)` оправдан только под доменное правило (E.164, ISO-страна, ИНН).
- `PG-T-022` `char(N)` — только строго фиксированная длина из стандарта.
- `PG-T-023` Case-insensitive — `citext` или functional unique index `(lower(...))`.

### Время (`PG-T-030` — `PG-T-035`)

- `PG-T-030` Бизнес-время = `timestamptz`. `timestamp without time zone` / `timestamp` для бизнес-времени = критическая ошибка.
- `PG-T-032` `timestamp` (без TZ) допустим только для локального времени без момента (расписание магазина) — должна быть рядом колонка с зоной.

### UUID (`PG-T-040` — `PG-T-044`)

- `PG-T-040` UUID = тип `uuid`. Не `varchar(36)`/`char(36)`/`text`.
- `PG-T-044` При UUID-PK: дочерние таблицы должны иметь индекс по FK.

### Enum (`PG-T-050` — `PG-T-052`)

- `PG-T-051` Если перечисление может расти / иметь атрибуты — reference table, не PG `ENUM`.
- `PG-T-051` Если простое техническое ≤7 значений — `ENUM` или `CHECK IN`.

### JSONB (`PG-T-060` — `PG-T-067`)

- `PG-T-060` Всегда `jsonb`, не `json`.
- `PG-T-061` Если по полю фильтруют/сортируют/джойнят — выноси в колонку, не оставляй в JSONB.
- `PG-T-067` В JSONB не должно быть бинарей/большого текста/base64.

### Массивы и range (`PG-T-070` — `PG-T-074`)

- `PG-T-071` Массив объектов с атрибутами (`jsonb[]` для строк заказа) — антипаттерн, нужна отдельная таблица.
- `PG-T-072` Сущность-интервал (тариф, бронь, период) → range-тип.
- `PG-T-073` Для непересечения интервалов → `EXCLUDE USING gist` constraint.
- `PG-T-074` Range с границей `[)` по умолчанию.

### Антипаттерны (сводно — `PG-T-080` — `PG-T-093`)

Эти 14 правил повторяют категории выше — используй их когда ссылаешься на «классический» антипаттерн в одном слове.

## Формат вывода

```
[критично] PG-T-091 customer.created_at: timestamp without time zone для бизнес-времени.
   В Java маппинг будет на LocalDateTime → разные значения на UTC-сервере и MSK-разработке.
   Должно быть: created_at timestamptz NOT NULL DEFAULT now()
   См. https://vikulin-va.ru/pg/time/

[важно] PG-T-082 customer.public_id: varchar(36) для UUID.
   Размер 36+ байт vs 16, нет валидации формата на вставке, чувствительно к регистру.
   Должно быть: public_id uuid NOT NULL DEFAULT gen_random_uuid()
   См. https://vikulin-va.ru/pg/uuid/

[мелкое] PG-T-080 customer.full_name: varchar(255) без бизнес-обоснования.
   Должно быть: full_name text NOT NULL
   См. https://vikulin-va.ru/pg/strings/
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
