---
name: ucp-node-caching-design
lang: node
description: Спроектировать кеширование в NestJS-сервисе (требования caching/*) — @nestjs/cache-manager + ioredis, cache-aside через кеш-порт в core/, кеш read-проекций, JSON-значения, per-cache TTL из конфига, evict на write, single-flight/redlock от stampede.
when_to_use: Добавление кеша. Триггеры — «закешируй X», «redis-кеш для Y», «cache-aside на NestJS».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Caching — проектирование (Node / @nestjs/cache-manager + ioredis)

Ты проектируешь кеширование по **контракту** `backend/caching/spec.md` (`R-CACHE-*`) и **Node-реализации** `backend/caching/references/node/implementation.md`.

## Инструкции

1. **Прочитай** требования `node-style/*`. Коды в обосновании, не в коде. Связанные: `cqrs` (кеш read-проекций), `backend/hexagonal/node/...` (кеш-порт в core/, реализация в `adapters/out/cache/`), `observability` (hit-rate метрика), `auth-patterns` (`auth-patterns/token-validated-by-library` — JWK-кеш встроен в `jwks-rsa`).

2. **Где** (`R-CACHE-WHERE-*`): кешируй read-heavy + редко меняющиеся read-проекции (`OrderSummaryDto`), не агрегаты, не write-path, не результат авторизации. Money — только с коротким TTL (5–30с) + явной invalidation. `CacheInterceptor`/`@CacheTTL` — только для простых HTTP-GET-кешей; остальное — явный cache-aside через порт.

3. **Backend/конфиг** (`R-CACHE-CFG-*`): в проде — Redis (ioredis-store через `CacheModule.registerAsync` с фабрикой от `CacheConfig`), не дефолтный in-memory store; значения — plain-JSON DTO (никакой бинарной десериализации и class-инстансов с методами); per-cache explicit TTL из типизированного `CacheConfig` (`nest-bootstrap/config-validated-at-startup`); fail-fast без backend; тесты — Testcontainers Redis (`@testcontainers/redis`), не мок порта.

4. **Ключи** (`R-CACHE-KEY-*`): namespace-префикс зашит в кеш-порт/билдер (`user-profiles:42`), kebab-case, explicit; sensitive — хешировать (`createHash('sha256')`).

5. **TTL/Invalidation** (`R-CACHE-TTL/INV-*`): каждый `cache.set(key, dto, ttlMs)` — с explicit TTL ≤ 24ч из конфига; `cache.del` на write того же ресурса и в `@OnEvent`-handler'ах (несколько — `Promise.all`); eventual consistency задекларируй в `@ApiOperation`; нет `cache.reset()` без причины.

6. **Паттерн/Stampede** (`R-CACHE-PATTERN/STAMP-*`): cache-aside дефолт (один паттерн на кеш); для одного инстанса — single-flight (`Map<string, Promise<T>>`), для multi-instance — `redlock` поверх ioredis; hot-ключи — refresh-ahead через `@Cron` (`@nestjs/schedule`); нет write-behind для money.

7. **Observability** (`R-CACHE-OBS-*`): hits/misses/evictions через `prom-client`-counters в кеш-порте; hit-rate alert. Самопроверка (§9) + предложи `ucp-node-caching-review`.

## Антипаттерны, которые НЕ генерировать

- Кеш агрегата целиком (`caching/cache-projections-not-aggregates`); кеш на write-path (`caching/no-cache-on-write-path`); кеш авторизации (`caching/no-caching-authorization-results`); money без TTL (`caching/money-data-needs-explicit-invalidation`).
- Бинарная/исполняемая десериализация значений из Redis (`caching/values-serialized-as-json`); `CacheModule.register()` с дефолтным in-memory store в multi-instance проде (`R-CACHE-CFG-X2/X4`); один глобальный TTL (`caching/explicit-ttl-per-cache`).
- Автоключ `CacheInterceptor` (URL) для service-методов / `JSON.stringify(obj)` целого DTO в ключе (`R-CACHE-KEY-X1/X2`); sensitive в ключе plain-text (`caching/no-sensitive-data-in-keys`); infinite TTL (`caching/explicit-ttl-per-cache`); TTL > 24ч (`caching/ttl-matches-data-nature`).
- Evict-all без причины (`caching/no-routine-full-flush`); write-behind для money (`caching/cache-aside-is-default`); локальный single-flight/`Map`-lock как защита distributed-кеша (`caching/stampede-protection`).

После работы скилла — обязательно `ucp-node-caching-review`.

$ARGUMENTS
