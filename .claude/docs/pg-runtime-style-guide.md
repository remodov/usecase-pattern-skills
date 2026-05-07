# PostgreSQL Runtime Style Guide — WAL, VACUUM, Locks

Правила работы с runtime-аспектами PostgreSQL: Write-Ahead Log, autovacuum/bloat, блокировки. Кодами `PG-W-NNN` (WAL), `PG-V-NNN` (VACUUM), `PG-L-NNN` (Locks) ссылается скилл `ucp-pg-runtime-review`.

Базовый принцип: **скорость и стабильность OLTP-нагрузки определяются не SQL, а тем, как код взаимодействует с MVCC**. Длинная транзакция, кривой `UPDATE`, лишний индекс — всё это перетекает в WAL, в bloat, в локи.

---

## 1. WAL — что разработчик может уменьшить

### Bulk-операции

`PG-W-010` **Для массовой вставки — `COPY`, не цикл `INSERT`.** Разница на 1M строк — 10–100× по времени и 5–10× по WAL. В JDBC используется `org.postgresql.copy.CopyManager`. Если COPY не подходит — `batchUpdate` (батч на 1–10K строк, одна транзакция).

`PG-W-011` **Один большой `COMMIT` с 10K вставок дешевле 10K маленьких `COMMIT`.** Меньше `fsync`-ов. Но: длинная транзакция блокирует autovacuum (см. §3 ниже). Оптимум — батчи 1–10K.

`PG-W-012` **Перед массовой загрузкой в пустую таблицу — дроп индексов, загрузка, восстановление.** Каждая вставка с активным индексом пишет WAL для таблицы И каждого индекса.

### HOT и fillfactor

`PG-W-020` **HOT (Heap-Only Tuple)** — оптимизация PG: `UPDATE` без перемещения и без переписывания индексов, если на странице есть свободное место И не изменены индексируемые колонки.

`PG-W-021` **Для интенсивно обновляемых таблиц — `fillfactor = 80–90`** в DDL. Дефолт 100 → каждая вставка под завязку → `UPDATE` уходит на новую страницу → нет HOT → больше WAL. Цена — 10–20% больше места, выигрыш — кратное уменьшение WAL.

`PG-W-022` **HOT отключается при `UPDATE` индексируемой колонки.** Если поле меняется на каждом `UPDATE` (например, `last_seen_at`) и индекс по нему слабоселективный — индекс может вообще не нужен, удали его.

Проверка HOT-ratio:
```sql
SELECT relname, n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / NULLIF(n_tup_upd, 0), 1) AS hot_pct
FROM pg_stat_user_tables ORDER BY n_tup_upd DESC LIMIT 10;
```

`hot_pct < 50%` на горячей таблице — кандидат на снижение `fillfactor`.

### TOAST и большие значения

`PG-W-030` **Большое значение в TOAST не переписывается при UPDATE, если не изменилось.** Это аргумент против «всё в один большой `data jsonb`»: при изменении одного маленького ключа PG не знает, что внутри JSONB не изменилось, и пишет всё в WAL.

`PG-W-031` **Часто-обновляемые маленькие поля и редко-меняющиеся большие — TOAST разделит автоматически (для значений > ~2KB) либо разделяй на две таблицы.**

### UNLOGGED

`PG-W-040` **Для данных, которые можно потерять при crash, — `UNLOGGED` таблица.** Нет WAL, нет реплики. Подходит: кеши, промежуточные данные ETL, очереди задач с TTL.

`PG-W-041` **`UNLOGGED → LOGGED` через `ALTER TABLE` переписывает всю таблицу с генерацией полного WAL.** Разовая операция, не делай в hot path.

### synchronous_commit

`PG-W-050` **`synchronous_commit = off` отключает ожидание fsync — большой прирост throughput, но при крахе сервера ~200мс закоммиченных транзакций могут потеряться.** Для финансов и заказов — никогда. Для аналитики, метрик, логов — приемлемо.

`PG-W-051` **Регулируй на уровне сессии:** `SET LOCAL synchronous_commit = off` — для batch-импорта, обычные транзакции остаются `on`.

### Длинные транзакции и replication slots

`PG-W-060` **Открытая долгая транзакция блокирует освобождение WAL и autovacuum.** PG не может удалить WAL, нужный любой открытой транзакции (для MVCC). Открытая транзакция на час = часы WAL → диск заполняется → кластер встаёт.

`PG-W-061` **Не делай долгие транзакции в коде:** Spring `@Transactional` на методе, который ходит во внешний HTTP / Kafka / S3 — десятки секунд = открытая транзакция. Транзакция — секунды, не минуты.

`PG-W-062` **Алёрт на `xact_age > 5 минут`** в `pg_stat_activity`.

`PG-W-070` **Висящий replication slot** не даёт PG удалить WAL. Алёрт на `pg_replication_slots.lag_bytes > 10GB` или `active = false` дольше часа. PG13+: `max_slot_wal_keep_size` ограничивает запас WAL для слота.

---

## 2. VACUUM и bloat

### Что и когда

`PG-V-001` **VACUUM освобождает место от dead tuples (но не возвращает ОС), обновляет visibility map, защищает от XID wraparound.** Не блокирует чтение/запись (только DDL).

`PG-V-010` **`VACUUM FULL` — почти никогда в проде.** Берёт ACCESS EXCLUSIVE — блокирует ВСЁ. Альтернатива без блокировки — `pg_repack` / `pg_squeeze`.

`PG-V-011` **`VACUUM ANALYZE` руками после массовой миграции** (`UPDATE`/`DELETE` миллионов строк). Иначе планировщик ещё долго работает с устаревшей статистикой.

### autovacuum — когда тюнить

`PG-V-020` **Дефолты autovacuum хороши для большинства проектов.** Не трогай без причины.

`PG-V-021` **На больших горячих таблицах дефолт мал** (`scale_factor = 0.2` = триггер при 20% dead tuples). Снизь до 0.05 для конкретной таблицы:
```sql
ALTER TABLE order_doc SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.05
);
```

### Мониторинг bloat

`PG-V-030` **Базовый — `pg_stat_user_tables`:** `n_dead_tup`, `last_autovacuum`. `dead_pct > 20%` — кандидат на ручной VACUUM.

`PG-V-031` **Точный — расширение `pgstattuple`:** `dead_tuple_percent > 30%` = bloat. Лечится `VACUUM` (если autovacuum не справляется), `pg_repack` или `VACUUM FULL` в окно.

`PG-V-032` **Bloat индексов** — `REINDEX CONCURRENTLY` (PG12+), не блокирует таблицу.

### Когда autovacuum не справляется

`PG-V-050` **Долгая транзакция блокирует освобождение dead tuples** (см. `PG-W-060`).

`PG-V-051` **Висящий replication slot** (см. `PG-W-070`).

`PG-V-052` **Prepared transactions** в `pg_prepared_xacts` — те же эффекты.

`PG-V-053` **Отключённый `autovacuum`** — глобально или per-table. Проверь:
```sql
SELECT relname, reloptions FROM pg_class
WHERE relkind = 'r' AND reloptions::text LIKE '%autovacuum%';
```

### Миграции и VACUUM

`PG-V-060` **После big `UPDATE`/`DELETE` миграции — `VACUUM ANALYZE` в той же миграции.**

`PG-V-061` **`CREATE INDEX CONCURRENTLY` обновляет visibility map** — после построения для Index Only Scan нужен `VACUUM`, чтобы Heap Fetches упали до нуля.

---

## 3. Блокировки

### Базовая модель

`PG-L-001` **`UPDATE`/`DELETE` уже берут row-level lock.** Параллельный `UPDATE` той же строки ждёт. Параллельный `SELECT` без `FOR UPDATE` НЕ ждёт (читает старую версию через MVCC).

### SELECT FOR UPDATE

`PG-L-010` **`SELECT ... FOR UPDATE` — когда читаешь строку, чтобы потом её изменить, и нужна гарантия, что между чтением и записью никто не вмешается.** Резерв остатков, изменение статуса, любой UPDATE-after-SELECT.

`PG-L-011` **`FOR UPDATE` блокирует только до конца транзакции.** В Spring это значит: `@Transactional` обязателен.

`PG-L-012` **В 95% случаев — `FOR UPDATE`. `FOR NO KEY UPDATE`/`FOR SHARE`/`FOR KEY SHARE` — оптимизации, не дёргай без понимания.**

### SKIP LOCKED — очередь задач

`PG-L-020` **`FOR UPDATE SKIP LOCKED` пропускает залоченные строки.** Идеальный паттерн для очереди задач в БД и для outbox-relay (несколько worker-ов берут разные строки, никто не ждёт).

```sql
SELECT id FROM task_queue
WHERE status = 'PENDING'
ORDER BY created_at LIMIT 1
FOR UPDATE SKIP LOCKED;
```

`PG-L-021` **Outbox-relay должен использовать `SKIP LOCKED`** при многих инстансах сервиса — иначе дублирующая публикация.

### NOWAIT

`PG-L-030` **`FOR UPDATE NOWAIT` — fail-fast вместо ожидания.** Когда лучше отказаться, чем ждать (API-таймаут).

### jOOQ

`PG-L-040` **jOOQ умеет все варианты:**
```java
ctx.selectFrom(PRODUCT).where(PRODUCT.ID.eq(id)).forUpdate().fetchOne();
ctx.selectFrom(TASK_QUEUE).where(...).limit(10).forUpdate().skipLocked().fetch();
ctx.selectFrom(...).forUpdate().noWait().fetchOne();
```

`PG-L-041` **Lock-запрос обязан быть внутри `@Transactional`-метода Spring.** Иначе jOOQ откроет/закроет соединение, лок отпустится мгновенно.

### Pessimistic vs Optimistic

`PG-L-050` **Pessimistic — `FOR UPDATE`.** Простой код, при высокой конкуренции — очередь TX.

`PG-L-051` **Optimistic — через `version`-колонку.** Не блокируешь заранее, на UPDATE проверяешь, что версия не изменилась. Лучше масштабируется при низкой реальной конкуренции. Для финансов и write-heavy — обычно pessimistic.

```sql
UPDATE order_doc SET status='PAID', version=version+1
WHERE id=? AND version=?;   -- 0 rows = конфликт
```

### Advisory locks

`PG-L-060` **`pg_advisory_xact_lock(key)` / `pg_try_advisory_xact_lock(key)` — блокировка на произвольный bigint-ключ, не привязана к таблице.** Полезно для:
- Запуск scheduled-job только одним инстансом из кластера.
- Предотвращение двух одновременных миграций.
- Глобальные семафоры.

`PG-L-061` **Два bigint-аргумента**, если лок логически разделяется: `pg_advisory_lock(class_id, object_id)`, например `(1001, tenant_id)`.

### Deadlock

`PG-L-070` **Deadlock — две TX берут локи в РАЗНОМ порядке.** PG детектит через `deadlock_timeout` (default 1s), убивает одну TX с ошибкой `40P01`.

`PG-L-071` **Лечится упорядочением блокировок.** Перевод денег: всегда блокировать счета в порядке возрастания `id`.

`PG-L-072` **На Java стороне — retry на `CannotAcquireLockException`** (1–3 попытки с backoff). Это нормальный исход в high-concurrency OLTP.

### lock_timeout

`PG-L-080` **`SET LOCAL lock_timeout = '5s'` для критичных операций** — не жди вечно. Особенно важно для миграций (`ALTER TABLE` берёт ACCESS EXCLUSIVE → блокирует всех ждущих).

### Антипаттерны

`PG-L-090` `SELECT FOR UPDATE` без транзакции — лок мгновенно отпускается.

`PG-L-091` `SELECT FOR UPDATE` со сложным `WHERE`, не покрытым индексом — может залочить кучу строк через seq scan.

`PG-L-092` Длинная транзакция с локом → блокирует всех ждущих и копит WAL.

`PG-L-093` Pessimistic lock на каждое чтение — превращает БД в очередь.

`PG-L-094` Брать локи в разном порядке в разных методах → deadlock.

`PG-L-095` `SELECT FOR UPDATE` без `LIMIT` на большой таблице — внезапно блокирует всё.

---

## Чек-лист на ревью кода и схемы

- [ ] Spring `@Transactional` — только вокруг короткой DB-логики, не вокруг HTTP/Kafka/S3.
- [ ] Bulk-импорты — через `COPY` или `batchUpdate`.
- [ ] Длинные транзакции (> 5 сек) — режутся на куски с промежуточными `COMMIT`.
- [ ] Кеши и временные данные — `UNLOGGED`.
- [ ] Часто-обновляемые таблицы — `fillfactor = 80–90` в DDL.
- [ ] Не вешать индексы на колонки, которые обновляются почти на каждом UPDATE.
- [ ] После big-миграции — `VACUUM ANALYZE` в той же миграции.
- [ ] `SELECT FOR UPDATE` — внутри `@Transactional`.
- [ ] Очереди задач / outbox-relay — `FOR UPDATE SKIP LOCKED LIMIT N`.
- [ ] Финансовые операции — pessimistic locking + retry на deadlock.
- [ ] Block в порядке возрастания PK для multi-row операций (предотвращает deadlock).
- [ ] `lock_timeout` в начале миграции.
- [ ] `pg_replication_slots.lag_bytes` мониторится — алёрт на > 10GB или `active=false`.
- [ ] `pg_stat_user_tables.last_autovacuum` мониторится для горячих таблиц.
