# PostgreSQL Indexes & EXPLAIN — реализация

Подход к проектированию индексов и чтению планов запросов в PostgreSQL. Каждое правило имеет код вида `PG-I-NNN` (индексы) или `PG-E-NNN` (EXPLAIN/runtime) — скилл `ucp-pg-explain-review` цитирует эти коды при ревью DDL индексов и планов запросов.

Базовый принцип: **индекс работает только если он соответствует запросу**. Создание индекса по «частому полю» без учёта селективности и левого префиксa составного — самый частый источник «мы добавили индекс, а быстрее не стало».

---

## 1. Composite-индексы и левый префикс

Составной B-tree-индекс `(a, b, c)` физически отсортирован по `a`, внутри каждого значения `a` — по `b`, внутри каждого `b` — по `c`. Это телефонная книга по фамилии-имени-отчеству.

### `pg-indexes/composite-left-prefix` — Индекс работает только на левый префикс полей

| Запрос | Использует `(a, b, c)`? |
|---|---|
| `WHERE a = ?` | да, эффективно |
| `WHERE a = ? AND b = ?` | да |
| `WHERE a = ? AND b = ? AND c = ?` | да |
| `WHERE a = ? AND c = ?` | по `a` — да, `c` доводит как `Filter` |
| `WHERE b = ?` | нет |
| `WHERE c = ?` | нет |

### `pg-indexes/composite-left-prefix` — Порядок написания в `WHERE` не важен — оптимизатор сам переставляет

`WHERE c=3 AND b=2 AND a=1` эквивалентно `WHERE a=1 AND b=2 AND c=3`.

### `pg-indexes/equality-first-range-last` — Первым в индексе — поле, по которому чаще всего идёт `=` в `WHERE`

Селективность вторична.

### `pg-indexes/equality-first-range-last` — Поля с диапазонами (`>`, `<`, `BETWEEN`, `LIKE 'x%'`) — последними

После range-условия следующие поля индекса перестают использоваться как ключ дерева.

### `pg-indexes/order-by-matches-index` — `ORDER BY` — порядок и направление полей должны совпадать с индексом

, иначе будет отдельная сортировка.

---

## 2. Селективность

### `pg-indexes/selectivity-decides` — Селективность колонки = `distinct_values / total_rows`. Чем выше, тем эффективнее индекс

Запрос с равенством, отдающий >20% таблицы, обычно не идёт через индекс — `Seq Scan` дешевле. Запрос отдающий <5% — почти всегда через индекс.

### `pg-indexes/selectivity-decides` — Индекс на низкоселективную колонку (`is_deleted`, `status`, `country` в одной стране) бесполезен

Если 98% строк подходят под условие — выгоднее прочитать всю таблицу одним проходом.

### `pg-indexes/keep-statistics-fresh` — Смотри статистику через `pg_stats`:
```sql
SELECT attname, n_distinct, most_common_vals, most_common_freqs, null_frac
FROM pg_stats WHERE schemaname = 'public' AND tablename = 'orders';
```
- `n_distinct > 0` — абсолютное число уникальных, `< 0` — доля от строк (`-0.05` = 5%).
- `most_common_freqs` — частота топ-значений.

### `pg-indexes/random-page-cost-matches-storage` — На SSD `random_page_cost = 1.1`, не дефолтные 4.0

Дефолт под HDD заставляет планировщик предпочесть seq-scan, когда индекс реально быстрее.

### `pg-indexes/selectivity-decides` — Композитный индекс может ожить там, где single-column бесполезен

`(status, created_at)`: `status='DELIVERED'` (62%) — индекс не пойдёт, но `status='DELIVERED' AND created_at > now()-interval '1 day'` (62% × 0.5% = 0.3%) — пойдёт.

### `pg-indexes/keep-statistics-fresh` — После массовой загрузки/UPDATE — `ANALYZE` руками

Autovacuum триггерится при изменении ~10% таблицы; на быстрых нагрузках не успевает.

### `pg-indexes/extended-statistics-for-correlated-columns` — Если в данных есть редкие пиковые значения, увеличь `default_statistics_target` для колонки:
```sql
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
ANALYZE orders;
```

### `pg-indexes/extended-statistics-for-correlated-columns` — Для коррелирующих колонок — `CREATE STATISTICS` с зависимостями

PostgreSQL по умолчанию считает колонки независимыми и завышает селективность их комбинации в 10–50 раз.

---

## 3. Типы индексов

### `pg-indexes/btree-by-default` — `CREATE INDEX` без указания типа = B-tree. Это правильный выбор в 80–90% случаев

B-tree поддерживает `=`, `<`, `>`, `BETWEEN`, `LIKE 'prefix%'`, `IS NULL`, `ORDER BY`, `UNIQUE`, composite.

### `pg-indexes/btree-by-default` — Hash-индекс почти всегда хуже B-tree. Не берите без явной причины

### `pg-indexes/gin-for-documents-and-search` — GIN — для JSONB, массивов, полнотекста
- `gin (column jsonb_path_ops)` для `@>` запросов (быстрее и меньше дефолтного GIN).
- `gin (column)` для `?`, `?|`, `?&`.
- `gin (to_tsvector('russian', body))` для полнотекста.
- Минус: запись медленнее B-tree.

### `pg-indexes/gist-for-ranges-and-geometry` — GiST — для range-типов, геометрии (PostGIS), kNN, EXCLUDE-constraint

Поддерживает `ORDER BY x <-> point` (kNN).
- GIN vs GiST для текста/массивов: GIN — быстрее на чтение, медленнее на запись; GiST наоборот.

### `pg-indexes/brin-for-append-only` — BRIN — для огромных append-only таблиц с естественной упорядоченностью

(логи событий с timestamp, метрики). Размер крошечный (десятки KB на гигабайты), эффективен на range-запросах. Не ускоряет точечный `=`. Деградирует, если данные не упорядочены физически — нужен `CLUSTER`.

### `pg-indexes/gin-for-documents-and-search` — `LIKE '%X%'` — GIN с расширением `pg_trgm`, не B-tree
```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX ix_name_trgm ON customer USING gin (full_name gin_trgm_ops);
```

### `pg-indexes/partial-index-for-subset` — Partial index — `WHERE`-условие в индексе, если индекс нужен только для подмножества
```sql
CREATE INDEX ix_orders_active ON orders (customer_id) WHERE status IN ('NEW','PAID','SHIPPED');
```
Размер в разы меньше, запись быстрее.

---

## 4. Управление индексами

### `pg-indexes/no-redundant-prefix-index` — Не создавай `(a)`, если уже есть `(a, b, c)` — последний покрывает запросы по `a`

Дубликаты занимают место, замедляют запись, путают планировщик.

### `pg-indexes/covering-index-include` — `INCLUDE` — для покрывающего индекса:
```sql
CREATE INDEX ix_orders_customer_inc
    ON orders (customer_id) INCLUDE (status, created_at, total);
```
Колонки в `INCLUDE` не участвуют в дереве, но хранятся в листьях → Index Only Scan без обращения к таблице.

### `pg-indexes/index-foreign-keys` — PostgreSQL не строит индекс по FK автоматически. Если по FK джойнят / удаляют родителя — индекс нужен

Без — `DELETE` родителя уйдёт в seq-scan child.

### `pg-indexes/functional-index-matches-expression` — Функциональный индекс — для регулярных выражений в `WHERE`:
```sql
CREATE INDEX ix_account_email_lower ON account (lower(email));
```
Запросы должны точно совпадать с выражением.

### `pg-migrations/index-concurrently` — В продакшен-миграциях — всегда `CREATE INDEX CONCURRENTLY` и `DROP INDEX CONCURRENTLY`

Без `CONCURRENTLY` берётся `SHARE` lock → блокировка записи на время построения. С `CONCURRENTLY` — два прохода без блокировки, но не работает в транзакции (Liquibase: `runInTransaction="false"`), при сломанной попытке — `INVALID` индекс надо дропнуть и пересоздать.

---

## 5. EXPLAIN — что просить

### `pg-indexes/explain-with-analyze-and-buffers` — Для диагностики — `EXPLAIN (ANALYZE, BUFFERS)`

Без `ANALYZE` — только оценка; без `BUFFERS` не видно, читалось из кеша или с диска.

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT ... ;
```

⚠️ `EXPLAIN ANALYZE` **выполняет запрос**. Для `INSERT`/`UPDATE`/`DELETE` оборачивай в `BEGIN; ... ROLLBACK;`.

---

## 6. EXPLAIN — узлы плана

| Узел | Что делает | Когда хорошо | Когда плохо |
|---|---|---|---|
| `Seq Scan` | Полный проход таблицы | Маленькая таблица; >20% строк отдаётся | Большая таблица + селективный фильтр без индекса |
| `Index Scan` | Поиск по B-tree + чтение строк из таблицы | Селективный `Index Cond:` | Когда `Filter:` важнее `Index Cond:` — индекс не используется как ключ |
| `Index Only Scan` | Все нужные колонки в индексе, таблица не читается | Часто запрашиваемое подмножество колонок есть в индексе | `Heap Fetches > 0` — visibility map устарел, нужен `VACUUM` |
| `Bitmap Index Scan` + `Bitmap Heap Scan` | Двухфазное: сначала битмап страниц, потом sequential read | Средняя селективность; комбинация нескольких индексов | `Recheck Cond:` указывает на lossy bitmap → теряется эффективность на больших выборках |
| `Nested Loop` | Для каждой строки внешнего — поиск во внутреннем | Малый outer + индекс по join-ключу inner | `loops` × inner_cost огромный → лучше Hash Join |
| `Hash Join` | Меньшее отношение в hash-таблицу, проход по большему | Большие отношения без индексов | `Batches: > 1` — hash не уместился в `work_mem` |
| `Merge Join` | Оба отношения отсортированы, мердж как зипкой | Очень большие отношения с готовой сортировкой | Если `Sort` сверху — почти всегда Hash Join лучше |
| `Sort` | Сортировка | Маленькие данные в `work_mem` | `external merge Disk:` — увеличить `work_mem` или добавить индекс с нужным порядком |
| `HashAggregate` | `GROUP BY` через hash в памяти | `work_mem` хватает | `GroupAggregate` со `Sort` — fallback при нехватке памяти |
| `Limit` | Останавливает выполнение при N строк | Index Scan + Limit для top-N | — |
| `Materialize` | Кеширует подноду в памяти | Внутри Nested Loop повторно используется | — |
| `Gather`/`Gather Merge` | Параллельный план | Большие таблицы | На мелких — оверхед запуска worker'ов |
| `Memoize` (PG14+) | Кеш результатов в Nested Loop | Повторяющиеся inner-подзапросы | — |

---

## 7. EXPLAIN — что искать в плане

### `pg-indexes/estimate-versus-actual` — Сравни `rows=` (оценка) с `actual rows=`. Расхождение в 10x+ → статистика устарела (см. `pg-indexes/keep-statistics-fresh`)

### `pg-indexes/estimate-versus-actual` — Реальное время узла = `actual time × loops`

Узел с `loops=10000` и `actual time=0.5..1.2` — это 12 секунд внутри Nested Loop, не миллисекунды.

### `pg-indexes/condition-must-be-index-key` — Если важное условие в `Filter:`, а не в `Index Cond:` — индекс по этому полю не используется как ключ

Нужно либо новый индекс, либо изменить порядок полей в существующем.

### `pg-indexes/heap-fetches-mean-stale-visibility-map` — `Heap Fetches > 0` на Index Only Scan → visibility map устарел

Помогает `VACUUM`.

### `pg-indexes/work-mem-signals` — `Recheck Cond:` показывает lossy bitmap

— на больших выборках эффективность теряется.

### `pg-indexes/work-mem-signals` — `Buckets ... Batches: > 1` в Hash Join → hash не уместился в `work_mem`. Увеличь `work_mem` для сессии

### `pg-indexes/work-mem-signals` — `Sort Method: external merge Disk:` → сортировка ушла на диск

Увеличь `work_mem` или добавь индекс с нужным порядком.

### `pg-indexes/parallel-plan-needs-volume` — Параллельный план (`Gather`/`Workers Launched`) оправдан на больших таблицах

На мелких оверхед запуска worker'ов больше выигрыша. Управляется `min_parallel_table_scan_size` (default 8MB).

---

## 8. Ловушка: `count(1)` и Index Only Scan на «неподходящем» индексе

### `pg-indexes/condition-must-be-index-key` — Запрос `SELECT count(1) FROM t WHERE c > X` при индексе `(a, b, c)` — типичный пример «индекс используется, но не как ключ»

Планировщик берёт `Index Only Scan` (полный проход индекса) потому что:

1. `count(1)` не нужно дёргать таблицу — нужен только факт строки.
2. Индекс содержит `c` — может выдать ответ, не читая heap.
3. Полный проход индекса дешевле полного `Seq Scan` по таблице (индекс физически меньше).

Признаки в плане:
- `Filter:` (не `Index Cond:`) по основному фильтрующему полю.
- `Heap Fetches: 0`.
- `Rows Removed by Filter` — большое число (просканирован весь индекс).

### `pg-indexes/condition-must-be-index-key` — Если на этом запросе нужна реальная скорость — нужен индекс по `c` (или `(c, ...)`)

Тогда план превратится в Index Scan с `Index Cond: (c > X)`.

### `pg-indexes/heap-fetches-mean-stale-visibility-map` — Если `Heap Fetches > 0` — `VACUUM`

Иначе Index Only Scan вырождается в обычный Index Scan с дёрганьем таблицы — может оказаться медленнее `Seq Scan`.

---

## 9. EXPLAIN — что НЕ показывает

### `pg-indexes/explain-is-not-monitoring` — EXPLAIN — про план одного запроса в моменте

Не показывает:
- Локскипы и блокировки → `pg_locks` + `pg_stat_activity`.
- `autovacuum` / `wraparound` → `pg_stat_user_tables`.
- Memory pressure → `top`/`pg_stat_database`.
- Replication lag → `pg_stat_replication`.
- Агрегированную статистику по запросам → `pg_stat_statements`.

---

## 10. Чек-лист «индекс не работает»

1. `EXPLAIN ANALYZE` показывает `Seq Scan` вместо `Index Scan`?
2. Сравни `rows=` оценку и `actual rows=`. Расхождение 10x+ → `ANALYZE`.
3. Селективность колонки в `pg_stats`? Низкая (>20% подходят) → индекс не поможет.
4. `random_page_cost` = 1.1 на SSD, не 4.0.
5. Колонка стоит первой в композитном (или в левом префиксе по условию)?
6. `LOWER()`/`COALESCE()` в `WHERE` → нужен functional index.
7. Частичный предикат (`WHERE deleted = false`) → partial index.
8. Корреляция колонок → `CREATE STATISTICS`.

---

## Чек-лист на ревью DDL индексов

- [ ] Composite: range/sort колонка последней, `=`-поле первой
- [ ] Нет дубликатов (`(a)` поверх `(a, b, c)`)
- [ ] Все FK покрыты индексом, если по нему джойнят
- [ ] Регулярные `LOWER()` в `WHERE` — functional index
- [ ] Частые подмножества — partial index
- [ ] В продакшен-миграциях — `CONCURRENTLY`
- [ ] JSONB — GIN с `jsonb_path_ops` (для `@>`) или functional (для конкретного ключа)
- [ ] Полнотекст / триграммы — GIN с `pg_trgm` или `to_tsvector`
- [ ] BRIN — рассмотреть для append-only таблиц >50M строк
