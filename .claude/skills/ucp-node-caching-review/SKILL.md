---
name: ucp-node-caching-review
lang: node
description: Ревью кеширования NestJS-сервиса (Node, @nestjs/cache-manager + ioredis) по UCP (коды R-CACHE-*) — read-проекции не агрегаты, Redis-backend с plain-JSON, per-cache TTL, namespace-ключи, evict на write, stampede через redlock.
when_to_use: Ревью кеш-порта/адаптера, CacheModule-конфига, CacheInterceptor/@CacheTTL, invalidation-логики.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Caching (Node / @nestjs/cache-manager + ioredis)

Ты ревьюишь кеширование на соответствие **контракту** `backend/caching/caching-rules.md` (`R-CACHE-*`) и **Node-реализации** `backend/caching/node/caching-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/caching/caching-rules.md`** + **`backend/caching/node/caching-style-guide.md`**.
- Парные: `cqrs` (кеш read-проекций), `backend/hexagonal/node/...` (кеш-порт), `observability` (hit-rate), `auth-patterns` (`AUTH-5`).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-CACHE-WHERE-X2`, `R-CACHE-CFG-X1`), не префикс.

2. **Скоп.** Кеш-порт/адаптер (`adapters/out/cache/`), `CacheModule`-конфиг, `CacheInterceptor`/`@CacheTTL`-использование, invalidation на write/`@OnEvent`, билдеры ключей; `git diff`.

3. **Прогон.**
   - **Где (`R-CACHE-WHERE-*`):** кеш агрегата целиком → `R-CACHE-WHERE-X2`; кеш write-path (`CacheInterceptor` на POST) → `R-CACHE-WHERE-X1`; кеш авторизации/валидации → `R-CACHE-WHERE-X5`; money без TTL/invalidation → `R-CACHE-WHERE-X3`.
   - **Конфиг (`R-CACHE-CFG-*`):** бинарная/исполняемая десериализация значений → `R-CACHE-CFG-X1` (security); дефолтный in-memory store (`CacheModule.register()`) в multi-instance проде → `R-CACHE-CFG-X2`; один глобальный TTL модуля → `R-CACHE-CFG-X3`; «кеш» без реального backend / no-op при ошибке подключения → `R-CACHE-CFG-X4`; тесты — Testcontainers Redis, не мок порта (`R-CACHE-CFG-5`).
   - **Ключи (`R-CACHE-KEY-*`):** namespace-префикс, explicit-билдер, kebab-case. Автоключ из URL/всех аргументов → `R-CACHE-KEY-X1`. `String(obj)`/`JSON.stringify(obj)` в ключе → `R-CACHE-KEY-X2`. Общий cache на разные entity → `R-CACHE-KEY-X3`. Sensitive plain-text в ключе → `R-CACHE-KEY-X4`.
   - **TTL (`R-CACHE-TTL-*`):** explicit, ≤24ч, из конфига. `cache.set` без TTL / `ttl: 0` → `R-CACHE-TTL-X1`. >24ч → `R-CACHE-TTL-X2`. Money без TTL / >1м без strict invalidation → `R-CACHE-TTL-X3`.
   - **Invalidation (`R-CACHE-INV-*`):** `cache.del` на write того же ресурса и в `@OnEvent`. `cache.reset()`/FLUSHDB без причины → `R-CACHE-INV-X1`. Только TTL для money → `R-CACHE-INV-X2`. EC без декларации в OpenAPI → `R-CACHE-INV-X3`.
   - **Паттерн/Stampede (`R-CACHE-PATTERN/STAMP-*`):** один паттерн на кеш (микс → `R-CACHE-PATTERN-X2`); write-behind для money → `R-CACHE-PATTERN-X1`; локальный `Map`-lock/single-flight как защита distributed-кеша → `R-CACHE-STAMP-X2`; игнор stampede на hot → `R-CACHE-STAMP-X1`.
   - **Observability (`R-CACHE-OBS-*`):** hit/miss-метрики в кеш-порте (`prom-client`); отсутствуют → `R-CACHE-OBS-X1`.

4. **Cross-check:** кешируемые read-проекции — `ucp-node-cqrs-review`; кеш-порт в core/ — `ucp-node-hexagonal-review`; hit-rate метрика — `ucp-node-observability-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — бинарная десериализация (`R-CACHE-CFG-X1`), кеш авторизации (`R-CACHE-WHERE-X5`), money без TTL/invalidation (`R-CACHE-WHERE-X3`/`R-CACHE-TTL-X3`), write-behind для money (`R-CACHE-PATTERN-X1`), `Map`-lock для distributed-кеша (`R-CACHE-STAMP-X2`).
   - **Предупреждение** — кеш агрегата целиком (`R-CACHE-WHERE-X2`), in-memory store в проде (`R-CACHE-CFG-X2`), infinite/>24ч TTL (`R-CACHE-TTL-X1/X2`), evict-all без причины (`R-CACHE-INV-X1`), sensitive в ключе (`R-CACHE-KEY-X4`).
   - **Замечание** — один глобальный TTL (`R-CACHE-CFG-X3`), микс паттернов (`R-CACHE-PATTERN-X2`), метрики кеша выключены (`R-CACHE-OBS-X1`).

## Что не входит

- Какие read-проекции кешировать — `ucp-node-cqrs-review`. Кеш-порт в core/ — `ucp-node-hexagonal-review`.
- hit-rate метрика/алерты — `ucp-node-observability-review`.

$ARGUMENTS
