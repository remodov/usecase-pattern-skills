---
lang: any
name: ucp-pg-explain-review
description: Ревью индексов и плана запроса PostgreSQL (требования pg-indexes/*) — левый префикс composite, селективность, типы индексов (B-tree/GIN/BRIN/partial/INCLUDE), Filter вместо Index Cond, Heap Fetches, external merge Disk.
when_to_use: Тормозящие запросы, добавление индексов, миграции с CREATE INDEX, вывод EXPLAIN (ANALYZE, BUFFERS).
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью индексов и плана запроса

Ты ревьюишь индексы и планы PostgreSQL на соответствие командному стилю.

## Зависимости

- **`.claude/docs/backend/pg-indexes/spec.md`** в проекте (или из `claude-code-java`) — источник правил. Коды `PG-I-NNN` (индексы) и `PG-E-NNN` (план/runtime).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/pg-indexes/spec.md` (полный текст с SQL-примерами и таблицей узлов плана — `backend/pg-indexes/references/implementation.md`, открывай точечно по разделу). Цитируй коды правил в каждой находке.

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

### Composite (`pg-indexes/composite-left-prefix` — `pg-indexes/order-by-matches-index`)

- `pg-indexes/equality-first-range-last` (`pg-indexes/equality-first-range-last`) Первое поле — то, что чаще всего в `WHERE` с `=`. Проверь по типичным запросам.
- `pg-indexes/equality-first-range-last` (`pg-indexes/equality-first-range-last`) Range-поле (`>`, `<`, `BETWEEN`, `LIKE 'x%'`) — последним.
- `pg-indexes/order-by-matches-index` (`pg-indexes/order-by-matches-index`) Если индекс предназначен для `ORDER BY` — направления должны совпадать (или быть обратными — Index Scan Backward).

### Управление (`pg-indexes/no-redundant-prefix-index` — `pg-migrations/index-concurrently`)

- `pg-indexes/no-redundant-prefix-index` (`pg-indexes/no-redundant-prefix-index`) Дубликаты: нет ли `(a)` поверх `(a, b, c)`.
- `pg-indexes/index-foreign-keys` (`pg-indexes/index-foreign-keys`) FK имеет покрывающий индекс (если по нему джойнят / удаляют родителя).
- `pg-indexes/functional-index-matches-expression` (`pg-indexes/functional-index-matches-expression`) `LOWER()`/`COALESCE()` в `WHERE` — должен быть functional index.
- `pg-migrations/index-concurrently` (`pg-migrations/index-concurrently`) (`pg-migrations/index-concurrently`) В продакшен-миграциях — `CREATE INDEX CONCURRENTLY`. Без — критично.

### Типы индексов (`pg-indexes/btree-by-default` — `pg-indexes/partial-index-for-subset`)

- `pg-indexes/btree-by-default` (`pg-indexes/btree-by-default`) По умолчанию — B-tree.
- `pg-indexes/gin-for-documents-and-search` (`pg-indexes/gin-for-documents-and-search`) JSONB — GIN (`jsonb_path_ops` для `@>` или дефолтный для `?`).
- `pg-indexes/gist-for-ranges-and-geometry` (`pg-indexes/gist-for-ranges-and-geometry`) Range-типы / геометрия — GiST.
- `pg-indexes/brin-for-append-only` (`pg-indexes/brin-for-append-only`) BRIN — рассмотри для append-only таблиц > 50M строк.
- `pg-indexes/gin-for-documents-and-search` (`pg-indexes/gin-for-documents-and-search`) `LIKE '%X%'` — GIN с `pg_trgm`, не B-tree.
- `pg-indexes/partial-index-for-subset` (`pg-indexes/partial-index-for-subset`) Partial — если индекс нужен только для подмножества.

### Селективность (`pg-indexes/selectivity-decides` — `pg-indexes/extended-statistics-for-correlated-columns`)

- `pg-indexes/selectivity-decides` (`pg-indexes/selectivity-decides`) Индекс на низкоселективную колонку (≤5 значений на 1М строк) — обычно бесполезен.
- `pg-indexes/keep-statistics-fresh` (`pg-indexes/keep-statistics-fresh`) Проверяй `pg_stats`: `n_distinct`, `most_common_freqs`.
- `pg-indexes/keep-statistics-fresh` (`pg-indexes/keep-statistics-fresh`) После массовой загрузки — `ANALYZE`.

## Чек-лист правил при ревью EXPLAIN

### Общие (`pg-indexes/explain-with-analyze-and-buffers` — `pg-indexes/estimate-versus-actual`)

- `pg-indexes/explain-with-analyze-and-buffers` (`pg-indexes/explain-with-analyze-and-buffers`) Должен быть `EXPLAIN (ANALYZE, BUFFERS)`. Без `BUFFERS` — попроси повторить.
- `pg-indexes/estimate-versus-actual` (`pg-indexes/estimate-versus-actual`) `rows=` оценка vs `actual rows=`. Расхождение 10x+ → `ANALYZE`.
- `pg-indexes/estimate-versus-actual` (`pg-indexes/estimate-versus-actual`) Реальное время = `actual time × loops`.

### Индексы используются неправильно (`pg-indexes/condition-must-be-index-key` — `pg-indexes/work-mem-signals`, `pg-indexes/condition-must-be-index-key` — `pg-indexes/heap-fetches-mean-stale-visibility-map`)

- `pg-indexes/condition-must-be-index-key` (`pg-indexes/condition-must-be-index-key`) Условие в `Filter:` вместо `Index Cond:` → индекс не используется как ключ.
- `pg-indexes/heap-fetches-mean-stale-visibility-map` (`pg-indexes/heap-fetches-mean-stale-visibility-map`) `Heap Fetches > 0` на Index Only Scan → `VACUUM`.
- `pg-indexes/work-mem-signals` (`pg-indexes/work-mem-signals`) `Recheck Cond:` → lossy bitmap, теряется эффективность.
- `pg-indexes/condition-must-be-index-key` (`pg-indexes/condition-must-be-index-key`) `count(1)` через Index Only Scan по «неподходящему» индексу: формально использует индекс, но как полный проход. На больших таблицах — нужен индекс по фильтрующему полю.
- `pg-indexes/heap-fetches-mean-stale-visibility-map` (`pg-indexes/heap-fetches-mean-stale-visibility-map`) Если `Heap Fetches > 0` и Index Only Scan медленнее ожиданий → запусти `VACUUM` и переснимите план.

### Память и сортировка (`pg-indexes/work-mem-signals` — `pg-indexes/work-mem-signals`)

- `pg-indexes/work-mem-signals` (`pg-indexes/work-mem-signals`) Hash Join `Batches: > 1` → `work_mem` мал, увеличь для сессии.
- `pg-indexes/work-mem-signals` (`pg-indexes/work-mem-signals`) `Sort Method: external merge Disk:` → увеличь `work_mem` или добавь индекс с нужным порядком.

### Параллелизм (`pg-indexes/parallel-plan-needs-volume`)

- `pg-indexes/parallel-plan-needs-volume` (`pg-indexes/parallel-plan-needs-volume`) Параллельный план оправдан на больших данных. На мелких — оверхед запуска worker'ов больше выигрыша.

## Формат вывода

### Ревью DDL индексов

```
[критично] pg-migrations/index-concurrently (PG-I-019) (PG-I-019) ix_orders_status_created создаётся без CONCURRENTLY.
   На бою это ACCESS EXCLUSIVE lock на orders на 5–15 минут — все INSERT/UPDATE заблокированы.
   Должно быть: CREATE INDEX CONCURRENTLY ix_orders_status_created ON orders (status, created_at);
   В Liquibase: <createIndex ... concurrent="true"/> + runInTransaction="false".

[важно] pg-indexes/equality-first-range-last (PG-I-013) ix_orders_at_status порядок полей.
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

[важно] pg-indexes/estimate-versus-actual (PG-E-031) Оценка планировщика 400К строк, реально 42К — расхождение 10x.
   Статистика устарела. Запусти: ANALYZE orders;

[важно] pg-indexes/selectivity-decides (PG-I-031) Селективность status — у тебя 'PAID' = 4% строк (см. pg_stats).
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
