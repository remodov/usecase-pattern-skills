# PostgreSQL Runtime — индекс правил

> **Что это.** Сжатый индекс правил `pg-runtime-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с SQL-примерами, yaml-конфигами и обоснованием — `pg-runtime-style-guide.md`**; открывай её точечно по разделу.
> Коды: `PG-W-*` (WAL), `PG-V-*` (VACUUM), `PG-L-*` (Locks), `PG-CP-*` (Connection Pool), `PG-IS-*` (Isolation).
> X-кодов нет; антипаттерны — обычные номера `…-09X`/`…-08X` в блоках «Антипаттерны».

Базовый принцип: **скорость и стабильность OLTP определяются не SQL, а тем, как код взаимодействует с MVCC** — длинная транзакция, кривой `UPDATE`, лишний индекс перетекают в WAL, bloat, локи.

## 1. WAL
**MUST:**
- **PG-W-010.** Массовая вставка — `COPY` (`CopyManager`), не цикл `INSERT` (10–100× по времени, 5–10× по WAL); fallback — `batchUpdate` 1–10K строк.
- **PG-W-011.** Один большой `COMMIT` дешевле многих маленьких (меньше fsync), но длинная транзакция блокирует autovacuum — оптимум батч 1–10K.
- **PG-W-012.** Перед массовой загрузкой в пустую таблицу — дроп индексов, загрузка, восстановление.
- **PG-W-020.** HOT (Heap-Only Tuple): `UPDATE` без переписывания индексов, если есть место на странице и не изменены индексируемые колонки.
- **PG-W-021.** Для интенсивно обновляемых таблиц — `fillfactor = 80–90` в DDL (дефолт 100 убивает HOT); цена +10–20% места, выигрыш кратный по WAL.
- **PG-W-022.** HOT отключается при `UPDATE` индексируемой колонки; часто меняемое слабоселективное поле (`last_seen_at`) — индекс, возможно, удалить. `hot_pct < 50%` → снизить fillfactor.
- **PG-W-030.** Большое TOAST-значение не переписывается при UPDATE, если не изменилось — аргумент против «всё в один большой `data jsonb`».
- **PG-W-031.** Часто-обновляемые маленькие и редко-меняющиеся большие поля — TOAST разделит (> ~2KB) либо разделяй на две таблицы.
- **PG-W-040.** Данные, которые можно потерять при crash (кеши, ETL, очереди с TTL) — `UNLOGGED` таблица (нет WAL, нет реплики).
- **PG-W-041.** `UNLOGGED → LOGGED` переписывает всю таблицу с полным WAL — разовая операция, не в hot path.
- **PG-W-050.** `synchronous_commit = off`: прирост throughput ценой ~200мс потерянных транзакций при крахе. Финансы/заказы — никогда; аналитика/метрики/логи — приемлемо.
- **PG-W-051.** Регулируй на уровне сессии: `SET LOCAL synchronous_commit = off` для batch-импорта.
- **PG-W-060.** Открытая долгая транзакция блокирует освобождение WAL и autovacuum (MVCC) → диск заполняется → кластер встаёт.
- **PG-W-061.** Не делай долгие транзакции в коде: транзакция вокруг HTTP/Kafka/S3 = открытая транзакция на десятки секунд. Транзакция — секунды, не минуты.
- **PG-W-062.** Алёрт на `xact_age > 5 минут` в `pg_stat_activity`.
- **PG-W-070.** Висящий replication slot не даёт удалить WAL; алёрт на `lag_bytes > 10GB` или `active=false` дольше часа; PG13+ — `max_slot_wal_keep_size`.

## 2. VACUUM и bloat
**MUST:**
- **PG-V-001.** VACUUM освобождает место от dead tuples (не возвращает ОС), обновляет visibility map, защищает от XID wraparound; не блокирует чтение/запись.
- **PG-V-010.** `VACUUM FULL` почти никогда в проде (ACCESS EXCLUSIVE блокирует всё); альтернатива — `pg_repack` / `pg_squeeze`.
- **PG-V-011.** `VACUUM ANALYZE` руками после массовой миграции — иначе планировщик долго на устаревшей статистике.
- **PG-V-020.** Дефолты autovacuum хороши для большинства проектов — не трогай без причины.
- **PG-V-021.** На больших горячих таблицах дефолт `scale_factor=0.2` мал — снизь до 0.05 per-table.
- **PG-V-030.** Базовый мониторинг — `pg_stat_user_tables` (`n_dead_tup`, `last_autovacuum`); `dead_pct > 20%` — кандидат на ручной VACUUM.
- **PG-V-031.** Точный — `pgstattuple`; `dead_tuple_percent > 30%` = bloat.
- **PG-V-032.** Bloat индексов — `REINDEX CONCURRENTLY` (PG12+), не блокирует таблицу.
- **PG-V-050.** Долгая транзакция блокирует освобождение dead tuples (см. `PG-W-060`).
- **PG-V-051.** Висящий replication slot — те же эффекты (см. `PG-W-070`).
- **PG-V-052.** Prepared transactions в `pg_prepared_xacts` — те же эффекты.
- **PG-V-053.** Проверяй отключённый autovacuum (глобально / per-table) через `pg_class.reloptions`.
- **PG-V-060.** После big `UPDATE`/`DELETE` миграции — `VACUUM ANALYZE` в той же миграции.
- **PG-V-061.** `CREATE INDEX CONCURRENTLY` — после построения нужен `VACUUM`, чтобы Heap Fetches упали до нуля (Index Only Scan).

## 3. Блокировки
**MUST:**
- **PG-L-001.** `UPDATE`/`DELETE` уже берут row-level lock; параллельный `SELECT` без `FOR UPDATE` не ждёт (MVCC).
- **PG-L-010.** `SELECT … FOR UPDATE` — когда читаешь строку чтобы изменить, и нужна гарантия отсутствия вмешательства (резерв, смена статуса, UPDATE-after-SELECT).
- **PG-L-011.** `FOR UPDATE` блокирует до конца транзакции → явная транзакция обязательна.
- **PG-L-012.** В 95% — `FOR UPDATE`; `FOR NO KEY UPDATE`/`FOR SHARE`/`FOR KEY SHARE` — оптимизации, не дёргай без понимания.
- **PG-L-020.** `FOR UPDATE SKIP LOCKED` пропускает залоченные строки — паттерн для очереди задач и outbox-relay.
- **PG-L-021.** Outbox-relay обязан использовать `SKIP LOCKED` при многих инстансах — иначе дублирующая публикация.
- **PG-L-030.** `FOR UPDATE NOWAIT` — fail-fast вместо ожидания (API-таймаут).
- **PG-L-040.** query-builder'ы умеют все варианты: `FOR UPDATE`, `FOR UPDATE SKIP LOCKED`, `.forUpdate().noWait()`.
- **PG-L-041.** Lock-запрос обязан быть внутри транзакции — иначе лок отпустится мгновенно.
- **PG-L-050.** Pessimistic — `FOR UPDATE`: простой код, при высокой конкуренции — очередь TX.
- **PG-L-051.** Optimistic — через `version`-колонку (`WHERE id=? AND version=?`, 0 rows = конфликт); лучше при низкой конкуренции. Финансы/write-heavy — обычно pessimistic.
- **PG-L-060.** `pg_advisory_xact_lock(key)` — блокировка на произвольный bigint-ключ (single-instance scheduled-job, защита от двух миграций, глобальные семафоры).
- **PG-L-061.** Два bigint-аргумента, если лок логически разделяется: `pg_advisory_lock(class_id, object_id)`.
- **PG-L-070.** Deadlock — две TX берут локи в разном порядке; PG детектит через `deadlock_timeout` (1s), убивает одну с `40P01`.
- **PG-L-071.** Лечится упорядочением блокировок (перевод денег: блокировать счета по возрастанию `id`).
- **PG-L-072.** На Java стороне — retry на `CannotAcquireLockException` (1–3 попытки с backoff); нормальный исход в high-concurrency OLTP.
- **PG-L-080.** `SET LOCAL lock_timeout = '5s'` для критичных операций; особенно для миграций (`ALTER TABLE` берёт ACCESS EXCLUSIVE).

**MUST NOT:**
- **PG-L-090.** `SELECT FOR UPDATE` без транзакции — лок мгновенно отпускается.
- **PG-L-091.** `SELECT FOR UPDATE` со сложным `WHERE` без индекса — залочит кучу строк через seq scan.
- **PG-L-092.** Длинная транзакция с локом — блокирует всех ждущих и копит WAL.
- **PG-L-093.** Pessimistic lock на каждое чтение — превращает БД в очередь.
- **PG-L-094.** Брать локи в разном порядке в разных методах — deadlock.
- **PG-L-095.** `SELECT FOR UPDATE` без `LIMIT` на большой таблице — блокирует всё.

## 4. Connection pool
**MUST:**
- **PG-CP-001.** Размер пула — формула `(core_count × 2) + spindles`; для SSD ~10–20 на инстанс. «Больше = лучше» — миф.
- **PG-CP-002.** Целевой размер пула на инстанс — 10–20; кажется мало → сначала измерь (узкое место чаще в долгих запросах).
- **PG-CP-003.** Бюджет соединений PG = `max_connections` (default 100), делится на все инстансы всех сервисов; решение — поднять max_connections (300–500) или PgBouncer.
- **PG-CP-010.** Минимальный Hikari: `maximum-pool-size`, `minimum-idle = max`, `connection-timeout: 3000`, `max-lifetime: 1800000`, `leak-detection-threshold: 60000`.
- **PG-CP-011.** `maximum-pool-size = minimum-idle` — пул всегда полный, нет latency-всплесков.
- **PG-CP-012.** `connection-timeout: 3 сек` — лучше упасть, чем ждать.
- **PG-CP-013.** `max-lifetime: 30 мин` — меньше серверного `idle_in_transaction_session_timeout` и LB-таймаутов.
- **PG-CP-014.** `leak-detection-threshold: 60 сек` — алёрт на забытый close / незакрытую транзакцию вокруг HTTP. Не отключай.
- **PG-CP-030.** Метрики пула соединений в системе метрик (`active/idle/pending/usage/timeout`); алёрт на стабильный `pending > 0` или `timeout > 0`.
- **PG-CP-040.** PgBouncer оправдан: десятки инстансов, общий PG для нескольких сервисов, serverless, ограничение connections ниже суммы пулов.
- **PG-CP-041.** Уровень `transaction` (default стека) — соединение в пул после COMMIT/ROLLBACK; не работают server-side prepared (без 1.21+), `SET` без `LOCAL`, `LISTEN`/`NOTIFY`, session-advisory-locks.
- **PG-CP-042.** `session` mode — когда нужны prepared/listen/notify; эффективность ниже.
- **PG-CP-045.** На transaction mode + JDBC: `prepareThreshold = 0` — отключить server-side prepared.
- **PG-CP-050.** С PgBouncer пул Hikari может быть больше (app_pool : pgbouncer_to_pg = 5:1+).
- **PG-CP-060.** Read-replica — отдельный DataSource + пул соединений, выбор по read-only флагу транзакции.
- **PG-CP-061.** Реплика — eventual consistency; не использовать для read-after-write.

**MUST NOT:**
- **PG-CP-080.** Огромный пул (`maximum-pool-size = 200`) — почти всегда пессимизация.
- **PG-CP-081.** Разные пулы на одну БД для одного приложения — каждый думает, что владеет всеми соединениями.
- **PG-CP-082.** Транзакция вокруг внешнего HTTP — соединение удерживается всё время вызова (см. `PG-W-061`).
- **PG-CP-083.** Отключение `leak-detection-threshold` — сокрытие проблемы.
- **PG-CP-085.** PgBouncer на `session` mode без причины — теряется главный выигрыш.
- **PG-CP-086.** PgBouncer transaction + server-side prepared без `prepareThreshold=0` — JDBC дёргает PG на каждом запросе.

## 5. Уровни изоляции
**MUST:**
- **PG-IS-001.** Дефолт `READ COMMITTED` правильный в 95%; поднимать уровень — только понимая, какую аномалию предотвращаешь.
- **PG-IS-002.** PG `READ COMMITTED` строже стандарта — dirty read невозможен (MVCC).
- **PG-IS-003.** PG `REPEATABLE READ` = snapshot isolation — phantom тоже предотвращён.
- **PG-IS-010.** `READ COMMITTED` минимизирует блокировки — правильный выбор для большинства OLTP.
- **PG-IS-020.** RR фиксирует snapshot на момент первого запроса — все SELECT видят то же состояние.
- **PG-IS-021.** RR оправдан: длинный отчёт по нескольким таблицам с консистентным срезом, `pg_dump`, сложный перенос данных.
- **PG-IS-022.** На RR `UPDATE` строки, изменившейся после snapshot, падает с `40001` — Java делает retry.
- **PG-IS-023.** Не использовать RR в hot path «на всякий случай» — всплеск 40001.
- **PG-IS-030.** `SERIALIZABLE` (SSI) гарантирует эквивалент последовательного выполнения — сильнее RR.
- **PG-IS-031.** Ловит write skew, который RR пропускает (инвариант «хотя бы один врач на смене»).
- **PG-IS-032.** SERIALIZABLE — для сложных инвариантов, не выразимых через `CHECK`/`FOR UPDATE`; финансы с множественными правилами.
- **PG-IS-033.** SERIALIZABLE дороже: PG отслеживает зависимости, race → откат 40001 → retry.
- **PG-IS-034.** На большинстве OLTP не оправдан — дешевле инвариант через `SELECT FOR UPDATE` + ручной CHECK.
- **PG-IS-040.** Уровень изоляции (SERIALIZABLE | REPEATABLE_READ) на конкретном методе.
- **PG-IS-041.** `READ_COMMITTED` — дефолт, не указывай явно; в коде явно только отличие от стандарта.
- **PG-IS-042.** На SERIALIZABLE/RR обязателен retry на `CannotSerializeTransactionException` (40001), 1–3 попытки с back-off.
- **PG-IS-070.** Серверный `idle_in_transaction_session_timeout = 30–60 сек` — убивает idle-транзакции.

**MUST NOT:**
- **PG-IS-080.** `SERIALIZABLE` на каждом методе «на всякий случай» — % rollback скакнёт.
- **PG-IS-081.** `REPEATABLE_READ` на коротком read-modify-write вместо `SELECT FOR UPDATE`.
- **PG-IS-082.** Поднимать уровень изоляции, когда корень — отсутствие constraint'а в схеме (CHECK / EXCLUDE).
- **PG-IS-083.** SERIALIZABLE без retry на `CannotSerializeTransactionException`.
- **PG-IS-084.** Долгие RR/SERIALIZABLE-транзакции — каждая держит snapshot, мешает autovacuum.
