---
name: ucp-pg-explain-review
description: Ревью индексов и плана запроса PostgreSQL. На вход — DDL индексов и/или вывод `EXPLAIN (ANALYZE, BUFFERS)`. Проверяет левый префикс composite, селективность, типы индексов (B-tree/GIN/GiST/BRIN/pg_trgm/partial/INCLUDE), нарушения по плану (`Filter` вместо `Index Cond`, `Heap Fetches > 0`, `Rows Removed by Filter` миллионы, `external merge Disk`, неиспользуемый Nested Loop). Вызывается при тормозящих запросах, добавлении индексов, ревью миграций с `CREATE INDEX`.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью индексов и плана запроса

Ты ревьюишь индексы и планы PostgreSQL на соответствие командному стилю.

## Зависимости

- **`.claude/docs/pg-indexes-style-guide.md`** в проекте (или из `claude-code-java`) — источник правил. Коды `PG-I-NNN` (индексы) и `PG-E-NNN` (план/runtime).

## Инструкции

1. **Прочти style guide** из `.claude/docs/pg-indexes-style-guide.md`. Цитируй коды правил в каждой находке.

2. **Определи режим работы:**
   - **Ревью DDL индексов** (если пользователь дал миграцию или ты видишь `CREATE INDEX` в `git diff`) — проверяй порядок полей, дубликаты, тип индекса, `CONCURRENTLY`.
   - **Ревью плана** (если пользователь дал `EXPLAIN ANALYZE`) — читай план снизу вверх, ищи узкое место, цитируй `PG-E-*`.
   - **Ревью DDL + плана вместе** — самый полезный кейс. Сначала прокомментируй индекс, потом план.

3. **При ревью плана — обязательно запроси/получи:**
   - Текст запроса.
   - Вывод `EXPLAIN (ANALYZE, BUFFERS)` (не просто `EXPLAIN`).
   - DDL индексов на затронутых таблицах (если есть).
   - Если плана не дано — попроси у пользователя:
     ```
     Для ревью плана нужен:
     EXPLAIN (ANALYZE, BUFFERS) <запрос>;
     ```

4. **Сгруппируй вывод** по типу: критично (план кривой / индекс бесполезный), важно (можно сильно улучшить), наблюдение (почему оптимизатор так решил).

5. **В конце — конкретный план действий** (один-два DDL-statement или ANALYZE/VACUUM, не «провести аудит схемы»).

## Чек-лист правил при ревью DDL индексов

### Composite (`PG-I-010` — `PG-I-014`)

- `PG-I-012` Первое поле — то, что чаще всего в `WHERE` с `=`. Проверь по типичным запросам.
- `PG-I-013` Range-поле (`>`, `<`, `BETWEEN`, `LIKE 'x%'`) — последним.
- `PG-I-014` Если индекс предназначен для `ORDER BY` — направления должны совпадать (или быть обратными — Index Scan Backward).

### Управление (`PG-I-015` — `PG-I-019`)

- `PG-I-015` Дубликаты: нет ли `(a)` поверх `(a, b, c)`.
- `PG-I-017` FK имеет покрывающий индекс (если по нему джойнят / удаляют родителя).
- `PG-I-018` `LOWER()`/`COALESCE()` в `WHERE` — должен быть functional index.
- `PG-I-019` В продакшен-миграциях — `CREATE INDEX CONCURRENTLY`. Без — критично.

### Типы индексов (`PG-I-020` — `PG-I-026`)

- `PG-I-020` По умолчанию — B-tree.
- `PG-I-022` JSONB — GIN (`jsonb_path_ops` для `@>` или дефолтный для `?`).
- `PG-I-023` Range-типы / геометрия — GiST.
- `PG-I-024` BRIN — рассмотри для append-only таблиц > 50M строк.
- `PG-I-025` `LIKE '%X%'` — GIN с `pg_trgm`, не B-tree.
- `PG-I-026` Partial — если индекс нужен только для подмножества.

### Селективность (`PG-I-030` — `PG-I-037`)

- `PG-I-031` Индекс на низкоселективную колонку (≤5 значений на 1М строк) — обычно бесполезен.
- `PG-I-032` Проверяй `pg_stats`: `n_distinct`, `most_common_freqs`.
- `PG-I-035` После массовой загрузки — `ANALYZE`.

## Чек-лист правил при ревью EXPLAIN

### Общие (`PG-E-030` — `PG-E-032`)

- `PG-E-030` Должен быть `EXPLAIN (ANALYZE, BUFFERS)`. Без `BUFFERS` — попроси повторить.
- `PG-E-031` `rows=` оценка vs `actual rows=`. Расхождение 10x+ → `ANALYZE`.
- `PG-E-032` Реальное время = `actual time × loops`.

### Индексы используются неправильно (`PG-E-033` — `PG-E-035`, `PG-E-010` — `PG-E-012`)

- `PG-E-033` Условие в `Filter:` вместо `Index Cond:` → индекс не используется как ключ.
- `PG-E-034` `Heap Fetches > 0` на Index Only Scan → `VACUUM`.
- `PG-E-035` `Recheck Cond:` → lossy bitmap, теряется эффективность.
- `PG-E-010` `count(1)` через Index Only Scan по «неподходящему» индексу: формально использует индекс, но как полный проход. На больших таблицах — нужен индекс по фильтрующему полю.
- `PG-E-012` Если `Heap Fetches > 0` и Index Only Scan медленнее ожиданий → запусти `VACUUM` и переснимите план.

### Память и сортировка (`PG-E-036` — `PG-E-037`)

- `PG-E-036` Hash Join `Batches: > 1` → `work_mem` мал, увеличь для сессии.
- `PG-E-037` `Sort Method: external merge Disk:` → увеличь `work_mem` или добавь индекс с нужным порядком.

### Параллелизм (`PG-E-038`)

- `PG-E-038` Параллельный план оправдан на больших данных. На мелких — оверхед запуска worker'ов больше выигрыша.

## Формат вывода

### Ревью DDL индексов

```
[критично] PG-I-019 ix_orders_status_created создаётся без CONCURRENTLY.
   На бою это ACCESS EXCLUSIVE lock на orders на 5–15 минут — все INSERT/UPDATE заблокированы.
   Должно быть: CREATE INDEX CONCURRENTLY ix_orders_status_created ON orders (status, created_at);
   В Liquibase: <createIndex ... concurrent="true"/> + runInTransaction="false".

[важно] PG-I-013 ix_orders_at_status порядок полей.
   Текущий: (created_at, status). При WHERE status='NEW' AND created_at > X
   индекс отсканирует все недавние записи и отфильтрует по status пост-фильтром.
   Должно быть: (status, created_at) — равенство первым, range последним.
```

### Ревью плана

```
EXPLAIN показывает:
  Seq Scan on orders  (cost=0.00..18334.00 rows=400000 width=...)
    (actual time=0.012..89.123 rows=42137 loops=1)
    Filter: (status = 'PAID')
    Rows Removed by Filter: 957863

[важно] PG-E-031 Оценка планировщика 400К строк, реально 42К — расхождение 10x.
   Статистика устарела. Запусти: ANALYZE orders;

[важно] PG-I-031 Селективность status — у тебя 'PAID' = 4% строк (см. pg_stats).
   Это в пределах, где индекс должен помочь. Но индекса по status нет → Seq Scan.
   Создай: CREATE INDEX CONCURRENTLY ix_orders_status ON orders (status);
   Если запрос часто включает фильтр по дате → (status, created_at).

План действий:
1. ANALYZE orders;
2. CREATE INDEX CONCURRENTLY ix_orders_status_created ON orders (status, created_at);
3. Перезапусти EXPLAIN ANALYZE — должен стать Index Scan.
```

## Что не входит

- Типы колонок и DDL без индексов — это `ucp-pg-schema-review`.
- Миграционные операции с локами и expand-contract — `ucp-pg-migration-review` (когда появится).
- Профилирование на уровне приложения / GC / connection pool — за пределами скилла.
