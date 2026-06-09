# Caching Style Guide

Свод правил кеширования в Java/Spring-сервисах команды UCP: что кешируем (что НЕ кешируем — чаще), Spring Cache + Redis конфигурация, key/TTL/invalidation, cache-aside vs write-through, защита от cache stampede, observability. Каждое правило идентифицируется кодом (`R-CACHE-WHERE-1`, `R-CACHE-INV-X1`) — скилл `ucp-caching-review` цитирует эти коды в findings.

Гайд опирается на [Spring Cache abstraction](https://docs.spring.io/spring-framework/reference/integration/cache.html) с Redis backend через `spring-boot-starter-data-redis`. ConcurrentMapCacheManager (in-memory) — допустим только в тестах. Не покрывает: кеш на стороне клиента (HTTP `Cache-Control` — это `R-RES-FB-1`/REST), database-level query plan cache (это PG-side), CDN.

Связанные стандарты:
- `R-RES-FB-1` (Resilience) — fallback может отдавать cached read при отказе внешней системы.
- `AUTH-16` (Auth) — PII в кеше требует отдельной политики (TTL, encryption at rest).
- `R-JOOQ-MS-3` (jOOQ) — кеш не отменяет multiset для eager-fetch, это разные слои защиты.
- `R-VLD-CFG-*` (Validation) — `@ConfigurationProperties` для cache-настроек обязательно `@Validated`.

---

## Содержание

1. [Где кешируем — `R-CACHE-WHERE-*`](#1-где-кешируем)
2. [Конфигурация — `R-CACHE-CFG-*`](#2-конфигурация)
3. [Ключи — `R-CACHE-KEY-*`](#3-ключи)
4. [TTL — `R-CACHE-TTL-*`](#4-ttl)
5. [Invalidation — `R-CACHE-INV-*`](#5-invalidation)
6. [Паттерны — `R-CACHE-PATTERN-*`](#6-паттерны)
7. [Cache stampede — `R-CACHE-STAMP-*`](#7-cache-stampede)
8. [Observability — `R-CACHE-OBS-*`](#8-observability)
9. [Антипаттерны — сводка `R-CACHE-*-X*`](#9-антипаттерны)

---

## 1. Где кешируем

Кеширование — оптимизация. Без неё сервис должен работать корректно. Если кеш «обязателен для корректности» — это бизнес-данные, не кеш.

### 1.1 Обязательно

- **R-CACHE-WHERE-1.** Кешируй **read-heavy + редко меняющиеся** данные:
  - Справочники (страны, валюты, тарифы) — TTL минут/часы.
  - User profile / settings — TTL 5–15 минут.
  - Конфигурация feature-flags — TTL 30–60 секунд.
  - Результаты тяжёлых вычислений (агрегации, отчёты) — TTL по бизнес-смыслу.

- **R-CACHE-WHERE-2.** Кеш **денежных данных** (баланс, лимиты, available credit) допустим, но только с **явной invalidation strategy**: TTL коротким (5–30 секунд), `@CacheEvict` на каждом write-методе того же ресурса, для критичных операций — `cache.evict()` перед чтением.

- **R-CACHE-WHERE-3.** Cache-aside (lazy load) — дефолтный паттерн для большинства случаев. Read проходит через `@Cacheable`, write делает `@CacheEvict` или явный `cache.evict()`.

### 1.2 Запрещено

- **R-CACHE-WHERE-X1.** **Кеш на write-path.** `@Cacheable` на `createOrder()`, `confirmPayment()` — нонсенс, write-операции не возвращают «то же значение для тех же входов».

- **R-CACHE-WHERE-X2.** **Кеширование доменного агрегата целиком.** `@Cacheable` на `OrderRepository.findById(id)` → `Order` aggregate с `List<OrderItem>` + `Payment` + `Shipment`. Нарушает границы агрегата (агрегат сам управляет своей целостностью), агрегат может содержать sensitive-данные, и invalidation становится сложной (любой child-update должен evict-ить parent). Кешируй **read-проекции** (`OrderSummary`), не агрегаты.

- **R-CACHE-WHERE-X3.** **Money-данные без TTL и invalidation.** Кешировать баланс пользователя на 1 час = «потратил, но баланс показывает старый» — рекламация и инцидент.

- **R-CACHE-WHERE-X4.** Кеш **бизнес-критичных** данных только для performance-оптимизации, без явной trade-off оценки. Stale-data для money / orders = inconsistent UX.

- **R-CACHE-WHERE-X5.** Кеш **результата валидации / авторизации**. JWT-валидация имеет встроенный JWK кеш (5 минут, см. `AUTH-5`); ABAC-проверки делаются каждый раз — кеш авторизации = security risk при изменении roles.

---

## 2. Конфигурация

### 2.1 Обязательно

- **R-CACHE-CFG-1.** В прод-сервисах cache backend — **Redis**, не in-memory `ConcurrentMapCacheManager`. Причины:
  - Multi-instance deployment — каждый pod имел бы свой локальный кеш, плюс свои eviction-стратегии → inconsistent reads, лишние invalidation race-conditions.
  - Persistence (опционально) — Redis может пережить рестарт.
  - Observability — Redis-side metrics + cluster mode.

  Spring-конфиг:
  ```java
  @Configuration
  @EnableCaching
  public class CacheConfig {

      @Bean
      RedisCacheManager cacheManager(RedisConnectionFactory cf, ObjectMapper mapper) {
          var config = RedisCacheConfiguration.defaultCacheConfig()
              .serializeValuesWith(SerializationPair.fromSerializer(
                  new GenericJackson2JsonRedisSerializer(mapper)))
              .entryTtl(Duration.ofMinutes(15))      // дефолт; per-cache переопределяется
              .disableCachingNullValues();

          var perCache = Map.of(
              "user-profiles", config.entryTtl(Duration.ofMinutes(15)),
              "currencies", config.entryTtl(Duration.ofHours(6)),
              "feature-flags", config.entryTtl(Duration.ofSeconds(60))
          );

          return RedisCacheManager.builder(cf)
              .cacheDefaults(config)
              .withInitialCacheConfigurations(perCache)
              .build();
      }
  }
  ```

- **R-CACHE-CFG-2.** Сериализация значений — **JSON** (`GenericJackson2JsonRedisSerializer`), **никогда** Java native (`JdkSerializationRedisSerializer`). Причины:
  - **Security:** Java deserialization = известный класс vulnerability (CVE-2015-7501 family).
  - Читаемость: JSON в Redis viewable через `redis-cli get`; binary blob — нет.
  - Forward-compat: добавление поля в DTO не ломает старый кеш сразу (Jackson игнорирует unknown).

- **R-CACHE-CFG-3.** **Per-cache configuration** — каждый именованный кеш имеет explicit TTL. Не полагайся на default-конфиг для всех кешей; разные данные требуют разного TTL.

- **R-CACHE-CFG-4.** Cache settings — через `@ConfigurationProperties` (см. `R-VLD-CFG-1`):
  ```java
  @ConfigurationProperties("cache")
  @Validated
  public record CacheSettings(
      @Valid @NotEmpty Map<String, CacheConfig> caches
  ) {
      public record CacheConfig(
          @NotNull Duration ttl,
          boolean disableNullValues
      ) {}
  }
  ```
  В `application.yml`:
  ```yaml
  cache:
    caches:
      user-profiles:
        ttl: 15m
        disable-null-values: true
      currencies:
        ttl: 6h
  ```

- **R-CACHE-CFG-5.** В тестах — `ConcurrentMapCacheManager` либо `Testcontainers` Redis. Не моки `Cache`-интерфейса (теряется поведение TTL/eviction).

### 2.2 Запрещено

- **R-CACHE-CFG-X1.** `JdkSerializationRedisSerializer` — security risk, см. `R-CACHE-CFG-2`.

- **R-CACHE-CFG-X2.** `ConcurrentMapCacheManager` (Spring default `simple`) в multi-instance проде. Каждый pod = свой кеш, нет консистентности.

- **R-CACHE-CFG-X3.** Один глобальный TTL для всех кешей. Профиль (15 мин) и валюты (6 часов) и feature-flags (60 сек) не должны делить настройку.

- **R-CACHE-CFG-X4.** `@EnableCaching` без CacheManager-бина. Spring создаст `NoOpCacheManager`, `@Cacheable` молча ничего не кеширует — silent skip.

---

## 3. Ключи

### 3.1 Обязательно

- **R-CACHE-KEY-1.** **Namespace через имя кеша:** `cacheNames = "user-profiles"` — Spring сам префиксует (Redis key: `user-profiles::42`). Префикс отделяет кеши в Redis, упрощает evict-by-namespace.

- **R-CACHE-KEY-2.** Имена cache (slug-style, kebab-case): `user-profiles`, `payment-methods`, `feature-flags`. Не camelCase, не PascalCase.

- **R-CACHE-KEY-3.** Ключ внутри cache — через SpEL **explicit**:
  ```java
  @Cacheable(cacheNames = "user-profiles", key = "#userId")
  public UserProfile findProfile(Long userId) { ... }

  @Cacheable(cacheNames = "orders-by-customer", key = "#customerId + ':' + #status")
  public List<OrderSummary> findByCustomerAndStatus(Long customerId, OrderStatus status) { ... }
  ```
  Composite-ключи через `+ ':' +` — простой и читаемый формат.

- **R-CACHE-KEY-4.** Custom `KeyGenerator` — только для **очень сложных** ключей (где SpEL нечитаем). Реализация:
  ```java
  @Component("complexKeyGenerator")
  public class ComplexKeyGenerator implements KeyGenerator {
      @Override
      public Object generate(Object target, Method method, Object... params) {
          // явная логика
      }
  }
  ```
  Использование: `@Cacheable(keyGenerator = "complexKeyGenerator")`.

### 3.2 Запрещено

- **R-CACHE-KEY-X1.** Дефолтный generator (без `key`-параметра) для методов с **несколькими параметрами**. Spring сериализует все аргументы через `SimpleKey` — выглядит как `[arg1, arg2]`, легко ломается при изменении сигнатуры. Указывай `key = "..."` явно.

- **R-CACHE-KEY-X2.** `Object.toString()` или подобное в ключе. Если параметр — DTO с `Object.toString()` дефолтным (`UserProfile@1a2b3c`) — каждый вызов = новый ключ.

- **R-CACHE-KEY-X3.** Один общий cache для разных entity (`cacheNames = "shared-cache"`). Теряется namespacing, evict пересекается, метрики нечитаемы.

- **R-CACHE-KEY-X4.** Encoding sensitive данных в ключе (email, phone, токены) plain-text. Redis-keys видны в logs, monitoring tools. Hash значение (`Hashing.sha256().hashString(email)`) если ключ обязан содержать.

---

## 4. TTL

### 4.1 Обязательно

- **R-CACHE-TTL-1.** **Каждый cache имеет explicit TTL.** Никаких infinite-кешей.

- **R-CACHE-TTL-2.** Типовые значения по характеру данных:

  | Тип данных | TTL | Пример |
  |---|---|---|
  | Static reference | hours | currencies, countries, timezones |
  | User profile / preferences | 15–30 min | UserProfile, UserSettings |
  | Feature flags | 30–60 sec | FeatureFlagSet |
  | Configuration overrides | 60 sec | TenantConfig |
  | Heavy aggregations | 5–10 min | DailyReport |
  | Money-related | 5–30 sec | UserBalance (с явной evict-стратегией) |
  | OAuth/JWT keys | 5 min (default) | JWK Set (см. `AUTH-5`) |

- **R-CACHE-TTL-3.** TTL — через `application.yml`, не hard-coded в Java. Это позволяет SRE/admin поднимать/понижать TTL под нагрузку без redeploy.

- **R-CACHE-TTL-4.** Если cached data имеет **естественный invalidation event** (например `orderConfirmed` → invalidate `OrderSummary`) — TTL longer, invalidation does the heavy lifting. Если invalidation не реализуема — TTL коротким (compromise).

### 4.2 Запрещено

- **R-CACHE-TTL-X1.** Cache с TTL = `Duration.ZERO` или infinite. ZERO — Spring трактует как «no TTL» = forever. Forever в Redis при достижении max-memory приведёт к eviction по LRU/LFU без вашего контроля.

- **R-CACHE-TTL-X2.** TTL **больше 24 часов** для бизнес-данных. Сервис рестартует чаще раза в сутки (deploy), и долгий TTL переживает релизы — могут быть закешированные значения с устаревшей структурой DTO.

- **R-CACHE-TTL-X3.** Money-кеш **без TTL** или TTL > 1 минута без strict invalidation. См. `R-CACHE-WHERE-X3`.

---

## 5. Invalidation

### 5.1 Обязательно

- **R-CACHE-INV-1.** На каждом **write-методе** того же агрегата — `@CacheEvict` на затронутые кеши:
  ```java
  @CacheEvict(cacheNames = "user-profiles", key = "#userId")
  public void updateProfile(Long userId, ProfileUpdate update) { ... }
  ```

- **R-CACHE-INV-2.** Если write меняет **несколько кешей** — `@Caching` композит:
  ```java
  @Caching(evict = {
      @CacheEvict(cacheNames = "user-profiles", key = "#userId"),
      @CacheEvict(cacheNames = "user-permissions", key = "#userId")
  })
  public void updateProfile(Long userId, ProfileUpdate update) { ... }
  ```

- **R-CACHE-INV-3.** При **доменных событиях** (`UserUpdatedEvent`) — invalidation через `@EventListener`:
  ```java
  @EventListener
  @CacheEvict(cacheNames = "user-profiles", key = "#event.userId()")
  public void onUserUpdated(UserUpdatedEvent event) { /* пустой метод */ }
  ```
  Это паттерн «invalidation as side-effect of domain event», независимый от того, какой именно use case вызвал изменение.

- **R-CACHE-INV-4.** Для **distributed cache invalidation** (Redis pub/sub при изменении на одной из инстансов) — встроенно в Redis backend, отдельной обвязки не нужно.

### 5.2 Запрещено

- **R-CACHE-INV-X1.** **`@CacheEvict(allEntries = true)`** без причины. Сбрасывает весь cache одной операцией — на холодном старте остальные пользователи получают cache miss → нагрузка на БД спайком. Допустимо только при админских операциях (truncate / rebuild).

- **R-CACHE-INV-X2.** Полагаться только на TTL для consistency. «Подождёт минуту и обновится» — приемлемо для еволюционирующих feature-flags, неприемлемо для money / orders.

- **R-CACHE-INV-X3.** **Eventual consistency без явной декларации.** Если кеш может быть stale — это часть контракта endpoint, документируй в OpenAPI (`description: 'Возможна задержка до 30 секунд'`).

---

## 6. Паттерны

### 6.1 Обязательно

- **R-CACHE-PATTERN-1.** **Cache-aside (lazy load + write evict)** — дефолтный паттерн.
  - Read: `@Cacheable` — first miss идёт в БД, кладёт в кеш; следующие reads — из кеша.
  - Write: `@CacheEvict` сбрасывает значение; следующий read load-нет свежее.
  - **Преимущества:** простой, читаем; кеш отстаёт от БД на TTL (acceptable для большинства).

- **R-CACHE-PATTERN-2.** **Cache-through (write-through)** — для высокочастотных read + write одного значения. На write кеш обновляется явно (`cache.put(...)`), не evict-ится:
  ```java
  @CachePut(cacheNames = "user-profiles", key = "#userId")
  public UserProfile updateProfile(Long userId, ProfileUpdate update) {
      // вернёт обновлённый, попадёт в кеш
  }
  ```
  Используй когда: данные сразу нужны после write (тот же flow продолжает работать с ними).

- **R-CACHE-PATTERN-3.** **Refresh-ahead** — для критичных hot-данных (главная страница, top-100 продуктов). Реализуется через `@Scheduled` job, который перезаливает cache до истечения TTL:
  ```java
  @Scheduled(fixedDelay = 30_000)
  public void refreshTopProducts() {
      var top = productRepository.findTop100();
      cacheManager.getCache("top-products").put("global", top);
  }
  ```
  Гарантирует «no cache miss for hot keys».

### 6.2 Запрещено

- **R-CACHE-PATTERN-X1.** **Write-behind** (write в кеш, async в БД позже) для money/critical-данных. Crash сервиса до flush в БД = потеря данных.

- **R-CACHE-PATTERN-X2.** Mix паттернов на одном cache. Если cache `user-profiles` использует cache-aside в одном методе и write-through в другом — invalidation logic становится непонятной. Один cache = один паттерн.

---

## 7. Cache stampede

Cache stampede (thundering herd) — multiple parallel requests на одну и ту же холодную ключ. Все думают «cache miss → fetch from DB», DB получает N одинаковых запросов. Под нагрузкой = инцидент.

### 7.1 Обязательно

- **R-CACHE-STAMP-1.** Для **локального кеша** (`ConcurrentMapCacheManager`) — `sync = true`:
  ```java
  @Cacheable(cacheNames = "currencies", sync = true)
  public List<Currency> findAll() { ... }
  ```
  Spring блокирует все параллельные вызовы на одном ключе до завершения первого.

- **R-CACHE-STAMP-2.** Для **distributed cache** (Redis) — `sync = true` не помогает (lock только within JVM). Опции:
  - **Distributed lock** через Redis `SET NX EX` или [Redisson](https://github.com/redisson/redisson) `RLock`:
    ```java
    var lock = redisson.getLock("user-profiles:" + userId + ":lock");
    if (lock.tryLock(100, 30, TimeUnit.MILLISECONDS)) {
        try {
            // double-check cache
            // load from DB, put to cache
        } finally {
            lock.unlock();
        }
    }
    ```
  - **Probabilistic refresh** — обновляй cache **до** истечения TTL с probability возрастающей по мере приближения к expiry. Уменьшает синхронные cache miss.

- **R-CACHE-STAMP-3.** Для **hot keys** (top-products) — `Refresh-ahead` (см. `R-CACHE-PATTERN-3`) — фоновое обновление cache до expiry. Stampede исключён по дизайну.

### 7.2 Запрещено

- **R-CACHE-STAMP-X1.** Игнорировать stampede для hot endpoints. Под рассчитываемой нагрузкой (>100 RPS на endpoint) cache miss всех вместе = DB latency-инцидент.

- **R-CACHE-STAMP-X2.** Использовать `synchronized`-блок в Java для distributed-cache защиты. JVM-lock не виден другим инстансам.

---

## 8. Observability

### 8.1 Обязательно

- **R-CACHE-OBS-1.** Spring Cache + Redis автоматически экспортирует через Micrometer (`spring-boot-starter-actuator`):
  - `cache_gets_total{cache,result=hit|miss}`
  - `cache_puts_total{cache}`
  - `cache_evictions_total{cache}`
  - `cache_size{cache}` (для bounded caches)

- **R-CACHE-OBS-2.** **Cache hit rate** — основная метрика здоровья кеша. Расчёт: `hits / (hits + misses)`. Алерт при **hit rate < 70%** для долго существующих кешей — означает либо неподходящий TTL, либо слишком частые invalidation.

- **R-CACHE-OBS-3.** Логировать **eviction** (`@CacheEvict`) на уровне DEBUG с key. Не INFO/WARN — будет шумно.

- **R-CACHE-OBS-4.** Redis-side метрики: `redis_cluster_state`, `redis_memory_used_bytes`, `redis_keys_total{db}` — мониторятся отдельно (Redis Exporter для Prometheus).

### 8.2 Запрещено

- **R-CACHE-OBS-X1.** Отключение Spring Cache metrics (`management.metrics.enable.cache=false`). Без них SRE не увидит «у нас hit rate 5%, кеш бесполезен».

---

## 9. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Кеш на write-методе | `R-CACHE-WHERE-X1` | только read, write — `@CacheEvict` |
| Кеш доменного агрегата целиком | `R-CACHE-WHERE-X2` | read-проекции (`OrderSummary`) |
| Money-кеш без TTL/invalidation | `R-CACHE-WHERE-X3`, `R-CACHE-TTL-X3` | TTL ≤ 30s + явный evict |
| Кеш JWT/ABAC-валидации | `R-CACHE-WHERE-X5` | JWK уже встроен (`AUTH-5`); ABAC — каждый раз |
| `JdkSerializationRedisSerializer` | `R-CACHE-CFG-X1` | `GenericJackson2JsonRedisSerializer` |
| `ConcurrentMapCacheManager` в multi-instance проде | `R-CACHE-CFG-X2` | RedisCacheManager |
| Один TTL на все кеши | `R-CACHE-CFG-X3` | per-cache config |
| `@EnableCaching` без CacheManager-бина | `R-CACHE-CFG-X4` | явно сконфигурированный bean |
| Дефолтный keyGenerator на multi-arg методе | `R-CACHE-KEY-X1` | `key = "..."` SpEL явно |
| `Object.toString()` в ключе | `R-CACHE-KEY-X2` | bean ID или primitive |
| Один общий cache `shared-cache` | `R-CACHE-KEY-X3` | per-entity |
| PII / токены plain в ключе | `R-CACHE-KEY-X4` | hash или ID-replacement |
| TTL = 0 / infinite | `R-CACHE-TTL-X1` | explicit duration |
| TTL > 24h для бизнес-данных | `R-CACHE-TTL-X2` | разумные интервалы |
| `@CacheEvict(allEntries=true)` без причины | `R-CACHE-INV-X1` | по конкретному ключу |
| Полагаться только на TTL для money-consistency | `R-CACHE-INV-X2` | явный `@CacheEvict` на write |
| Eventual consistency без декларации | `R-CACHE-INV-X3` | в OpenAPI `description` |
| Write-behind для money | `R-CACHE-PATTERN-X1` | write-through или cache-aside |
| Mix паттернов на одном cache | `R-CACHE-PATTERN-X2` | один cache = один паттерн |
| Игнорировать stampede на hot endpoints | `R-CACHE-STAMP-X1` | distributed lock или refresh-ahead |
| `synchronized` для distributed-cache защиты | `R-CACHE-STAMP-X2` | Redis lock |
| Отключение cache metrics | `R-CACHE-OBS-X1` | оставить включёнными |

Финальная сводка: правил «Обязательно» — около 20, «Запрещено» — около 18.
