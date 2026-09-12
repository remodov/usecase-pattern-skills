---
name: ucp-caching-review
description: Ревью кеширования Java/Spring (Spring Cache + Redis) по UCP (требования caching/*) — где кешируем, конфигурация и сериализация, ключи и TTL, invalidation, cache-aside, stampede, observability.
when_to_use: Изменения в @Configuration с CacheManager, классах с @Cacheable/@CacheEvict, application.yml с cache-блоком, custom Cache-аспектах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью кеширования

Ты ревьюишь кеширование в Java/Spring-сервисе на соответствие требованиям `caching/*`. Главные точки контроля: где кешируем, конфигурация (Redis + JSON), ключи и TTL, invalidation, паттерны и защита от stampede.

## Зависимости

- **`.claude/docs/backend/caching/spec.md`** — индекс всех правил (полный текст с примерами — `references/<lang>/implementation.md`). Каждое нарушение цитируется кодом из подгрупп: `R-CACHE-WHERE-*` (где), `R-CACHE-CFG-*` (конфигурация), `R-CACHE-KEY-*` (ключи), `R-CACHE-TTL-*` (TTL), `R-CACHE-INV-*` (invalidation), `R-CACHE-PATTERN-*` (паттерны), `R-CACHE-STAMP-*` (stampede), `R-CACHE-OBS-*` (observability).
- Парные документы: `backend/resilience/spec.md` (`resilience/fallback-does-not-fake-success` — fallback из cache), `backend/auth-patterns/spec.md` (`auth-patterns/no-pii-in-logs-and-events` — PII в кеше), `backend/validation/spec.md` (`R-VLD-CFG-*` — `@ConfigurationProperties` для cache-настроек).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/caching/spec.md`. Цитируй конкретные коды (`caching/cache-projections-not-aggregates`, `caching/values-serialized-as-json`).

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на `*CacheConfig*`, `*CacheManager*`, `application*.yml` с `cache:` или `spring.cache.*` блоком.
   - Файлы с `@Cacheable`/`@CacheEvict`/`@CachePut`/`@Caching`.
   - Файлы с `@Scheduled` для refresh-ahead.

3. **Прогон по подгруппам кодов:**
   - **`R-CACHE-WHERE-*`** — `@Cacheable` только на read-методах; не на write; не на доменных агрегатах целиком; money-кеш с короткой TTL и evict; не на JWT/ABAC.
   - **`R-CACHE-CFG-*`** — `RedisCacheManager` (не `ConcurrentMapCacheManager` в проде); `GenericJackson2JsonRedisSerializer` (не JDK); per-cache config с explicit TTL; `@EnableCaching` + явный CacheManager bean; `@ConfigurationProperties` для cache-settings.
   - **`R-CACHE-KEY-*`** — кебаб-case namespace per-cache; `key = "..."` SpEL явно для multi-arg методов; нет общего `shared-cache`; PII/токены не в plain.
   - **`R-CACHE-TTL-*`** — каждый cache имеет explicit TTL; в `application.yml` (не hard-coded); ≤ 24h для бизнес-данных; ≤ 30s для money.
   - **`R-CACHE-INV-*`** — `@CacheEvict` на write-методах; `@Caching` композит для нескольких кешей; `@EventListener + @CacheEvict` для domain-events; не `allEntries=true` без причины; не only-TTL для money.
   - **`R-CACHE-PATTERN-*`** — cache-aside дефолт; `@CachePut` для write-through где нужно; refresh-ahead для hot keys; не write-behind для money; не mix паттернов в одном cache.
   - **`R-CACHE-STAMP-*`** — `sync=true` для local cache; distributed lock (Redisson `RLock`) для Redis hot keys; refresh-ahead через `@Scheduled` для hot.
   - **`R-CACHE-OBS-*`** — Spring Cache metrics включены; alert на hit rate < 70%; eviction в DEBUG, не INFO.

4. **Ищи паттерны-нарушения:**
   - `@Cacheable` на методе с именем `create*`/`save*`/`update*` — `caching/no-cache-on-write-path`.
   - `@Cacheable` на repository-методе, возвращающем full Aggregate (`Order` с `List<OrderItem>` + `Payment` + `Shipment`) — `caching/cache-projections-not-aggregates`.
   - `JdkSerializationRedisSerializer` или `RedisSerializer.java()` в коде — `caching/values-serialized-as-json`.
   - В прод-конфиге явное `new ConcurrentMapCacheManager(...)` или дефолтное `simple` cache type — `caching/distributed-cache-in-production`.
   - `@EnableCaching` в `@Configuration` без `@Bean CacheManager`-метода в том же или родительском контексте — `caching/no-cache-without-manager` (silent NoOp).
   - `RedisCacheManager.builder()` без `withInitialCacheConfigurations(perCache)` или с одним `cacheDefaults(...)` для всего — `caching/explicit-ttl-per-cache`.
   - `@Cacheable(cacheNames = "X")` без `key`-параметра при наличии 2+ параметров метода — `caching/explicit-cache-key`.
   - `@Cacheable` на методе с DTO-параметром без custom `equals/hashCode` — risk `caching/explicit-cache-key`.
   - `cacheNames = "shared-cache"` в нескольких местах — `caching/cache-name-is-namespace`.
   - `key = "#email"` или `key = "#token"` для PII — `caching/no-sensitive-data-in-keys`.
   - `RedisCacheConfiguration.defaultCacheConfig()` без `entryTtl(...)` — `caching/explicit-ttl-per-cache` (default = no TTL = forever).
   - В `application.yml` `entry-ttl: 24h+` или больше для не-static данных — `caching/ttl-matches-data-nature`.
   - `@Cacheable` на методе вида `getBalance(...)` / `getCredit(...)` без TTL ≤ 30s или без `@CacheEvict` на write-партнёре — `caching/money-data-needs-explicit-invalidation`.
   - `@CacheEvict(allEntries = true)` в обычном write-методе (не админский truncate) — `caching/no-routine-full-flush`.
   - В Resilience-fallback `cache.put(...)` для money без `@CacheEvict` соседнего метода — `caching/ttl-is-not-consistency`.
   - `CompletableFuture.runAsync(... cache.put(...))` без `@Transactional` consistency — write-behind для money риск `caching/cache-aside-is-default`.
   - `@Cacheable(sync = true)` на Redis-cache (sync синхронизирует JVM, не Redis) — `caching/stampede-protection` для distributed.
   - `synchronized`-блок вокруг cache-fetch в multi-instance app — `caching/stampede-protection`.
   - `management.metrics.enable.cache: false` или подобное disable — `caching/cache-metrics-enabled`.

5. **При ревью `application.yml`:**
   - `spring.cache.type: redis` (не `simple`).
   - `cache.caches.<name>.ttl: <duration>` для каждого именованного cache.
   - `spring.redis.host`/`port` или `spring.data.redis.url` валидны (но это `R-VLD-CFG`-зона).
   - `management.endpoints.web.exposure.include` содержит `caches` actuator endpoint (для observability).

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). В качестве `<КодПравила>` — конкретный код.

7. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично:**
     - `JdkSerializationRedisSerializer` — security CVE.
     - `@Cacheable` на доменном агрегате целиком — нарушение границ.
     - Money-кеш без TTL/evict — двойные списания / stale balance.
     - `ConcurrentMapCacheManager` в multi-instance проде — inconsistent reads между pods.
     - `@EnableCaching` без CacheManager-бина — silent NoOp, кеш не работает.
   - **Предупреждение:**
     - Дефолтный keyGenerator на multi-arg — фрагильный к рефакторингу.
     - Один TTL на все кеши — типичная неоптимальность.
     - `@CacheEvict(allEntries=true)` без причины.
     - PII в plain-text ключе.
   - **Замечание:**
     - Неинформативные имена кешей (`cache1`, `temp`).
     - Отсутствие cache hit rate alerts.

## Что не входит

- HTTP-cache (`Cache-Control` headers) — `ucp-api-review` (REST API).
- JWT JWK кеш Spring Security — `ucp-auth-review` (`auth-patterns/token-validated-by-library`).
- DB query plan cache — `ucp-pg-runtime-review`.
- Resilience cache-as-fallback (`resilience/fallback-does-not-fake-success`) — `ucp-resilience-review`.
- @ConfigurationProperties валидация — `ucp-validation-review` (`R-VLD-CFG-*`).

$ARGUMENTS
