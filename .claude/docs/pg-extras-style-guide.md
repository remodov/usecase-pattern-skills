# PostgreSQL Extras Style Guide — FTS, PostGIS

Узкие, но полезные правила для проектов с full-text search и геоданными. Кодами `PG-FTS-NNN` (FTS) и `PG-GIS-NNN` (PostGIS) ссылается скилл `ucp-pg-schema-review`.

Применяй ТОЛЬКО на проектах, где эти технологии реально используются. На остальных — игнорируй.

---

## 1. Полнотекстовый поиск (FTS)

### Когда хватает PG FTS

### `PG-FTS-001` — PG FTS подходит для:
- Корпоративный/админский поиск (≤ 10M документов).
- E-commerce среднего масштаба.
- Поиск по комментариям, тикетам.

### `PG-FTS-002` — Не подходит:
- ≫ 10M документов с ranking-нагрузкой → Elasticsearch.
- Сложный fuzzy с typo tolerance → Elasticsearch + edge-ngram.

### Хранение tsvector

### `PG-FTS-020` — Generated column (PG12+) обязательна — не вычисляй `to_tsvector(...)` на лету

```sql
CREATE TABLE article (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title       text NOT NULL,
    body        text NOT NULL,
    search_doc  tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('russian', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('russian', coalesce(body, '')), 'B')
    ) STORED
);

CREATE INDEX ix_article_search_doc ON article USING gin (search_doc);
```

### `PG-FTS-021` — GIN-индекс на tsvector обязателен

Без него — seq-scan, медленно.

### `PG-FTS-022` — Используй русскую конфигурацию `to_tsvector('russian', ...)`

(или соответствующий язык). `simple` без стемминга — «покупатель» и «покупателя» будут разные токены.

### `PG-FTS-023` — Веса `setweight` для разных полей:

A=title, B=body/desc, C=tags, D=другое. Без весов ranking бесполезен.

### Запросы

### `PG-FTS-030` — Пользовательский ввод — `plainto_tsquery` или `websearch_to_tsquery` (PG11+), не сырой `to_tsquery`

(легко получить syntax error).

```sql
SELECT * FROM article WHERE search_doc @@ websearch_to_tsquery('russian', $1);
-- 'покупатель -ребёнок "новый каталог"'
```

### `PG-FTS-031` — Подсветка совпадений — `ts_headline`

### Глубокая пагинация

### `PG-FTS-040` — OFFSET + LIMIT для глубокой пагинации страдает

Используй keyset pagination по `(rank, id)`:
```sql
WHERE search_doc @@ q AND (ts_rank(search_doc, q), id) < ($prev_rank, $prev_id)
ORDER BY rank DESC, id DESC LIMIT 20;
```

### Триграммы (pg_trgm)

### `PG-FTS-050` — `pg_trgm` дополняет FTS

для:
- `LIKE '%substring%'` с индексом.
- Поиск с опечатками через `similarity()`.
- Короткие поля (имя, бренд).

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX ix_customer_name_trgm ON customer USING gin (full_name gin_trgm_ops);

SELECT * FROM customer WHERE full_name ILIKE '%иван%';
SELECT * FROM customer WHERE similarity(full_name, 'иванв') > 0.4;
```

### Антипаттерны FTS

`PG-FTS-090` Хранить `to_tsvector(...)` как stored function в `WHERE` — без индекса.

`PG-FTS-091` `simple` конфигурация для русского — без стемминга.

`PG-FTS-092` Игнорировать веса `setweight` — все совпадения равны.

`PG-FTS-093` `ts_rank` в `WHERE` — считается на каждом совпадении, медленно.

---

## 2. PostGIS — геоданные

### Когда нужен

### `PG-GIS-001` — PostGIS оправдан для:
- Поиск в радиусе, kNN ближайших.
- Расстояние между точками.
- Полигон-poly операции (в каком районе адрес).
- Маршруты.

### `PG-GIS-002` — Для двух колонок `lat`/`lon` без операций — избыточен

Достаточно `numeric(9,6)`/`numeric(10,6)`.

### Типы

### `PG-GIS-010` — Default: `geography(Point, 4326)`

Сферическая, точно для глобальных приложений, проще (один SRID — 4326 для WGS84).

### `PG-GIS-011` — `geometry` — для локальных систем

(один город, регион — UTM-проекция). Быстрее, но требует осмысленного SRID.

### `PG-GIS-012` — Порядок координат: `POINT(lon lat)` — долгота сначала, широта потом

Самая частая ошибка.

### Индексы

### `PG-GIS-020` — GiST-индекс на geo-колонке обязателен

Без него любой `ST_DWithin`/`ST_Contains` — seq-scan.

```sql
CREATE INDEX ix_shop_location_gist ON shop USING gist (location);
```

### Операции

### `PG-GIS-030` — Поиск в радиусе — `ST_DWithin` в `WHERE` (использует индекс), не `ST_Distance`

(без индекса):

```sql
SELECT id, name FROM shop
WHERE ST_DWithin(location, ST_GeogFromText('SRID=4326;POINT(30.31 59.93)'), 5000)
ORDER BY ST_Distance(location, ST_GeogFromText('SRID=4326;POINT(30.31 59.93)'))
LIMIT 50;
```

### `PG-GIS-031` — kNN — оператор `<->` (использует GiST):
```sql
SELECT id FROM shop
ORDER BY location <-> ST_GeogFromText('SRID=4326;POINT(30.31 59.93)')
LIMIT 10;
```

### `PG-GIS-032` — Composite GiST с `btree_gist`

для multi-фильтра:
```sql
CREATE EXTENSION btree_gist;
CREATE INDEX ix_shop_active_loc ON shop USING gist (is_active, location);
```

### Антипаттерны PostGIS

`PG-GIS-090` `ST_Distance` без `ST_DWithin` в `WHERE` — seq-scan.

`PG-GIS-091` `POINT(lat lon)` — distance врёт. Помни: `(lon lat)`.

`PG-GIS-092` `lat/lon` как `varchar` — не сравнить, не индексировать.

`PG-GIS-093` Расчёт расстояния через haversine в коде Java — медленно, неиндексируемо.

`PG-GIS-094` `geometry` для глобальных координат без проекции — ошибка на больших расстояниях.

`PG-GIS-095` Spatial-индекс отсутствует — все запросы seq-scan.

---

## Чек-лист на ревью (FTS)

- [ ] `tsvector` хранится как `GENERATED ... STORED` или через триггер.
- [ ] GIN-индекс на tsvector колонке.
- [ ] Русская (или языковая) конфигурация `to_tsvector('russian', ...)`.
- [ ] Веса `setweight` для разных полей.
- [ ] Пользовательский ввод через `plainto_tsquery`/`websearch_to_tsquery`.
- [ ] Подсветка через `ts_headline`.
- [ ] `pg_trgm` для коротких полей с опечатками.

## Чек-лист на ревью (PostGIS)

- [ ] Тип колонки `geography(Point, 4326)`, не `lat/lon` отдельно.
- [ ] GiST-индекс на geo-колонке.
- [ ] `ST_DWithin` в WHERE, не `ST_Distance`.
- [ ] kNN через `ORDER BY <->`, не вычисление в коде.
- [ ] Координаты `POINT(lon lat)`.
- [ ] Multi-фильтр — composite GiST с `btree_gist`.
