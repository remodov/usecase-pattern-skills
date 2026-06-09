# Caching — Python Style Guide (redis.asyncio / aiocache)

Реализация язык-нейтрального контракта `../caching-rules.md` (`R-CACHE-*`) на Python. Коды общие с Java; меняется
механизм: у Python нет декларативного `@Cacheable` Spring — либо **явный cache-aside** через тонкий cache-порт над
`redis.asyncio`, либо **`aiocache`** (`@cached`-декоратор с TTL/serializer). Кеш-порт — `Protocol` в `core/`,
реализация в `adapters/out/cache/` (cross-ref `R-HEX-PORT-1`).

## 1. Где кешируем (`R-CACHE-WHERE-*`)

`R-CACHE-WHERE-1` — read-heavy + редко меняющиеся (профили, справочники, feature-flags). `R-CACHE-WHERE-2` —
money-данные только с явной invalidation: короткий TTL (5–30с) + инвалидация на каждом write + evict перед
критичным чтением. `R-CACHE-WHERE-3` — cache-aside (lazy + evict на write) — дефолт.

`R-CACHE-WHERE-X1` — кеш на write-path (кешировать `create_order()`). `R-CACHE-WHERE-X2` — кеш **доменного агрегата
целиком** (нарушает границы, сложная invalidation) — кешируй read-проекции (`OrderSummary`), не `Order`.
`R-CACHE-WHERE-X3` — money без TTL/invalidation. `R-CACHE-WHERE-X4` — кеш бизнес-критичного без оценки trade-off.
`R-CACHE-WHERE-X5` — кеш результата авторизации/валидации (ABAC каждый раз; JWK-кеш — встроен, `AUTH-5`).

## 2. Конфигурация (`R-CACHE-CFG-*`)

`R-CACHE-CFG-1` — в проде backend — **Redis** (`redis.asyncio`), не in-memory dict (каждый процесс — свой кеш).
`R-CACHE-CFG-2` — сериализация — **JSON**, **никогда `pickle`** (RCE при десериализации недоверенных данных, как
`JdkSerializationRedisSerializer`). `R-CACHE-CFG-3` — per-cache explicit TTL. `R-CACHE-CFG-4` — настройки через
`pydantic-settings`. `R-CACHE-CFG-5` — в тестах — Testcontainers Redis или in-memory backend, не мок cache-порта
(теряется поведение TTL/eviction).

`R-CACHE-CFG-X1` — `pickle`-сериализация (`aiocache.PickleSerializer`) — security risk. `R-CACHE-CFG-X2` — in-memory
dict-кеш в multi-instance проде. `R-CACHE-CFG-X3` — один глобальный TTL на все кеши. `R-CACHE-CFG-X4` — «кеширование»
без реального backend (тихо ничего не кеширует).

## 3. Ключи (`R-CACHE-KEY-*`)

`R-CACHE-KEY-1` — namespace через префикс имени кеша (`user-profiles:42`). `R-CACHE-KEY-2` — имена kebab-case
(`user-profiles`, `feature-flags`). `R-CACHE-KEY-3` — ключ внутри namespace — explicit (`f"user-profiles:{user_id}"`),
не «весь объект». `R-CACHE-KEY-4` — кастомная сборка ключа — только для сложных случаев, читаемо.

`R-CACHE-KEY-X1` — ключ из всех аргументов автоматически (ломается при смене сигнатуры). `R-CACHE-KEY-X2` — дефолтный
`repr()`/`id()` объекта в ключе (`<User object at 0x..>` — каждый вызов новый ключ). `R-CACHE-KEY-X3` — общий cache на
разные entity (теряется namespacing/метрики). `R-CACHE-KEY-X4` — sensitive (email/phone/токен) в ключе plain-text
(виден в Redis/логах) — хешировать (`sha256`).

## 4. TTL (`R-CACHE-TTL-*`)

`R-CACHE-TTL-1` — **каждый кеш — explicit TTL**, никаких infinite. `R-CACHE-TTL-2` — типовые по характеру (профиль
~15м, справочники ~6ч, feature-flags ~60с, money 5–30с). `R-CACHE-TTL-3` — TTL через настройки, не хардкод.
`R-CACHE-TTL-4` — при естественном invalidation-событии TTL длиннее (инвалидация делает работу); иначе короткий.

`R-CACHE-TTL-X1` — TTL = 0/None трактуется как «навсегда» (Redis LRU-eviction вне контроля). `R-CACHE-TTL-X2` —
TTL > 24ч для бизнес-данных (переживает деплои, устаревшая структура DTO). `R-CACHE-TTL-X3` — money без TTL / TTL > 1м
без строгой invalidation.

## 5. Invalidation (`R-CACHE-INV-*`)

`R-CACHE-INV-1` — на каждом write того же ресурса — evict затронутых ключей (`await cache.delete("user-profiles:42")`).
`R-CACHE-INV-2` — write меняет несколько кешей → evict всех затронутых. `R-CACHE-INV-3` — при доменных событиях —
invalidation как side-effect (consumer/handler события). `R-CACHE-INV-4` — distributed invalidation встроена в Redis
(общий backend), отдельной обвязки не надо.

`R-CACHE-INV-X1` — evict-all (`FLUSHDB`/удаление по всему namespace) без причины (холодный старт → spike на БД); только
для админ-операций. `R-CACHE-INV-X2` — полагаться только на TTL для money/orders. `R-CACHE-INV-X3` — eventual
consistency кеша без декларации в API.

## 6. Паттерны (`R-CACHE-PATTERN-*`)

`R-CACHE-PATTERN-1` — **cache-aside** (lazy get-or-load + evict на write) — дефолт. `R-CACHE-PATTERN-2` —
write-through (явный `cache.set` на write) — для high read+write одного значения. `R-CACHE-PATTERN-3` — refresh-ahead
(`@Scheduled`/APScheduler перезаливает hot-ключи до TTL).

`R-CACHE-PATTERN-X1` — write-behind (в кеш сейчас, в БД async позже) для money/critical (crash → потеря). `R-CACHE-PATTERN-X2` —
смешение паттернов на одном кеше (непонятная invalidation) — один cache = один паттерн.

## 7. Cache stampede (`R-CACHE-STAMP-*`)

`R-CACHE-STAMP-1` — для локального backend — single-flight (`aiocache` lock / `asyncio.Lock` на ключ) — параллельные
вызовы одного ключа ждут первого. `R-CACHE-STAMP-2` — для Redis (multi-instance) — **distributed lock** (`redis.lock`
/ `aiocache` RedLock), `asyncio.Lock` не виден другим процессам. `R-CACHE-STAMP-3` — для hot-ключей — refresh-ahead
(stampede исключён по дизайну).

`R-CACHE-STAMP-X1` — игнор stampede для hot-эндпоинтов (>100 RPS, общий miss → DB-инцидент). `R-CACHE-STAMP-X2` —
`asyncio.Lock` как защита distributed-кеша (lock в одном процессе, не виден другим).

## 8. Observability (`R-CACHE-OBS-*`)

`R-CACHE-OBS-1` — метрики hits/misses/evictions через `prometheus-client`. `R-CACHE-OBS-2` — **hit rate** = главная;
alert при < 70% для долгих кешей. `R-CACHE-OBS-3` — eviction логировать на DEBUG, не INFO. `R-CACHE-OBS-4` — Redis-side
метрики через Redis Exporter.

`R-CACHE-OBS-X1` — отключение cache-метрик (SRE не увидит hit rate 5%).

## 9. Чеклист подключения к новому сервису (Python)

1. Кешируются read-проекции, не агрегаты; не write-path; не авторизация; money — короткий TTL + invalidation.
2. Backend Redis (`redis.asyncio`), JSON-сериализация (не pickle), per-cache TTL, тесты на Testcontainers.
3. Ключи: namespace-префикс, explicit, kebab-case, sensitive хешировано.
4. Каждый кеш — explicit TTL ≤ 24ч; money ≤ 1м со strict invalidation.
5. Evict на write того же ресурса; нет evict-all без причины; eventual consistency задекларирована.
6. Один паттерн на кеш; нет write-behind для money; stampede — distributed lock / refresh-ahead.
7. hit-rate метрика + alert.
