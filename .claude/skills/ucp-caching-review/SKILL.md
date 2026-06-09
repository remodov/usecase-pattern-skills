---
name: ucp-caching-review
description: Ревью кеширования Java/Spring (Spring Cache + Redis) по UCP (коды R-CACHE-*) — где кешируем, конфигурация и сериализация, ключи и TTL, invalidation, cache-aside, stampede, observability.
when_to_use: Изменения в @Configuration с CacheManager, классах с @Cacheable/@CacheEvict, application.yml с cache-блоком, custom Cache-аспектах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью кеширования

Ты ревьюишь кеширование в Java/Spring-сервисе на соответствие Caching Style Guide. Главные точки контроля: где кешируем, конфигурация (Redis + JSON), ключи и TTL, invalidation, паттерны и защита от stampede.

## Зависимости

- **`.claude/docs/backend/caching/caching-rules.md`** — индекс всех правил (полный текст с примерами — соответствующий `*-style-guide.md`). Каждое нарушение цитируется кодом из подгрупп: `R-CACHE-WHERE-*` (где), `R-CACHE-CFG-*` (конфигурация), `R-CACHE-KEY-*` (ключи), `R-CACHE-TTL-*` (TTL), `R-CACHE-INV-*` (invalidation), `R-CACHE-PATTERN-*` (паттерны), `R-CACHE-STAMP-*` (stampede), `R-CACHE-OBS-*` (observability).
- Парные документы: `backend/resilience/resilience-rules.md` (`R-RES-FB-1` — fallback из cache), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-16` — PII в кеше), `backend/validation/validation-rules.md` (`R-VLD-CFG-*` — `@ConfigurationProperties` для cache-настроек).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/caching/caching-rules.md`. Цитируй конкретные коды (`R-CACHE-WHERE-X2`, `R-CACHE-CFG-X1`).

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
   - `@Cacheable` на методе с именем `create*`/`save*`/`update*` — `R-CACHE-WHERE-X1`.
   - `@Cacheable` на repository-методе, возвращающем full Aggregate (`Order` с `List<OrderItem>` + `Payment` + `Shipment`) — `R-CACHE-WHERE-X2`.
   - `JdkSerializationRedisSerializer` или `RedisSerializer.java()` в коде — `R-CACHE-CFG-X1`.
   - В прод-конфиге явное `new ConcurrentMapCacheManager(...)` или дефолтное `simple` cache type — `R-CACHE-CFG-X2`.
   - `@EnableCaching` в `@Configuration` без `@Bean CacheManager`-метода в том же или родительском контексте — `R-CACHE-CFG-X4` (silent NoOp).
   - `RedisCacheManager.builder()` без `withInitialCacheConfigurations(perCache)` или с одним `cacheDefaults(...)` для всего — `R-CACHE-CFG-X3`.
   - `@Cacheable(cacheNames = "X")` без `key`-параметра при наличии 2+ параметров метода — `R-CACHE-KEY-X1`.
   - `@Cacheable` на методе с DTO-параметром без custom `equals/hashCode` — risk `R-CACHE-KEY-X2`.
   - `cacheNames = "shared-cache"` в нескольких местах — `R-CACHE-KEY-X3`.
   - `key = "#email"` или `key = "#token"` для PII — `R-CACHE-KEY-X4`.
   - `RedisCacheConfiguration.defaultCacheConfig()` без `entryTtl(...)` — `R-CACHE-TTL-X1` (default = no TTL = forever).
   - В `application.yml` `entry-ttl: 24h+` или больше для не-static данных — `R-CACHE-TTL-X2`.
   - `@Cacheable` на методе вида `getBalance(...)` / `getCredit(...)` без TTL ≤ 30s или без `@CacheEvict` на write-партнёре — `R-CACHE-WHERE-X3`.
   - `@CacheEvict(allEntries = true)` в обычном write-методе (не админский truncate) — `R-CACHE-INV-X1`.
   - В Resilience-fallback `cache.put(...)` для money без `@CacheEvict` соседнего метода — `R-CACHE-INV-X2`.
   - `CompletableFuture.runAsync(... cache.put(...))` без `@Transactional` consistency — write-behind для money риск `R-CACHE-PATTERN-X1`.
   - `@Cacheable(sync = true)` на Redis-cache (sync синхронизирует JVM, не Redis) — `R-CACHE-STAMP-X2` для distributed.
   - `synchronized`-блок вокруг cache-fetch в multi-instance app — `R-CACHE-STAMP-X2`.
   - `management.metrics.enable.cache: false` или подобное disable — `R-CACHE-OBS-X1`.

5. **При ревью `application.yml`:**
   - `spring.cache.type: redis` (не `simple`).
   - `cache.caches.<name>.ttl: <duration>` для каждого именованного cache.
   - `spring.redis.host`/`port` или `spring.data.redis.url` валидны (но это `R-VLD-CFG`-зона).
   - `management.endpoints.web.exposure.include` содержит `caches` actuator endpoint (для observability).

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-finding-format.md` (`RFF-1`..`RFF-16`). В качестве `<КодПравила>` — конкретный код.

7. **Доменные ориентиры серьёзности** (`RFF-12`):
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
- JWT JWK кеш Spring Security — `ucp-auth-review` (`AUTH-5`).
- DB query plan cache — `ucp-pg-runtime-review`.
- Resilience cache-as-fallback (`R-RES-FB-1`) — `ucp-resilience-review`.
- @ConfigurationProperties валидация — `ucp-validation-review` (`R-VLD-CFG-*`).

$ARGUMENTS
