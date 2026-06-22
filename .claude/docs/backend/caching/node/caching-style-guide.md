# Caching — Node Style Guide (@nestjs/cache-manager + ioredis)

Реализация язык-нейтрального контракта `../caching-rules.md` (`R-CACHE-*`) на Node/NestJS. Коды общие с Java;
меняется механизм: `@nestjs/cache-manager` (cache-manager + Redis-store поверх **ioredis**) с явным cache-aside в
сервисах/адаптерах; `CacheInterceptor`/`@CacheTTL` — только для простых HTTP-GET-кешей. Кеш-порт — интерфейс в
`core/`, реализация в `adapters/out/cache/` (cross-ref `R-HEX-PORT-1`).

## 1. Где кешируем (`R-CACHE-WHERE-*`)

`R-CACHE-WHERE-1` — read-heavy + редко меняющиеся (профили, справочники, feature-flags). `R-CACHE-WHERE-2` —
money-данные только с явной invalidation: короткий TTL (5–30с) + `cache.del` на каждом write + evict перед
критичным чтением. `R-CACHE-WHERE-3` — cache-aside (lazy + evict на write) — дефолт.

`R-CACHE-WHERE-X1` — кеш на write-path (кешировать `createOrder()`; `CacheInterceptor` на POST). `R-CACHE-WHERE-X2` —
кеш **доменного агрегата целиком** (нарушает границы, сложная invalidation) — кешируй read-проекции
(`OrderSummaryDto`), не `Order`. `R-CACHE-WHERE-X3` — money без TTL/invalidation. `R-CACHE-WHERE-X4` — кеш
бизнес-критичного без оценки trade-off. `R-CACHE-WHERE-X5` — кеш результата авторизации/валидации (ABAC каждый
раз; JWK-кеш встроен в `jwks-rsa`, `AUTH-5`).

## 2. Конфигурация (`R-CACHE-CFG-*`)

`R-CACHE-CFG-1` — в проде backend — **Redis** (ioredis через Redis-store cache-manager), не in-memory store
(каждый pod — свой кеш). `R-CACHE-CFG-2` — сериализация — **JSON** (plain DTO через `JSON.stringify`); никакой
бинарной десериализации недоверенных данных (`v8.deserialize`/`eval`-подобное — аналог Java native-сериализации) и
никаких class-инстансов с методами в кеше (после round-trip это plain object). `R-CACHE-CFG-3` — per-cache explicit
TTL: TTL задаётся на каждый именованный кеш из конфига, не один глобальный `ttl` модуля. `R-CACHE-CFG-4` —
настройки через типизированный конфиг (`CacheConfig`, zod/class-validator, `NESTBOOT-4`): host, per-cache TTL,
namespace-префикс. `R-CACHE-CFG-5` — в тестах — Testcontainers Redis (`@testcontainers/redis`) или in-memory store,
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

`R-CACHE-CFG-X1` — бинарная/исполняемая десериализация значений из Redis (security risk). `R-CACHE-CFG-X2` —
in-memory store в multi-instance проде. `R-CACHE-CFG-X3` — один глобальный TTL на все кеши. `R-CACHE-CFG-X4` —
«кеширование» без реального backend (дефолтный память-store вместо Redis, no-op при ошибке подключения —
тихо ничего не кеширует; fail-fast на старте).

## 3. Ключи (`R-CACHE-KEY-*`)

`R-CACHE-KEY-1` — namespace через префикс имени кеша: `user-profiles:42` (cache-manager не префиксует сам — префикс
зашивается в кеш-порт/билдер ключей). `R-CACHE-KEY-2` — имена kebab-case (`user-profiles`, `feature-flags`).
`R-CACHE-KEY-3` — ключ внутри namespace — **explicit** (`` `user-profiles:${userId}` ``), не «весь объект».
`R-CACHE-KEY-4` — кастомная сборка ключа — только для сложных случаев, читаемой функцией-билдером.

`R-CACHE-KEY-X1` — автоключ из всех аргументов метода (ломается при смене сигнатуры); у `CacheInterceptor` дефолтный
ключ = URL — для service-методов ключ всегда явный. `R-CACHE-KEY-X2` — `String(obj)`/`JSON.stringify(obj)` целого
DTO в ключе (`[object Object]` / нестабильный порядок полей). `R-CACHE-KEY-X3` — общий cache на разные entity
(теряется namespacing/метрики). `R-CACHE-KEY-X4` — sensitive (email/phone/токен) в ключе plain-text (виден в
Redis/логах) — хешировать (`createHash('sha256')`).

## 4. TTL (`R-CACHE-TTL-*`)

`R-CACHE-TTL-1` — **каждый кеш — explicit TTL**: `cache.set(key, dto, ttlMs)` всегда с третьим аргументом
(или `@CacheTTL(...)` для interceptor); никаких infinite. `R-CACHE-TTL-2` — типовые по характеру (профиль ~15м,
справочники ~6ч, feature-flags ~60с, money 5–30с). `R-CACHE-TTL-3` — TTL из `CacheConfig`, не хардкод-литерал в
вызове. `R-CACHE-TTL-4` — при естественном invalidation-событии TTL длиннее (инвалидация делает работу); иначе
короткий.

`R-CACHE-TTL-X1` — `cache.set(key, value)` без TTL / `ttl: 0` — «навсегда» (Redis LRU-eviction вне контроля).
`R-CACHE-TTL-X2` — TTL > 24ч для бизнес-данных (переживает деплои, устаревшая структура DTO). `R-CACHE-TTL-X3` —
money без TTL / TTL > 1м без строгой invalidation.

## 5. Invalidation (`R-CACHE-INV-*`)

`R-CACHE-INV-1` — на каждом write-методе того же ресурса — evict затронутых ключей
(`await cache.del('user-profiles:42')`). `R-CACHE-INV-2` — write меняет несколько кешей →
`Promise.all([cache.del(...), cache.del(...)])`. `R-CACHE-INV-3` — при доменных событиях — invalidation как
side-effect: `@OnEvent('user.updated')`-handler (или Kafka-consumer) делает evict — независимо от того, какой use
case вызвал изменение. `R-CACHE-INV-4` — distributed invalidation встроена: общий Redis-backend на все инстансы,
отдельной обвязки не надо.

```ts
// PREFER: точечный evict на write
async updateProfile(cmd: UpdateProfileCommand): Promise<void> {
  await this.repo.update(cmd);
  await this.cache.del(`user-profiles:${cmd.userId}`);
}
// AVOID: await this.cache.reset()  — clear-all, холодный старт → spike на БД
```

`R-CACHE-INV-X1` — `cache.reset()`/`FLUSHDB`/массовое удаление namespace без причины — только для админ-операций.
`R-CACHE-INV-X2` — полагаться только на TTL для money/orders. `R-CACHE-INV-X3` — eventual consistency кеша без
декларации в OpenAPI (`@ApiOperation({ description: 'Возможна задержка до 30 секунд' })`).

## 6. Паттерны (`R-CACHE-PATTERN-*`)

`R-CACHE-PATTERN-1` — **cache-aside** (get → miss → load → `set` с TTL; evict на write) — дефолт.
`R-CACHE-PATTERN-2` — write-through (явный `cache.set` на write вместо evict) — для high read+write одного значения.
`R-CACHE-PATTERN-3` — refresh-ahead: `@Cron`/`@Interval` (`@nestjs/schedule`) перезаливает hot-ключи до истечения TTL.

`R-CACHE-PATTERN-X1` — write-behind (в кеш сейчас, в БД async позже) для money/critical (crash → потеря).
`R-CACHE-PATTERN-X2` — смешение паттернов на одном кеше (непонятная invalidation) — один cache = один паттерн.

## 7. Cache stampede (`R-CACHE-STAMP-*`)

`R-CACHE-STAMP-1` — для одного инстанса — **локальный single-flight**: `Map<string, Promise<T>>` in-flight загрузок —
параллельные вызовы одного ключа ждут один promise. `R-CACHE-STAMP-2` — для Redis (multi-instance) — **distributed
lock**: `redlock` (поверх ioredis) вокруг load-on-miss; локальный single-flight не виден другим процессам.
`R-CACHE-STAMP-3` — для hot-ключей — refresh-ahead (stampede исключён по дизайну).

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

`R-CACHE-STAMP-X1` — игнор stampede для hot-эндпоинтов (>100 RPS, общий miss → DB-инцидент). `R-CACHE-STAMP-X2` —
локальный single-flight/`Map`-lock как защита distributed-кеша (виден одному процессу) — redlock.

## 8. Observability (`R-CACHE-OBS-*`)

`R-CACHE-OBS-1` — метрики hits/misses/evictions через `prom-client` (counters в кеш-порте — cache-manager сам не
экспортирует). `R-CACHE-OBS-2` — **hit rate** = главная; alert при < 70% для долгих кешей. `R-CACHE-OBS-3` —
eviction логировать на DEBUG, не INFO. `R-CACHE-OBS-4` — Redis-side метрики через Redis Exporter.

`R-CACHE-OBS-X1` — отсутствие cache-метрик (SRE не увидит hit rate 5%).

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
