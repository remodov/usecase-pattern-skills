# Caching — реализация на Python (redis.asyncio / aiocache)

Реализация язык-нейтрального контракта `../spec.md` (`R-CACHE-*`) на Python. Коды общие с Java; меняется
механизм: у Python нет декларативного `@Cacheable` Spring — либо **явный cache-aside** через тонкий cache-порт над
`redis.asyncio`, либо **`aiocache`** (`@cached`-декоратор с TTL/serializer). Кеш-порт — `Protocol` в `core/`,
реализация в `adapters/out/cache/` (cross-ref `hexagonal/outbound-port-interface-in-core`).

## 1. Где кешируем (`R-CACHE-WHERE-*`)

`caching/cache-read-heavy-stable-data` — read-heavy + редко меняющиеся (профили, справочники, feature-flags). `caching/money-data-needs-explicit-invalidation` —
money-данные только с явной invalidation: короткий TTL (5–30с) + инвалидация на каждом write + evict перед
критичным чтением. `caching/cache-aside-is-default` — cache-aside (lazy + evict на write) — дефолт.

`caching/no-cache-on-write-path` — кеш на write-path (кешировать `create_order()`). `caching/cache-projections-not-aggregates` — кеш **доменного агрегата
целиком** (нарушает границы, сложная invalidation) — кешируй read-проекции (`OrderSummary`), не `Order`.
`caching/money-data-needs-explicit-invalidation` — money без TTL/invalidation. `caching/cache-read-heavy-stable-data` — кеш бизнес-критичного без оценки trade-off.
`caching/no-caching-authorization-results` — кеш результата авторизации/валидации (ABAC каждый раз; JWK-кеш — встроен, `auth-patterns/token-validated-by-library`).

## 2. Конфигурация (`R-CACHE-CFG-*`)

`caching/distributed-cache-in-production` — в проде backend — **Redis** (`redis.asyncio`), не in-memory dict (каждый процесс — свой кеш).
`caching/values-serialized-as-json` — сериализация — **JSON**, **никогда `pickle`** (RCE при десериализации недоверенных данных, как
`JdkSerializationRedisSerializer`). `caching/explicit-ttl-per-cache` — per-cache explicit TTL. `caching/cache-settings-are-typed` — настройки через
`pydantic-settings`. `caching/tests-use-real-cache` — в тестах — Testcontainers Redis или in-memory backend, не мок cache-порта
(теряется поведение TTL/eviction).

`caching/values-serialized-as-json` — `pickle`-сериализация (`aiocache.PickleSerializer`) — security risk. `caching/distributed-cache-in-production` — in-memory
dict-кеш в multi-instance проде. `caching/explicit-ttl-per-cache` — один глобальный TTL на все кеши. `caching/no-cache-without-manager` — «кеширование»
без реального backend (тихо ничего не кеширует).

```python
from datetime import timedelta
from pydantic_settings import BaseSettings, SettingsConfigDict

# R-CACHE-CFG-4 + R-CACHE-TTL-3: per-cache explicit TTL из настроек, не хардкод, не один глобальный (R-CACHE-CFG-X3).
class CacheSettings(BaseSettings):
    redis_url: str                                   # R-CACHE-CFG-1: Redis в проде, не in-memory dict (R-CACHE-CFG-X2)
    ttl_user_profiles: int = 15 * 60                 # сек; R-CACHE-TTL-1: explicit, не infinite (R-CACHE-TTL-X1)
    ttl_currencies: int = 6 * 3600
    ttl_feature_flags: int = 60
    ttl_balance: int = 15                            # R-CACHE-TTL-X3: money ≤ 1м + строгая invalidation
    model_config = SettingsConfigDict(env_prefix="CACHE_")

# Кеш-порт — Protocol в core/ (cross-ref R-HEX-PORT-1); реализация в adapters/out/cache/.
class CacheProvider(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, *, ttl: int) -> None: ...
    async def delete(self, *keys: str) -> None: ...

# adapters/out/cache/redis_cache_provider.py — тонкая обёртка над redis.asyncio.
class RedisCacheProvider:                            # implements CacheProvider
    def __init__(self, redis: "redis.asyncio.Redis") -> None:
        self._redis = redis

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, *, ttl: int) -> None:
        # R-CACHE-CFG-2: значение — JSON-строка, НЕ pickle (RCE при десериализации, R-CACHE-CFG-X1).
        await self._redis.set(key, value, ex=ttl)   # ex=TTL обязателен (R-CACHE-TTL-X1)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._redis.delete(*keys)
```

## 3. Ключи (`R-CACHE-KEY-*`)

`caching/cache-name-is-namespace` — namespace через префикс имени кеша (`user-profiles:42`). `caching/cache-name-is-namespace` — имена kebab-case
(`user-profiles`, `feature-flags`). `caching/explicit-cache-key` — ключ внутри namespace — explicit (`f"user-profiles:{user_id}"`),
не «весь объект». `caching/custom-key-generator-when-needed` — кастомная сборка ключа — только для сложных случаев, читаемо.

`caching/explicit-cache-key` — ключ из всех аргументов автоматически (ломается при смене сигнатуры). `caching/explicit-cache-key` — дефолтный
`repr()`/`id()` объекта в ключе (`<User object at 0x..>` — каждый вызов новый ключ). `caching/cache-name-is-namespace` — общий cache на
разные entity (теряется namespacing/метрики). `caching/no-sensitive-data-in-keys` — sensitive (email/phone/токен) в ключе plain-text
(виден в Redis/логах) — хешировать (`sha256`).

```python
import hashlib

# R-CACHE-KEY-1/2/3: namespace-префикс kebab-case + explicit f-string ключ; НЕ авто-ключ из всех аргументов (R-CACHE-KEY-X1).
def user_profile_key(user_id: int) -> str:
    return f"user-profiles:{user_id}"               # user-profiles:42

def orders_by_customer_key(customer_id: int, status: str) -> str:
    return f"orders-by-customer:{customer_id}:{status}"   # composite — явный, читаемый

# R-CACHE-KEY-X4: sensitive в ключе — только хеш, не plain-text (виден в redis-cli/логах).
def session_by_email_key(email: str) -> str:
    digest = hashlib.sha256(email.encode()).hexdigest()
    return f"sessions:{digest}"
```

## 4. TTL (`R-CACHE-TTL-*`)

`caching/explicit-ttl-per-cache` — **каждый кеш — explicit TTL**, никаких infinite. `caching/ttl-matches-data-nature` — типовые по характеру (профиль
~15м, справочники ~6ч, feature-flags ~60с, money 5–30с). `caching/explicit-ttl-per-cache` — TTL через настройки, не хардкод.
`caching/ttl-matches-data-nature` — при естественном invalidation-событии TTL длиннее (инвалидация делает работу); иначе короткий.

`caching/explicit-ttl-per-cache` — TTL = 0/None трактуется как «навсегда» (Redis LRU-eviction вне контроля). `caching/ttl-matches-data-nature` —
TTL > 24ч для бизнес-данных (переживает деплои, устаревшая структура DTO). `caching/money-data-needs-explicit-invalidation` — money без TTL / TTL > 1м
без строгой invalidation.

## 5. Invalidation (`R-CACHE-INV-*`)

`caching/write-evicts-affected-caches` — на каждом write того же ресурса — evict затронутых ключей (`await cache.delete("user-profiles:42")`).
`caching/write-evicts-affected-caches` — write меняет несколько кешей → evict всех затронутых. `caching/invalidate-on-domain-event` — при доменных событиях —
invalidation как side-effect (consumer/handler события). `caching/distributed-invalidation-is-built-in` — distributed invalidation встроена в Redis
(общий backend), отдельной обвязки не надо.

`caching/no-routine-full-flush` — evict-all (`FLUSHDB`/удаление по всему namespace) без причины (холодный старт → spike на БД); только
для админ-операций. `caching/ttl-is-not-consistency` — полагаться только на TTL для money/orders. `caching/staleness-is-declared` — eventual
consistency кеша без декларации в API.

```python
# R-CACHE-INV-1: на write того же ресурса — evict затронутых ключей. Доступ к БД — через репозиторий,
# handler/service оркестрирует и держит UoW; кеш-инвалидация — side-effect ПОСЛЕ успешного commit.
class UpdateProfileHandler:
    def __init__(self, session_factory, profile_repo: ProfileRepository, cache: CacheProvider) -> None:
        self._session_factory = session_factory
        self._profile_repo = profile_repo
        self._cache = cache

    async def handle(self, cmd: UpdateProfileCommand) -> None:
        async with self._session_factory() as session, session.begin():   # UoW в handler
            await self._profile_repo.update(session, cmd.user_id, cmd.changes)  # запись — только в репозитории
        # R-CACHE-INV-2: write затронул несколько кешей → evict всех; после commit, не внутри TX.
        await self._cache.delete(
            user_profile_key(cmd.user_id),
            f"user-permissions:{cmd.user_id}")
        # R-CACHE-INV-X1: НЕ FLUSHDB / delete по всему namespace — точечный evict по ключам.
```

## 6. Паттерны (`R-CACHE-PATTERN-*`)

`caching/cache-aside-is-default` — **cache-aside** (lazy get-or-load + evict на write) — дефолт. `caching/cache-aside-is-default` —
write-through (явный `cache.set` на write) — для high read+write одного значения. `caching/cache-aside-is-default` — refresh-ahead
(`@Scheduled`/APScheduler перезаливает hot-ключи до TTL).

`caching/cache-aside-is-default` — write-behind (в кеш сейчас, в БД async позже) для money/critical (crash → потеря). `caching/cache-aside-is-default` —
смешение паттернов на одном кеше (непонятная invalidation) — один cache = один паттерн.

```python
# R-CACHE-PATTERN-1: cache-aside (lazy get-or-load + evict на write) — дефолт.
# Read-проекция (R-CACHE-WHERE-X2: НЕ агрегат целиком), доступ к БД — через репозиторий, не raw в сервисе.
class ProfileQueryService:
    def __init__(self, session_factory, profile_repo: ProfileRepository,
                 cache: CacheProvider, settings: CacheSettings) -> None:
        self._session_factory = session_factory
        self._profile_repo = profile_repo
        self._cache = cache
        self._settings = settings

    async def get_profile(self, user_id: int) -> UserProfileView:
        key = user_profile_key(user_id)
        cached = await self._cache.get(key)
        if cached is not None:
            return UserProfileView.model_validate_json(cached)      # hit
        # miss → грузим через репозиторий (БД-доступ только там), кладём read-DTO в кеш
        async with self._session_factory() as session:
            view = await self._profile_repo.load_summary(session, user_id)
        await self._cache.set(
            key, view.model_dump_json(), ttl=self._settings.ttl_user_profiles)  # explicit TTL
        return view
```

## 7. Cache stampede (`R-CACHE-STAMP-*`)

`caching/stampede-protection` — для локального backend — single-flight (`aiocache` lock / `asyncio.Lock` на ключ) — параллельные
вызовы одного ключа ждут первого. `caching/stampede-protection` — для Redis (multi-instance) — **distributed lock** (`redis.lock`
/ `aiocache` RedLock), `asyncio.Lock` не виден другим процессам. `caching/stampede-protection` — для hot-ключей — refresh-ahead
(stampede исключён по дизайну).

`caching/stampede-protection` — игнор stampede для hot-эндпоинтов (>100 RPS, общий miss → DB-инцидент). `caching/stampede-protection` —
`asyncio.Lock` как защита distributed-кеша (lock в одном процессе, не виден другим).

```python
# R-CACHE-STAMP-2: для Redis (multi-instance) — DISTRIBUTED lock через redis.asyncio SET NX PX.
# asyncio.Lock виден только в одном процессе → НЕ защищает distributed-кеш (R-CACHE-STAMP-X2).
async def get_profile_single_flight(
    self, user_id: int) -> UserProfileView:
    key = user_profile_key(user_id)
    cached = await self._cache.get(key)
    if cached is not None:
        return UserProfileView.model_validate_json(cached)

    lock_key = f"{key}:lock"
    # SET NX PX — атомарно ставит lock с TTL; canon redis.asyncio, НЕ asyncio.Lock, НЕ Redisson (это Java).
    got_lock = await self._redis.set(lock_key, "1", nx=True, px=3000)
    if not got_lock:
        # кто-то уже грузит — короткое ожидание и повторный read из кеша (избегаем общего miss в БД)
        await asyncio.sleep(0.05)
        cached = await self._cache.get(key)
        if cached is not None:
            return UserProfileView.model_validate_json(cached)
    try:
        # double-check: пока ждали lock, значение могло появиться
        cached = await self._cache.get(key)
        if cached is not None:
            return UserProfileView.model_validate_json(cached)
        async with self._session_factory() as session:        # БД-доступ — только через репозиторий
            view = await self._profile_repo.load_summary(session, user_id)
        await self._cache.set(key, view.model_dump_json(), ttl=self._settings.ttl_user_profiles)
        return view
    finally:
        if got_lock:
            await self._redis.delete(lock_key)

# Альтернатива — высокоуровневый Redis.lock() (тот же SET NX PX под капотом):
#   async with self._redis.lock(lock_key, timeout=3):
#       ...  # double-check + load + set
```

## 8. Observability (`R-CACHE-OBS-*`)

`caching/cache-metrics-enabled` — метрики hits/misses/evictions через `prometheus-client`. `caching/cache-metrics-enabled` — **hit rate** = главная;
alert при < 70% для долгих кешей. `caching/eviction-logged-at-debug` — eviction логировать на DEBUG, не INFO. `caching/cache-metrics-enabled` — Redis-side
метрики через Redis Exporter.

`caching/cache-metrics-enabled` — отключение cache-метрик (SRE не увидит hit rate 5%).

## 9. Чеклист подключения к новому сервису (Python)

1. Кешируются read-проекции, не агрегаты; не write-path; не авторизация; money — короткий TTL + invalidation.
2. Backend Redis (`redis.asyncio`), JSON-сериализация (не pickle), per-cache TTL, тесты на Testcontainers.
3. Ключи: namespace-префикс, explicit, kebab-case, sensitive хешировано.
4. Каждый кеш — explicit TTL ≤ 24ч; money ≤ 1м со strict invalidation.
5. Evict на write того же ресурса; нет evict-all без причины; eventual consistency задекларирована.
6. Один паттерн на кеш; нет write-behind для money; stampede — distributed lock / refresh-ahead.
7. hit-rate метрика + alert.
