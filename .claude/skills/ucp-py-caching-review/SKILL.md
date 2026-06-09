---
name: ucp-py-caching-review
lang: python
description: Ревью кеширования FastAPI-сервиса (Python, redis.asyncio + aiocache) по UCP (коды R-CACHE-*) — read-проекции не агрегаты, Redis-backend с JSON не pickle, per-cache TTL, namespace-ключи, evict на write, stampede через distributed lock.
when_to_use: Ревью cache-порта/адаптера, redis-конфига, @cached-декораторов, invalidation-логики.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Caching (Python / redis.asyncio + aiocache)

Ты ревьюишь кеширование на соответствие **контракту** `backend/caching/caching-rules.md` (`R-CACHE-*`) и **Python-реализации** `backend/caching/python/caching-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/caching/caching-rules.md`** + **`backend/caching/python/caching-style-guide.md`**.
- Парные: `cqrs` (кеш read-проекций), `backend/hexagonal/python/...` (cache-порт), `observability` (hit-rate), `auth-patterns` (`AUTH-5`).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-CACHE-WHERE-X2`, `R-CACHE-CFG-X1`), не префикс.

2. **Скоп.** Cache-порт/адаптер (`adapters/out/cache/`), redis-конфиг, `@cached`-использование, invalidation на write, ключи; `git diff`.

3. **Прогон.**
   - **Где (`R-CACHE-WHERE-*`):** кеш агрегата целиком → `R-CACHE-WHERE-X2`; кеш write-path → `R-CACHE-WHERE-X1`; кеш авторизации → `R-CACHE-WHERE-X5`; money без TTL/invalidation → `R-CACHE-WHERE-X3`.
   - **Конфиг (`R-CACHE-CFG-*`):** `pickle`-сериализация → `R-CACHE-CFG-X1` (security); in-memory dict в проде → `R-CACHE-CFG-X2`; один глобальный TTL → `R-CACHE-CFG-X3`; «кеш» без backend → `R-CACHE-CFG-X4`.
   - **Ключи (`R-CACHE-KEY-*`):** namespace-префикс, explicit, kebab-case. Sensitive plain-text в ключе → `R-CACHE-KEY-X4`. Объект `repr`/`id` в ключе → `R-CACHE-KEY-X2`. Общий cache на entity → `R-CACHE-KEY-X3`.
   - **TTL (`R-CACHE-TTL-*`):** explicit, ≤24ч. Infinite/None → `R-CACHE-TTL-X1`. >24ч → `R-CACHE-TTL-X2`. Money без TTL → `R-CACHE-TTL-X3`.
   - **Invalidation (`R-CACHE-INV-*`):** evict на write того же ресурса. Evict-all без причины → `R-CACHE-INV-X1`. Только TTL для money → `R-CACHE-INV-X2`. EC без декларации → `R-CACHE-INV-X3`.
   - **Паттерн/Stampede (`R-CACHE-PATTERN/STAMP-*`):** один паттерн на кеш (микс → `R-CACHE-PATTERN-X2`); write-behind для money → `R-CACHE-PATTERN-X1`; `asyncio.Lock` для distributed-кеша → `R-CACHE-STAMP-X2`; игнор stampede на hot → `R-CACHE-STAMP-X1`.
   - **Observability (`R-CACHE-OBS-*`):** hit/miss метрики; отключены → `R-CACHE-OBS-X1`.

4. **Cross-check:** кешируемые read-проекции — `ucp-py-cqrs-review`; cache-порт в core/ — `ucp-py-hexagonal-review`; hit-rate метрика — `ucp-py-observability-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `pickle`-сериализация (`R-CACHE-CFG-X1`), кеш авторизации (`R-CACHE-WHERE-X5`), money без TTL/invalidation (`R-CACHE-WHERE-X3`/`R-CACHE-TTL-X3`), write-behind для money (`R-CACHE-PATTERN-X1`), `asyncio.Lock` для distributed-кеша (`R-CACHE-STAMP-X2`).
   - **Предупреждение** — кеш агрегата целиком (`R-CACHE-WHERE-X2`), in-memory dict в проде (`R-CACHE-CFG-X2`), infinite/>24ч TTL (`R-CACHE-TTL-X1/X2`), evict-all без причины (`R-CACHE-INV-X1`), sensitive в ключе (`R-CACHE-KEY-X4`).
   - **Замечание** — один глобальный TTL (`R-CACHE-CFG-X3`), микс паттернов (`R-CACHE-PATTERN-X2`), метрики кеша выключены (`R-CACHE-OBS-X1`).

## Что не входит

- Какие read-проекции кешировать — `ucp-py-cqrs-review`. Cache-порт в core/ — `ucp-py-hexagonal-review`.
- hit-rate метрика/алерты — `ucp-py-observability-review`.

$ARGUMENTS
