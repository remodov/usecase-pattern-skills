---
name: ucp-py-caching-review
lang: python
description: Ревью кеширования FastAPI-сервиса (Python, redis.asyncio + aiocache) по UCP (требования caching/*) — read-проекции не агрегаты, Redis-backend с JSON не pickle, per-cache TTL, namespace-ключи, evict на write, stampede через distributed lock.
when_to_use: Ревью cache-порта/адаптера, redis-конфига, @cached-декораторов, invalidation-логики.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Caching (Python / redis.asyncio + aiocache)

Ты ревьюишь кеширование на соответствие **контракту** `backend/caching/spec.md` (`R-CACHE-*`) и **Python-реализации** `backend/caching/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/caching/spec.md`** + **`backend/caching/references/python/implementation.md`**.
- Парные: `cqrs` (кеш read-проекций), `backend/hexagonal/python/...` (cache-порт), `observability` (hit-rate), `auth-patterns` (`auth-patterns/token-validated-by-library`).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`caching/cache-projections-not-aggregates`, `caching/values-serialized-as-json`), не префикс.

2. **Скоп.** Cache-порт/адаптер (`adapters/out/cache/`), redis-конфиг, `@cached`-использование, invalidation на write, ключи; `git diff`.

3. **Прогон.**
   - **Где (`R-CACHE-WHERE-*`):** кеш агрегата целиком → `caching/cache-projections-not-aggregates`; кеш write-path → `caching/no-cache-on-write-path`; кеш авторизации → `caching/no-caching-authorization-results`; money без TTL/invalidation → `caching/money-data-needs-explicit-invalidation`.
   - **Конфиг (`R-CACHE-CFG-*`):** `pickle`-сериализация → `caching/values-serialized-as-json` (security); in-memory dict в проде → `caching/distributed-cache-in-production`; один глобальный TTL → `caching/explicit-ttl-per-cache`; «кеш» без backend → `caching/no-cache-without-manager`.
   - **Ключи (`R-CACHE-KEY-*`):** namespace-префикс, explicit, kebab-case. Sensitive plain-text в ключе → `caching/no-sensitive-data-in-keys`. Объект `repr`/`id` в ключе → `caching/explicit-cache-key`. Общий cache на entity → `caching/cache-name-is-namespace`.
   - **TTL (`R-CACHE-TTL-*`):** explicit, ≤24ч. Infinite/None → `caching/explicit-ttl-per-cache`. >24ч → `caching/ttl-matches-data-nature`. Money без TTL → `caching/money-data-needs-explicit-invalidation`.
   - **Invalidation (`R-CACHE-INV-*`):** evict на write того же ресурса. Evict-all без причины → `caching/no-routine-full-flush`. Только TTL для money → `caching/ttl-is-not-consistency`. EC без декларации → `caching/staleness-is-declared`.
   - **Паттерн/Stampede (`R-CACHE-PATTERN/STAMP-*`):** один паттерн на кеш (микс → `caching/cache-aside-is-default`); write-behind для money → `caching/cache-aside-is-default`; `asyncio.Lock` для distributed-кеша → `caching/stampede-protection`; игнор stampede на hot → `caching/stampede-protection`.
   - **Observability (`R-CACHE-OBS-*`):** hit/miss метрики; отключены → `caching/cache-metrics-enabled`.

4. **Cross-check:** кешируемые read-проекции — `ucp-py-cqrs-review`; cache-порт в core/ — `ucp-py-hexagonal-review`; hit-rate метрика — `ucp-py-observability-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `pickle`-сериализация (`caching/values-serialized-as-json`), кеш авторизации (`caching/no-caching-authorization-results`), money без TTL/invalidation (`caching/money-data-needs-explicit-invalidation`/`caching/money-data-needs-explicit-invalidation`), write-behind для money (`caching/cache-aside-is-default`), `asyncio.Lock` для distributed-кеша (`caching/stampede-protection`).
   - **Предупреждение** — кеш агрегата целиком (`caching/cache-projections-not-aggregates`), in-memory dict в проде (`caching/distributed-cache-in-production`), infinite/>24ч TTL (`R-CACHE-TTL-X1/X2`), evict-all без причины (`caching/no-routine-full-flush`), sensitive в ключе (`caching/no-sensitive-data-in-keys`).
   - **Замечание** — один глобальный TTL (`caching/explicit-ttl-per-cache`), микс паттернов (`caching/cache-aside-is-default`), метрики кеша выключены (`caching/cache-metrics-enabled`).

## Что не входит

- Какие read-проекции кешировать — `ucp-py-cqrs-review`. Cache-порт в core/ — `ucp-py-hexagonal-review`.
- hit-rate метрика/алерты — `ucp-py-observability-review`.

$ARGUMENTS
