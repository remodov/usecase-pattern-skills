---
name: ucp-node-caching-review
lang: node
description: Ревью кеширования NestJS-сервиса (Node, @nestjs/cache-manager + ioredis) по UCP (требования caching/*) — read-проекции не агрегаты, Redis-backend с plain-JSON, per-cache TTL, namespace-ключи, evict на write, stampede через redlock.
when_to_use: Ревью кеш-порта/адаптера, CacheModule-конфига, CacheInterceptor/@CacheTTL, invalidation-логики.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Caching (Node / @nestjs/cache-manager + ioredis)

Ты ревьюишь кеширование на соответствие **контракту** `backend/caching/spec.md` (`R-CACHE-*`) и **Node-реализации** `backend/caching/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/caching/spec.md`** + **`backend/caching/references/node/implementation.md`**.
- Парные: `cqrs` (кеш read-проекций), `backend/hexagonal/node/...` (кеш-порт), `observability` (hit-rate), `auth-patterns` (`auth-patterns/token-validated-by-library`).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`caching/cache-projections-not-aggregates`, `caching/values-serialized-as-json`), не префикс.

2. **Скоп.** Кеш-порт/адаптер (`adapters/out/cache/`), `CacheModule`-конфиг, `CacheInterceptor`/`@CacheTTL`-использование, invalidation на write/`@OnEvent`, билдеры ключей; `git diff`.

3. **Прогон.**
   - **Где (`R-CACHE-WHERE-*`):** кеш агрегата целиком → `caching/cache-projections-not-aggregates`; кеш write-path (`CacheInterceptor` на POST) → `caching/no-cache-on-write-path`; кеш авторизации/валидации → `caching/no-caching-authorization-results`; money без TTL/invalidation → `caching/money-data-needs-explicit-invalidation`.
   - **Конфиг (`R-CACHE-CFG-*`):** бинарная/исполняемая десериализация значений → `caching/values-serialized-as-json` (security); дефолтный in-memory store (`CacheModule.register()`) в multi-instance проде → `caching/distributed-cache-in-production`; один глобальный TTL модуля → `caching/explicit-ttl-per-cache`; «кеш» без реального backend / no-op при ошибке подключения → `caching/no-cache-without-manager`; тесты — Testcontainers Redis, не мок порта (`caching/tests-use-real-cache`).
   - **Ключи (`R-CACHE-KEY-*`):** namespace-префикс, explicit-билдер, kebab-case. Автоключ из URL/всех аргументов → `caching/explicit-cache-key`. `String(obj)`/`JSON.stringify(obj)` в ключе → `caching/explicit-cache-key`. Общий cache на разные entity → `caching/cache-name-is-namespace`. Sensitive plain-text в ключе → `caching/no-sensitive-data-in-keys`.
   - **TTL (`R-CACHE-TTL-*`):** explicit, ≤24ч, из конфига. `cache.set` без TTL / `ttl: 0` → `caching/explicit-ttl-per-cache`. >24ч → `caching/ttl-matches-data-nature`. Money без TTL / >1м без strict invalidation → `caching/money-data-needs-explicit-invalidation`.
   - **Invalidation (`R-CACHE-INV-*`):** `cache.del` на write того же ресурса и в `@OnEvent`. `cache.reset()`/FLUSHDB без причины → `caching/no-routine-full-flush`. Только TTL для money → `caching/ttl-is-not-consistency`. EC без декларации в OpenAPI → `caching/staleness-is-declared`.
   - **Паттерн/Stampede (`R-CACHE-PATTERN/STAMP-*`):** один паттерн на кеш (микс → `caching/cache-aside-is-default`); write-behind для money → `caching/cache-aside-is-default`; локальный `Map`-lock/single-flight как защита distributed-кеша → `caching/stampede-protection`; игнор stampede на hot → `caching/stampede-protection`.
   - **Observability (`R-CACHE-OBS-*`):** hit/miss-метрики в кеш-порте (`prom-client`); отсутствуют → `caching/cache-metrics-enabled`.

4. **Cross-check:** кешируемые read-проекции — `ucp-node-cqrs-review`; кеш-порт в core/ — `ucp-node-hexagonal-review`; hit-rate метрика — `ucp-node-observability-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — бинарная десериализация (`caching/values-serialized-as-json`), кеш авторизации (`caching/no-caching-authorization-results`), money без TTL/invalidation (`caching/money-data-needs-explicit-invalidation`/`caching/money-data-needs-explicit-invalidation`), write-behind для money (`caching/cache-aside-is-default`), `Map`-lock для distributed-кеша (`caching/stampede-protection`).
   - **Предупреждение** — кеш агрегата целиком (`caching/cache-projections-not-aggregates`), in-memory store в проде (`caching/distributed-cache-in-production`), infinite/>24ч TTL (`R-CACHE-TTL-X1/X2`), evict-all без причины (`caching/no-routine-full-flush`), sensitive в ключе (`caching/no-sensitive-data-in-keys`).
   - **Замечание** — один глобальный TTL (`caching/explicit-ttl-per-cache`), микс паттернов (`caching/cache-aside-is-default`), метрики кеша выключены (`caching/cache-metrics-enabled`).

## Что не входит

- Какие read-проекции кешировать — `ucp-node-cqrs-review`. Кеш-порт в core/ — `ucp-node-hexagonal-review`.
- hit-rate метрика/алерты — `ucp-node-observability-review`.

$ARGUMENTS
