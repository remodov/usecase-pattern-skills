# Caching — реализация на Node (@nestjs/cache-manager + ioredis)

Реализация язык-нейтрального контракта `../spec.md` (`R-CACHE-*`) на Node/NestJS. Коды общие с Java;
меняется механизм: `@nestjs/cache-manager` (cache-manager + Redis-store поверх **ioredis**) с явным cache-aside в
сервисах/адаптерах; `CacheInterceptor`/`@CacheTTL` — только для простых HTTP-GET-кешей. Кеш-порт — интерфейс в
`core/`, реализация в `adapters/out/cache/` (cross-ref `hexagonal/outbound-port-interface-in-core`).

## 1. Где кешируем (`R-CACHE-WHERE-*`)

`caching/cache-read-heavy-stable-data` — read-heavy + редко меняющиеся (профили, справочники, feature-flags). `caching/money-data-needs-explicit-invalidation` —
money-данные только с явной invalidation: короткий TTL (5–30с) + `cache.del` на каждом write + evict перед
критичным чтением. `caching/cache-aside-is-default` — cache-aside (lazy + evict на write) — дефолт.

`caching/no-cache-on-write-path` — кеш на write-path (кешировать `createOrder()`; `CacheInterceptor` на POST). `caching/cache-projections-not-aggregates` —
кеш **доменного агрегата целиком** (нарушает границы, сложная invalidation) — кешируй read-проекции
(`OrderSummaryDto`), не `Order`. `caching/money-data-needs-explicit-invalidation` — money без TTL/invalidation. `caching/cache-read-heavy-stable-data` — кеш
бизнес-критичного без оценки trade-off. `caching/no-caching-authorization-results` — кеш результата авторизации/валидации (ABAC каждый
раз; JWK-кеш встроен в `jwks-rsa`, `auth-patterns/token-validated-by-library`).

## 2. Конфигурация (`R-CACHE-CFG-*`)

`caching/distributed-cache-in-production` — в проде backend — **Redis** (ioredis через Redis-store cache-manager), не in-memory store
(каждый pod — свой кеш). `caching/values-serialized-as-json` — сериализация — **JSON** (plain DTO через `JSON.stringify`); никакой
бинарной десериализации недоверенных данных (`v8.deserialize`/`eval`-подобное — аналог Java native-сериализации) и
никаких class-инстансов с методами в кеше (после round-trip это plain object). `caching/explicit-ttl-per-cache` — per-cache explicit
TTL: TTL задаётся на каждый именованный кеш из конфига, не один глобальный `ttl` модуля. `caching/cache-settings-are-typed` —
настройки через типизированный конфиг (`CacheConfig`, zod/class-validator, `nest-bootstrap/config-validated-at-startup`): host, per-cache TTL,
namespace-префикс. `caching/tests-use-real-cache` — в тестах — Testcontainers Redis (`@testcontainers/redis`) или in-memory store,
не мок кеш-порта (теряется поведение TTL/eviction).

```ts
// PREFER: backend из конфига, TTL per-cache из настроек
CacheModule.registerAsync({
  isGlobal: true,
  useFactory: (cfg: CacheConfig) => ({ store: redisStore, host: cfg.host, port: cfg.port }),
  inject: [CACHE_CONFIG],
})
// AVOID: CacheModule.register() — дефолтный in-memory store молча уезжает в прод
```

`caching/values-serialized-as-json` — бинарная/исполняемая десериализация значений из Redis (security risk). `caching/distributed-cache-in-production` —
in-memory store в multi-instance проде. `caching/explicit-ttl-per-cache` — один глобальный TTL на все кеши. `caching/no-cache-without-manager` —
«кеширование» без реального backend (дефолтный память-store вместо Redis, no-op при ошибке подключения —
тихо ничего не кеширует; fail-fast на старте).

## 3. Ключи (`R-CACHE-KEY-*`)

`caching/cache-name-is-namespace` — namespace через префикс имени кеша: `user-profiles:42` (cache-manager не префиксует сам — префикс
зашивается в кеш-порт/билдер ключей). `caching/cache-name-is-namespace` — имена kebab-case (`user-profiles`, `feature-flags`).
`caching/explicit-cache-key` — ключ внутри namespace — **explicit** (`` `user-profiles:${userId}` ``), не «весь объект».
`caching/custom-key-generator-when-needed` — кастомная сборка ключа — только для сложных случаев, читаемой функцией-билдером.

`caching/explicit-cache-key` — автоключ из всех аргументов метода (ломается при смене сигнатуры); у `CacheInterceptor` дефолтный
ключ = URL — для service-методов ключ всегда явный. `caching/explicit-cache-key` — `String(obj)`/`JSON.stringify(obj)` целого
DTO в ключе (`[object Object]` / нестабильный порядок полей). `caching/cache-name-is-namespace` — общий cache на разные entity
(теряется namespacing/метрики). `caching/no-sensitive-data-in-keys` — sensitive (email/phone/токен) в ключе plain-text (виден в
Redis/логах) — хешировать (`createHash('sha256')`).

## 4. TTL (`R-CACHE-TTL-*`)

`caching/explicit-ttl-per-cache` — **каждый кеш — explicit TTL**: `cache.set(key, dto, ttlMs)` всегда с третьим аргументом
(или `@CacheTTL(...)` для interceptor); никаких infinite. `caching/ttl-matches-data-nature` — типовые по характеру (профиль ~15м,
справочники ~6ч, feature-flags ~60с, money 5–30с). `caching/explicit-ttl-per-cache` — TTL из `CacheConfig`, не хардкод-литерал в
вызове. `caching/ttl-matches-data-nature` — при естественном invalidation-событии TTL длиннее (инвалидация делает работу); иначе
короткий.

`caching/explicit-ttl-per-cache` — `cache.set(key, value)` без TTL / `ttl: 0` — «навсегда» (Redis LRU-eviction вне контроля).
`caching/ttl-matches-data-nature` — TTL > 24ч для бизнес-данных (переживает деплои, устаревшая структура DTO). `caching/money-data-needs-explicit-invalidation` —
money без TTL / TTL > 1м без строгой invalidation.

## 5. Invalidation (`R-CACHE-INV-*`)

`caching/write-evicts-affected-caches` — на каждом write-методе того же ресурса — evict затронутых ключей
(`await cache.del('user-profiles:42')`). `caching/write-evicts-affected-caches` — write меняет несколько кешей →
`Promise.all([cache.del(...), cache.del(...)])`. `caching/invalidate-on-domain-event` — при доменных событиях — invalidation как
side-effect: `@OnEvent('user.updated')`-handler (или Kafka-consumer) делает evict — независимо от того, какой use
case вызвал изменение. `caching/distributed-invalidation-is-built-in` — distributed invalidation встроена: общий Redis-backend на все инстансы,
отдельной обвязки не надо.

```ts
// PREFER: точечный evict на write
async updateProfile(cmd: UpdateProfileCommand): Promise<void> {
  await this.repo.update(cmd);
  await this.cache.del(`user-profiles:${cmd.userId}`);
}
// AVOID: await this.cache.reset()  — clear-all, холодный старт → spike на БД
```

`caching/no-routine-full-flush` — `cache.reset()`/`FLUSHDB`/массовое удаление namespace без причины — только для админ-операций.
`caching/ttl-is-not-consistency` — полагаться только на TTL для money/orders. `caching/staleness-is-declared` — eventual consistency кеша без
декларации в OpenAPI (`@ApiOperation({ description: 'Возможна задержка до 30 секунд' })`).

## 6. Паттерны (`R-CACHE-PATTERN-*`)

`caching/cache-aside-is-default` — **cache-aside** (get → miss → load → `set` с TTL; evict на write) — дефолт.
`caching/cache-aside-is-default` — write-through (явный `cache.set` на write вместо evict) — для high read+write одного значения.
`caching/cache-aside-is-default` — refresh-ahead: `@Cron`/`@Interval` (`@nestjs/schedule`) перезаливает hot-ключи до истечения TTL.

`caching/cache-aside-is-default` — write-behind (в кеш сейчас, в БД async позже) для money/critical (crash → потеря).
`caching/cache-aside-is-default` — смешение паттернов на одном кеше (непонятная invalidation) — один cache = один паттерн.

## 7. Cache stampede (`R-CACHE-STAMP-*`)

`caching/stampede-protection` — для одного инстанса — **локальный single-flight**: `Map<string, Promise<T>>` in-flight загрузок —
параллельные вызовы одного ключа ждут один promise. `caching/stampede-protection` — для Redis (multi-instance) — **distributed
lock**: `redlock` (поверх ioredis) вокруг load-on-miss; локальный single-flight не виден другим процессам.
`caching/stampede-protection` — для hot-ключей — refresh-ahead (stampede исключён по дизайну).

```ts
private readonly inFlight = new Map<string, Promise<UserProfileDto>>();

async getProfile(userId: number): Promise<UserProfileDto> {
  const key = `user-profiles:${userId}`;
  const hit = await this.cache.get<UserProfileDto>(key);
  if (hit) return hit;
  let load = this.inFlight.get(key);                       // single-flight (R-CACHE-STAMP-1)
  if (!load) {
    load = this.loadAndSet(key, userId).finally(() => this.inFlight.delete(key));
    this.inFlight.set(key, load);
  }
  return load;
}
```

`caching/stampede-protection` — игнор stampede для hot-эндпоинтов (>100 RPS, общий miss → DB-инцидент). `caching/stampede-protection` —
локальный single-flight/`Map`-lock как защита distributed-кеша (виден одному процессу) — redlock.

## 8. Observability (`R-CACHE-OBS-*`)

`caching/cache-metrics-enabled` — метрики hits/misses/evictions через `prom-client` (counters в кеш-порте — cache-manager сам не
экспортирует). `caching/cache-metrics-enabled` — **hit rate** = главная; alert при < 70% для долгих кешей. `caching/eviction-logged-at-debug` —
eviction логировать на DEBUG, не INFO. `caching/cache-metrics-enabled` — Redis-side метрики через Redis Exporter.

`caching/cache-metrics-enabled` — отсутствие cache-метрик (SRE не увидит hit rate 5%).

## 9. Чеклист подключения к новому сервису (Node/NestJS)

1. Кешируются read-проекции (DTO), не агрегаты; не write-path; не авторизация; money — короткий TTL + invalidation.
2. Backend Redis (ioredis-store), plain-JSON значения, per-cache TTL из конфига, fail-fast без backend;
   тесты на Testcontainers Redis.
3. Ключи: namespace-префикс, explicit-билдер, kebab-case, sensitive хешировано; `CacheInterceptor` — только
   простые HTTP-GET.
4. Каждый `cache.set` — с TTL ≤ 24ч; money ≤ 1м со strict invalidation.
5. `cache.del` на write того же ресурса и в `@OnEvent`-handler'ах; нет `cache.reset()` без причины; EC кеша
   задекларирована.
6. Один паттерн на кеш; нет write-behind для money; stampede — redlock (multi-instance) или single-flight + refresh-ahead.
7. hit/miss-метрики в кеш-порте + alert на hit rate.
