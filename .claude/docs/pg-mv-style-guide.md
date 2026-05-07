# PostgreSQL Materialized Views Style Guide

Правила для materialized views: refresh-стратегии, индексы, альтернативы. Кодами `PG-MV-NNN` ссылается скилл `ucp-pg-schema-review` (DDL) и `ucp-pg-runtime-review` (refresh-стратегии в коде).

Базовый принцип: **MV — закэшированный snapshot тяжёлого запроса с латентностью обновления.** Для real-time данных — Read Model в коде, не MV.

---

## 1. Когда оправдан

### `PG-MV-001` — MV подходит для:
- Тяжёлые агрегации, читают часто, обновлять можно с задержкой ОК.
- Сложные join'ы по нескольким таблицам.
- Pre-computed search-индексы (FTS).
- Денормализация для read-heavy.

### `PG-MV-002` — MV не подходит:
- Real-time данные (refresh имеет латентность).
- Часто меняющиеся данные (cost refresh > выигрыш).
- Простые запросы — обычный VIEW или индекс.

## 2. DDL

### `PG-MV-010` — MV всегда с UNIQUE-индексом

Без UNIQUE нельзя `REFRESH CONCURRENTLY`, остаётся только blocking refresh.

```sql
CREATE MATERIALIZED VIEW order_stats_mv AS
SELECT customer_id, count(*) AS orders_count, sum(total_amount) AS total_spent
FROM order_doc
WHERE status != 'CANCELLED'
GROUP BY customer_id
WITH DATA;

CREATE UNIQUE INDEX uk_order_stats_customer ON order_stats_mv (customer_id);
CREATE INDEX ix_order_stats_total ON order_stats_mv (total_spent DESC);
```

### `PG-MV-011` — Naming — суффикс `_mv`

(`PG-N-080` из naming-style-guide).

### `PG-MV-012` — `WITH NO DATA` для пустого старта в миграции

+ последующий refresh-job. Для маленьких — сразу `WITH DATA`.

## 3. Refresh-стратегии

### `PG-MV-020` — `REFRESH MATERIALIZED VIEW CONCURRENTLY` — стандартный выбор для прод

Без CONCURRENTLY = `ACCESS EXCLUSIVE` lock = блокировка всех читателей.

### `PG-MV-021` — `REFRESH` (без CONCURRENTLY) — только в окно обслуживания

### `PG-MV-022` — Cron / `@Scheduled` — для аналитики/отчётов:
```java
@Scheduled(fixedDelay = 300_000)  // 5 минут
public void refreshOrderStats() {
    jdbc.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY order_stats_mv");
}
```

### `PG-MV-023` — Триггер на каждое изменение исходной таблицы — антипаттерн

Refresh всей MV на каждый INSERT уничтожает throughput. Используй ТОЛЬКО когда:
- Изменения редкие.
- MV маленькая.
- Альтернативы нет.

### `PG-MV-024` — Debounced refresh через Redis/cron — компромисс между свежестью и нагрузкой:
```java
// при изменении исходных данных:
redis.set("mv:order_stats:dirty", "1");

@Scheduled(fixedDelay = 60_000)
public void refreshIfDirty() {
    if (redis.delete("mv:order_stats:dirty")) {
        jdbc.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY order_stats_mv");
    }
}
```

## 4. MV vs Read Model в коде

### `PG-MV-030` — MV — это read model в БД. Read Model в коде — отдельная таблица + код, обновляющий её на event'ах

| | MV | Read Model в коде |
|---|---|---|
| Логика обновления | SQL | Java code |
| Гранулярность | вся MV | по строкам |
| Латентность | секунды-минуты | микросекунды |
| Сложность | низкая | высокая |

### `PG-MV-031` — Простое правило выбора:
- Запрос — сложный `SELECT ... GROUP BY` с JOIN, читается часто, задержка приемлема → MV.
- Read model нужна с минимальной задержкой, обновляется поэлементно → отдельная таблица + event handler (Read Model паттерн UCP Level 2).

## 5. Антипаттерны

### `PG-MV-080` — `REFRESH MATERIALIZED VIEW` (без CONCURRENTLY) на проде

— блокирует всех читателей.

### `PG-MV-081` — Триггер `AFTER INSERT/UPDATE/DELETE` с REFRESH

на горячей таблице — каждое изменение триггерит full refresh.

### `PG-MV-082` — MV без UNIQUE-индекса

— нельзя CONCURRENTLY refresh.

### `PG-MV-083` — MV для real-time данных

— латентность refresh не покрывает требования.

### `PG-MV-084` — MV вместо нормального индекса

— иногда «закэшируем `SELECT WHERE foo = ?`» решается обычным индексом.

### `PG-MV-085` — MV без явной refresh-стратегии в коде

— кто-то когда-то её должен обновить.

---

## Чек-лист на ревью

- [ ] MV оправдана: тяжёлая агрегация, латентность приемлема.
- [ ] Есть UNIQUE-индекс на MV.
- [ ] `REFRESH MATERIALIZED VIEW CONCURRENTLY`, не блокирующий вариант.
- [ ] Refresh вынесен в `@Scheduled` или debounced trigger, не на каждый INSERT.
- [ ] Стратегия refresh: cron для аналитики, debounced для near-real-time.
- [ ] Альтернатива (Read Model в коде) рассмотрена и отвергнута по конкретной причине.
- [ ] Naming с суффиксом `_mv`.
