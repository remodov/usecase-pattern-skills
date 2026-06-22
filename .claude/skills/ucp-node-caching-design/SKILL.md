---
name: ucp-node-caching-design
lang: node
description: Спроектировать кеширование в NestJS-сервисе (коды R-CACHE-*) — @nestjs/cache-manager + ioredis, cache-aside через кеш-порт в core/, кеш read-проекций, JSON-значения, per-cache TTL из конфига, evict на write, single-flight/redlock от stampede.
when_to_use: Добавление кеша. Триггеры — «закешируй X», «redis-кеш для Y», «cache-aside на NestJS».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Caching — проектирование (Node / @nestjs/cache-manager + ioredis)

Ты проектируешь кеширование по **контракту** `backend/caching/caching-rules.md` (`R-CACHE-*`) и **Node-реализации** `backend/caching/node/caching-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `cqrs` (кеш read-проекций), `backend/hexagonal/node/...` (кеш-порт в core/, реализация в `adapters/out/cache/`), `observability` (hit-rate метрика), `auth-patterns` (`AUTH-5` — JWK-кеш встроен в `jwks-rsa`).

2. **Где** (`R-CACHE-WHERE-*`): кешируй read-heavy + редко меняющиеся read-проекции (`OrderSummaryDto`), не агрегаты, не write-path, не результат авторизации. Money — только с коротким TTL (5–30с) + явной invalidation. `CacheInterceptor`/`@CacheTTL` — только для простых HTTP-GET-кешей; остальное — явный cache-aside через порт.

3. **Backend/конфиг** (`R-CACHE-CFG-*`): в проде — Redis (ioredis-store через `CacheModule.registerAsync` с фабрикой от `CacheConfig`), не дефолтный in-memory store; значения — plain-JSON DTO (никакой бинарной десериализации и class-инстансов с методами); per-cache explicit TTL из типизированного `CacheConfig` (`NESTBOOT-4`); fail-fast без backend; тесты — Testcontainers Redis (`@testcontainers/redis`), не мок порта.

4. **Ключи** (`R-CACHE-KEY-*`): namespace-префикс зашит в кеш-порт/билдер (`user-profiles:42`), kebab-case, explicit; sensitive — хешировать (`createHash('sha256')`).

5. **TTL/Invalidation** (`R-CACHE-TTL/INV-*`): каждый `cache.set(key, dto, ttlMs)` — с explicit TTL ≤ 24ч из конфига; `cache.del` на write того же ресурса и в `@OnEvent`-handler'ах (несколько — `Promise.all`); eventual consistency задекларируй в `@ApiOperation`; нет `cache.reset()` без причины.

6. **Паттерн/Stampede** (`R-CACHE-PATTERN/STAMP-*`): cache-aside дефолт (один паттерн на кеш); для одного инстанса — single-flight (`Map<string, Promise<T>>`), для multi-instance — `redlock` поверх ioredis; hot-ключи — refresh-ahead через `@Cron` (`@nestjs/schedule`); нет write-behind для money.

7. **Observability** (`R-CACHE-OBS-*`): hits/misses/evictions через `prom-client`-counters в кеш-порте; hit-rate alert. Самопроверка (§9) + предложи `ucp-node-caching-review`.

## Антипаттерны, которые НЕ генерировать

- Кеш агрегата целиком (`R-CACHE-WHERE-X2`); кеш на write-path (`R-CACHE-WHERE-X1`); кеш авторизации (`R-CACHE-WHERE-X5`); money без TTL (`R-CACHE-WHERE-X3`).
- Бинарная/исполняемая десериализация значений из Redis (`R-CACHE-CFG-X1`); `CacheModule.register()` с дефолтным in-memory store в multi-instance проде (`R-CACHE-CFG-X2/X4`); один глобальный TTL (`R-CACHE-CFG-X3`).
- Автоключ `CacheInterceptor` (URL) для service-методов / `JSON.stringify(obj)` целого DTO в ключе (`R-CACHE-KEY-X1/X2`); sensitive в ключе plain-text (`R-CACHE-KEY-X4`); infinite TTL (`R-CACHE-TTL-X1`); TTL > 24ч (`R-CACHE-TTL-X2`).
- Evict-all без причины (`R-CACHE-INV-X1`); write-behind для money (`R-CACHE-PATTERN-X1`); локальный single-flight/`Map`-lock как защита distributed-кеша (`R-CACHE-STAMP-X2`).

После работы скилла — обязательно `ucp-node-caching-review`.

$ARGUMENTS
