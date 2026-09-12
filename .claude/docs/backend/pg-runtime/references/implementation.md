# требования `pg-runtime/*` — WAL, VACUUM, Locks, Pool, Isolation

Правила работы с runtime-аспектами PostgreSQL: Write-Ahead Log, autovacuum/bloat, блокировки, connection pool, уровни изоляции. Кодами `PG-W-NNN` (WAL), `PG-V-NNN` (VACUUM), `PG-L-NNN` (Locks), `PG-CP-NNN` (Connection Pool), `PG-IS-NNN` (Isolation) ссылается скилл `ucp-pg-runtime-review`.

Базовый принцип: **скорость и стабильность OLTP-нагрузки определяются не SQL, а тем, как код взаимодействует с MVCC**. Длинная транзакция, кривой `UPDATE`, лишний индекс — всё это перетекает в WAL, в bloat, в локи.

---

## 1. WAL — что разработчик может уменьшить

### Bulk-операции

### `pg-runtime/bulk-load-via-copy` — Для массовой вставки — `COPY`, не цикл `INSERT`

Разница на 1M строк — 10–100× по времени и 5–10× по WAL. В JDBC используется `org.postgresql.copy.CopyManager`. Если COPY не подходит — `batchUpdate` (батч на 1–10K строк, одна транзакция).

### `pg-runtime/bulk-load-via-copy` — Один большой `COMMIT` с 10K вставок дешевле 10K маленьких `COMMIT`

Меньше `fsync`-ов. Но: длинная транзакция блокирует autovacuum (см. §3 ниже). Оптимум — батчи 1–10K.

### `pg-runtime/bulk-load-via-copy` — Перед массовой загрузкой в пустую таблицу — дроп индексов, загрузка, восстановление

Каждая вставка с активным индексом пишет WAL для таблицы И каждого индекса.

### HOT и fillfactor

### `pg-runtime/fillfactor-for-hot-updates` — HOT (Heap-Only Tuple)

— оптимизация PG: `UPDATE` без перемещения и без переписывания индексов, если на странице есть свободное место И не изменены индексируемые колонки.

### `pg-runtime/fillfactor-for-hot-updates` — Для интенсивно обновляемых таблиц — `fillfactor = 80–90`

в DDL. Дефолт 100 → каждая вставка под завязку → `UPDATE` уходит на новую страницу → нет HOT → больше WAL. Цена — 10–20% больше места, выигрыш — кратное уменьшение WAL.

### `pg-runtime/fillfactor-for-hot-updates` — HOT отключается при `UPDATE` индексируемой колонки

Если поле меняется на каждом `UPDATE` (например, `last_seen_at`) и индекс по нему слабоселективный — индекс может вообще не нужен, удали его.

Проверка HOT-ratio:
```sql
SELECT relname, n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / NULLIF(n_tup_upd, 0), 1) AS hot_pct
FROM pg_stat_user_tables ORDER BY n_tup_upd DESC LIMIT 10;
```

`hot_pct < 50%` на горячей таблице — кандидат на снижение `fillfactor`.

### TOAST и большие значения

### `pg-runtime/toast-large-values-separately` — Большое значение в TOAST не переписывается при UPDATE, если не изменилось

Это аргумент против «всё в один большой `data jsonb`»: при изменении одного маленького ключа PG не знает, что внутри JSONB не изменилось, и пишет всё в WAL.

### `pg-runtime/toast-large-values-separately` — Часто-обновляемые маленькие поля и редко-меняющиеся большие — TOAST разделит автоматически (для значений > ~2KB) либо разделяй на две таблицы

### UNLOGGED

### `pg-runtime/unlogged-for-disposable-data` — Для данных, которые можно потерять при crash, — `UNLOGGED` таблица

Нет WAL, нет реплики. Подходит: кеши, промежуточные данные ETL, очереди задач с TTL.

### `pg-runtime/unlogged-for-disposable-data` — `UNLOGGED → LOGGED` через `ALTER TABLE` переписывает всю таблицу с генерацией полного WAL

Разовая операция, не делай в hot path.

### synchronous_commit

### `pg-runtime/synchronous-commit-scope` — `synchronous_commit = off` отключает ожидание fsync — большой прирост throughput, но при крахе сервера ~200мс закоммиченных транзакций могут потеряться

Для финансов и заказов — никогда. Для аналитики, метрик, логов — приемлемо.

### `pg-runtime/synchronous-commit-scope` — Регулируй на уровне сессии:

`SET LOCAL synchronous_commit = off` — для batch-импорта, обычные транзакции остаются `on`.

### Длинные транзакции и replication slots

### `pg-runtime/short-transactions` — Открытая долгая транзакция блокирует освобождение WAL и autovacuum

PG не может удалить WAL, нужный любой открытой транзакции (для MVCC). Открытая транзакция на час = часы WAL → диск заполняется → кластер встаёт.

### `pg-runtime/short-transactions` — Не делай долгие транзакции в коде:

Spring `@Transactional` на методе, который ходит во внешний HTTP / Kafka / S3 — десятки секунд = открытая транзакция. Транзакция — секунды, не минуты.

### `pg-runtime/short-transactions` — Алёрт на `xact_age > 5 минут`

в `pg_stat_activity`.

### `pg-runtime/replication-slots-watched` — Висящий replication slot

не даёт PG удалить WAL. Алёрт на `pg_replication_slots.lag_bytes > 10GB` или `active = false` дольше часа. PG13+: `max_slot_wal_keep_size` ограничивает запас WAL для слота.

---

## 2. VACUUM и bloat

### Что и когда

### `pg-runtime/no-vacuum-full-in-production` — VACUUM освобождает место от dead tuples (но не возвращает ОС), обновляет visibility map, защищает от XID wraparound

Не блокирует чтение/запись (только DDL).

### `pg-runtime/no-vacuum-full-in-production` — `VACUUM FULL` — почти никогда в проде

Берёт ACCESS EXCLUSIVE — блокирует ВСЁ. Альтернатива без блокировки — `pg_repack` / `pg_squeeze`.

### `pg-runtime/vacuum-analyze-after-bulk-change` — `VACUUM ANALYZE` руками после массовой миграции

(`UPDATE`/`DELETE` миллионов строк). Иначе планировщик ещё долго работает с устаревшей статистикой.

### autovacuum — когда тюнить

### `pg-runtime/autovacuum-tuning-per-table` — Дефолты autovacuum хороши для большинства проектов

Не трогай без причины.

### `pg-runtime/autovacuum-tuning-per-table` — На больших горячих таблицах дефолт мал

(`scale_factor = 0.2` = триггер при 20% dead tuples). Снизь до 0.05 для конкретной таблицы:
```sql
ALTER TABLE order_doc SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.05
);
```

### Мониторинг bloat

### `pg-runtime/bloat-monitoring` — Базовый — `pg_stat_user_tables`:

`n_dead_tup`, `last_autovacuum`. `dead_pct > 20%` — кандидат на ручной VACUUM.

### `pg-runtime/bloat-monitoring` — Точный — расширение `pgstattuple`:

`dead_tuple_percent > 30%` = bloat. Лечится `VACUUM` (если autovacuum не справляется), `pg_repack` или `VACUUM FULL` в окно.

### `pg-runtime/no-vacuum-full-in-production` — Bloat индексов

— `REINDEX CONCURRENTLY` (PG12+), не блокирует таблицу.

### Когда autovacuum не справляется

### `pg-runtime/short-transactions` — Долгая транзакция блокирует освобождение dead tuples

(см. `pg-runtime/short-transactions`).

### `pg-runtime/replication-slots-watched` — Висящий replication slot

(см. `pg-runtime/replication-slots-watched`).

### `pg-runtime/no-dangling-prepared-transactions` — Prepared transactions

в `pg_prepared_xacts` — те же эффекты.

### `pg-runtime/autovacuum-tuning-per-table` — Отключённый `autovacuum`

— глобально или per-table. Проверь:
```sql
SELECT relname, reloptions FROM pg_class
WHERE relkind = 'r' AND reloptions::text LIKE '%autovacuum%';
```

### Миграции и VACUUM

### `pg-runtime/vacuum-analyze-after-bulk-change` — После big `UPDATE`/`DELETE` миграции — `VACUUM ANALYZE` в той же миграции

### `pg-runtime/vacuum-analyze-after-bulk-change` — `CREATE INDEX CONCURRENTLY` обновляет visibility map

— после построения для Index Only Scan нужен `VACUUM`, чтобы Heap Fetches упали до нуля.

---

## 3. Блокировки

### Базовая модель

### `pg-runtime/row-lock-inside-transaction` — `UPDATE`/`DELETE` уже берут row-level lock

Параллельный `UPDATE` той же строки ждёт. Параллельный `SELECT` без `FOR UPDATE` НЕ ждёт (читает старую версию через MVCC).

### SELECT FOR UPDATE

### `pg-runtime/row-lock-inside-transaction` — `SELECT ... FOR UPDATE` — когда читаешь строку, чтобы потом её изменить, и нужна гарантия, что между чтением и записью никто не вмешается

Резерв остатков, изменение статуса, любой UPDATE-after-SELECT.

### `pg-runtime/row-lock-inside-transaction` — `FOR UPDATE` блокирует только до конца транзакции

В Spring это значит: `@Transactional` обязателен.

### `pg-runtime/row-lock-inside-transaction` — В 95% случаев — `FOR UPDATE`. `FOR NO KEY UPDATE`/`FOR SHARE`/`FOR KEY SHARE` — оптимизации, не дёргай без понимания

### SKIP LOCKED — очередь задач

### `pg-runtime/skip-locked-for-queues` — `FOR UPDATE SKIP LOCKED` пропускает залоченные строки

Идеальный паттерн для очереди задач в БД и для outbox-relay (несколько worker-ов берут разные строки, никто не ждёт).

```sql
SELECT id FROM task_queue
WHERE status = 'PENDING'
ORDER BY created_at LIMIT 1
FOR UPDATE SKIP LOCKED;
```

### `pg-runtime/skip-locked-for-queues` — Outbox-relay должен использовать `SKIP LOCKED`

при многих инстансах сервиса — иначе дублирующая публикация.

### NOWAIT

### `pg-runtime/nowait-for-bounded-latency` — `FOR UPDATE NOWAIT` — fail-fast вместо ожидания

Когда лучше отказаться, чем ждать (API-таймаут).

### jOOQ

### `pg-runtime/row-lock-inside-transaction` — jOOQ умеет все варианты:
```java
ctx.selectFrom(PRODUCT).where(PRODUCT.ID.eq(id)).forUpdate().fetchOne();
ctx.selectFrom(TASK_QUEUE).where(...).limit(10).forUpdate().skipLocked().fetch();
ctx.selectFrom(...).forUpdate().noWait().fetchOne();
```

### `pg-runtime/row-lock-inside-transaction` — Lock-запрос обязан быть внутри `@Transactional`-метода Spring

Иначе jOOQ откроет/закроет соединение, лок отпустится мгновенно.

### Pessimistic vs Optimistic

### `pg-runtime/pessimistic-versus-optimistic` — Pessimistic — `FOR UPDATE`

Простой код, при высокой конкуренции — очередь TX.

### `pg-runtime/pessimistic-versus-optimistic` — Optimistic — через `version`-колонку

Не блокируешь заранее, на UPDATE проверяешь, что версия не изменилась. Лучше масштабируется при низкой реальной конкуренции. Для финансов и write-heavy — обычно pessimistic.

```sql
UPDATE order_doc SET status='PAID', version=version+1
WHERE id=? AND version=?;   -- 0 rows = конфликт
```

### Advisory locks

### `pg-runtime/advisory-lock-for-singleton` — `pg_advisory_xact_lock(key)` / `pg_try_advisory_xact_lock(key)` — блокировка на произвольный bigint-ключ, не привязана к таблице

Полезно для:
- Запуск scheduled-job только одним инстансом из кластера.
- Предотвращение двух одновременных миграций.
- Глобальные семафоры.

### `pg-runtime/advisory-lock-for-singleton` — Два bigint-аргумента

, если лок логически разделяется: `pg_advisory_lock(class_id, object_id)`, например `(1001, tenant_id)`.

### Deadlock

### `pg-runtime/deadlock-prevention-by-order` — Deadlock — две TX берут локи в РАЗНОМ порядке

PG детектит через `deadlock_timeout` (default 1s), убивает одну TX с ошибкой `40P01`.

### `pg-runtime/deadlock-prevention-by-order` — Лечится упорядочением блокировок

Перевод денег: всегда блокировать счета в порядке возрастания `id`.

### `pg-runtime/deadlock-prevention-by-order` — На Java стороне — retry на `CannotAcquireLockException`

(1–3 попытки с backoff). Это нормальный исход в high-concurrency OLTP.

### lock_timeout

### `pg-runtime/lock-timeout-for-critical-operations` — `SET LOCAL lock_timeout = '5s'` для критичных операций

— не жди вечно. Особенно важно для миграций (`ALTER TABLE` берёт ACCESS EXCLUSIVE → блокирует всех ждущих).

### Антипаттерны

`pg-runtime/row-lock-inside-transaction` `SELECT FOR UPDATE` без транзакции — лок мгновенно отпускается.

`pg-runtime/locking-select-needs-index-and-limit` `SELECT FOR UPDATE` со сложным `WHERE`, не покрытым индексом — может залочить кучу строк через seq scan.

`pg-runtime/short-transactions` Длинная транзакция с локом → блокирует всех ждущих и копит WAL.

`pg-runtime/pessimistic-versus-optimistic` Pessimistic lock на каждое чтение — превращает БД в очередь.

`pg-runtime/deadlock-prevention-by-order` Брать локи в разном порядке в разных методах → deadlock.

`pg-runtime/locking-select-needs-index-and-limit` `SELECT FOR UPDATE` без `LIMIT` на большой таблице — внезапно блокирует всё.

---

## 4. Connection pool

### HikariCP

### `pg-runtime/pool-size-is-calculated` — Размер пула — формула Wooldridge: `connections = (core_count × 2) + effective_spindle_count`

Для современных SSD-серверов с N CPU-ядрами оптимум 2N+1 = ~10–20 соединений на инстанс. «Больше = лучше» — миф.

### `pg-runtime/pool-size-is-calculated` — Целевой размер пула на инстанс: 10–20

Если кажется, что нужно больше — сначала измерь, узкое место чаще в долгих запросах/транзакциях.

### `pg-runtime/connection-budget-shared` — Бюджет соединений PG = `max_connections` (default 100)

Раздели между всеми инстансами всех сервисов. На 10 инстансов по 20 — уже 200. Решение — увеличить max_connections (300–500 разумно) или PgBouncer.

### `pg-runtime/pool-settings-complete` — Минимальная конфигурация Spring Boot:
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20
      minimum-idle: 20             # = max, иначе ramp-up на холодную
      connection-timeout: 3000
      max-lifetime: 1800000        # 30 мин (меньше LB-таймаута)
      leak-detection-threshold: 60000
```

### `pg-runtime/pool-settings-complete` — `maximum-pool-size = minimum-idle`

— пул всегда полный, нет latency-всплесков.

### `pg-runtime/pool-settings-complete` — `connection-timeout: 3 сек`

— лучше упасть, чем ждать.

### `pg-runtime/pool-settings-complete` — `max-lifetime: 30 мин`

— защита от утечек памяти PG и от поломки соединений за LB. Должен быть меньше серверного `idle_in_transaction_session_timeout` и таймаутов балансировщиков.

### `pg-runtime/leak-detection-enabled` — `leak-detection-threshold: 60 сек`

— алёрт на забытый close или `@Transactional` вокруг долгого HTTP. Не отключай.

### `pg-runtime/pool-metrics-observed` — Метрики HikariCP в Micrometer:

`connections.active/idle/pending/usage/timeout`. Алёрт на `pending > 0` стабильно или `timeout` > 0.

### PgBouncer

### `pg-runtime/pooler-when-justified` — PgBouncer оправдан

: десятки инстансов одного сервиса, общий PG для нескольких сервисов, serverless workers, ограничение connections к PG ниже суммы пулов.

### `pg-runtime/pooler-transaction-mode-constraints` — Уровень `transaction` (default для нашего стека)

— соединение возвращается в пул после COMMIT/ROLLBACK. Не работают: server-side prepared statements (без 1.21+), session-level vars (`SET` без `LOCAL`), `LISTEN`/`NOTIFY`, advisory locks (sessionном scope).

### `pg-runtime/pooler-transaction-mode-constraints` — `session` mode

— когда нужны prepared/listen/notify. Эффективность ниже.

### `pg-runtime/pooler-transaction-mode-constraints` — На transaction mode + JDBC: `prepareThreshold = 0`

в HikariCP — отключить server-side prepared. Иначе теряются между транзакциями.

### `pg-runtime/pool-sizing-with-pooler` — С PgBouncer пул HikariCP может быть БОЛЬШЕ

Соотношение app_pool : pgbouncer_to_pg = 5:1 или больше.

### Read-replica routing

### `pg-runtime/read-replica-separate-datasource` — Отдельный DataSource + отдельный HikariCP пул для реплики

Через `AbstractRoutingDataSource` Spring выбирает на основе `@Transactional(readOnly = true)`.

### `pg-runtime/read-replica-separate-datasource` — Реплика — eventual consistency

Replication lag — миллисекунды, под нагрузкой может расти. Не используй реплику для read-after-write.

### Антипаттерны Pool

`pg-runtime/pool-size-is-calculated` Огромный пул (`maximum-pool-size = 200`) — почти всегда пессимизация.

`pg-runtime/single-pool-per-database` Разные пулы на одну БД для одного приложения — каждый думает, что владеет всеми соединениями.

`pg-runtime/short-transactions` `@Transactional` вокруг внешнего HTTP-вызова — соединение удерживается всё время вызова (см. `pg-runtime/short-transactions`).

`pg-runtime/leak-detection-enabled` Отключение `leak-detection-threshold` — сокрытие проблемы.

`pg-runtime/pooler-when-justified` PgBouncer на `session` mode без явной причины — теряется главный выигрыш.

`pg-runtime/pooler-transaction-mode-constraints` PgBouncer transaction + server-side prepared без отключения `prepareThreshold` — JDBC дёргает PG на каждом запросе.

---

## 5. Уровни изоляции

### `pg-runtime/default-isolation-is-right` — Дефолт PG `READ COMMITTED` правильный в 95% случаев

Поднимать уровень — только когда понимаешь, какую конкретно аномалию предотвращаешь.

### Три уровня PostgreSQL

| Уровень | Dirty | Non-repeatable | Phantom | Serialization |
|---|---|---|---|---|
| `READ COMMITTED` (default) | предотвр. | разрешает | разрешает | разрешает |
| `REPEATABLE READ` (snapshot) | предотвр. | предотвр. | предотвр. | разрешает |
| `SERIALIZABLE` (SSI) | предотвр. | предотвр. | предотвр. | предотвр. |

### `pg-runtime/default-isolation-is-right` — PG `READ COMMITTED` строже стандарта

— dirty read невозможен через MVCC.

### `pg-runtime/repeatable-read-for-consistent-snapshot` — PG `REPEATABLE READ` = snapshot isolation

— phantom тоже предотвращён.

### `pg-runtime/default-isolation-is-right` — `READ COMMITTED` минимизирует блокировки

В большинстве OLTP — правильный выбор.

### REPEATABLE READ

### `pg-runtime/repeatable-read-for-consistent-snapshot` — RR фиксирует snapshot на момент первого запроса в транзакции

Все последующие SELECT видят то же состояние.

### `pg-runtime/repeatable-read-for-consistent-snapshot` — Когда RR оправдан:

длинный отчёт по нескольким таблицам с консистентным срезом, `pg_dump`, перенос данных по сложной логике.

### `pg-runtime/repeatable-read-for-consistent-snapshot` — На RR `UPDATE` той же строки, что изменилась после snapshot, упадёт с `40001 serialization_failure`

Java должен делать retry.

### `pg-runtime/repeatable-read-for-consistent-snapshot` — Не используй RR в hot path просто «на всякий случай»

— будет всплеск 40001-ошибок.

### SERIALIZABLE

### `pg-runtime/serializable-for-cross-row-invariants` — `SERIALIZABLE` через SSI гарантирует: результат параллельных TX = результат последовательных

Сильнее, чем RR.

### `pg-runtime/serializable-for-cross-row-invariants` — Классический пример write skew, который RR пропускает, а SERIALIZABLE ловит:

инвариант «всегда хотя бы один врач на смене», две параллельные TX освобождают разных врачей.

### `pg-runtime/serializable-for-cross-row-invariants` — Когда SERIALIZABLE:

сложные инварианты, которые невозможно выразить через `CHECK` или `FOR UPDATE`. Финансовые расчёты с множественными правилами.

### `pg-runtime/serializable-for-cross-row-invariants` — SERIALIZABLE дороже:

PG отслеживает зависимости, race-condition → откат с 40001 → retry.

### `pg-runtime/serializable-for-cross-row-invariants` — На большинстве OLTP НЕ оправдан

Дешевле выразить инвариант через `SELECT FOR UPDATE` + ручной CHECK.

### Spring

### `pg-runtime/isolation-declared-per-operation` — `@Transactional(isolation = Isolation.SERIALIZABLE)` или `Isolation.REPEATABLE_READ`

на конкретном методе.

### `pg-runtime/default-isolation-is-right` — `READ_COMMITTED` — дефолт, не указывай явно

Пусть в коде явно стоит только то, что отличается от стандарта.

### `pg-runtime/retry-on-serialization-failure` — На SERIALIZABLE / RR — обязателен retry на `CannotSerializeTransactionException` (PG код 40001)

1–3 попытки с back-off.

### `pg-runtime/idle-in-transaction-timeout` — Серверный `idle_in_transaction_session_timeout = 30–60 сек`

— автоматически убивает idle-транзакции.

### Антипаттерны Isolation

`pg-runtime/serializable-for-cross-row-invariants` `@Transactional(isolation = SERIALIZABLE)` на каждом методе «на всякий случай» — % rollback'ов скакнёт.

`pg-runtime/repeatable-read-for-consistent-snapshot` `Isolation.REPEATABLE_READ` на коротком read-modify-write вместо `SELECT FOR UPDATE`.

`pg-runtime/isolation-is-not-a-constraint` Поднимать уровень изоляции, когда корень проблемы — отсутствие constraint'а в схеме (CHECK / EXCLUDE).

`pg-runtime/retry-on-serialization-failure` SERIALIZABLE без retry на `CannotSerializeTransactionException`.

`pg-runtime/idle-in-transaction-timeout` Долгие RR/SERIALIZABLE-транзакции — каждая держит snapshot, мешает autovacuum.

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
