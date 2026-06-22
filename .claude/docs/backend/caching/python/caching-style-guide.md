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

`R-CACHE-KEY-1` — namespace через префикс имени кеша (`user-profiles:42`). `R-CACHE-KEY-2` — имена kebab-case
(`user-profiles`, `feature-flags`). `R-CACHE-KEY-3` — ключ внутри namespace — explicit (`f"user-profiles:{user_id}"`),
не «весь объект». `R-CACHE-KEY-4` — кастомная сборка ключа — только для сложных случаев, читаемо.

`R-CACHE-KEY-X1` — ключ из всех аргументов автоматически (ломается при смене сигнатуры). `R-CACHE-KEY-X2` — дефолтный
`repr()`/`id()` объекта в ключе (`<User object at 0x..>` — каждый вызов новый ключ). `R-CACHE-KEY-X3` — общий cache на
разные entity (теряется namespacing/метрики). `R-CACHE-KEY-X4` — sensitive (email/phone/токен) в ключе plain-text
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

`R-CACHE-PATTERN-1` — **cache-aside** (lazy get-or-load + evict на write) — дефолт. `R-CACHE-PATTERN-2` —
write-through (явный `cache.set` на write) — для high read+write одного значения. `R-CACHE-PATTERN-3` — refresh-ahead
(`@Scheduled`/APScheduler перезаливает hot-ключи до TTL).

`R-CACHE-PATTERN-X1` — write-behind (в кеш сейчас, в БД async позже) для money/critical (crash → потеря). `R-CACHE-PATTERN-X2` —
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

`R-CACHE-STAMP-1` — для локального backend — single-flight (`aiocache` lock / `asyncio.Lock` на ключ) — параллельные
вызовы одного ключа ждут первого. `R-CACHE-STAMP-2` — для Redis (multi-instance) — **distributed lock** (`redis.lock`
/ `aiocache` RedLock), `asyncio.Lock` не виден другим процессам. `R-CACHE-STAMP-3` — для hot-ключей — refresh-ahead
(stampede исключён по дизайну).

`R-CACHE-STAMP-X1` — игнор stampede для hot-эндпоинтов (>100 RPS, общий miss → DB-инцидент). `R-CACHE-STAMP-X2` —
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
