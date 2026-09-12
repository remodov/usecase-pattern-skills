---
name: ucp-py-caching-design
lang: python
description: Спроектировать кеширование в FastAPI-сервисе на Python (требования caching/*) — redis.asyncio/aiocache, cache-aside через cache-порт, кеш read-проекций, JSON-сериализация, explicit TTL, evict на write, защита от stampede.
when_to_use: Добавление кеша. Триггеры — «закешируй X», «redis-кеш для Y», «cache-aside на питоне».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Caching — проектирование (Python / redis.asyncio + aiocache)

Ты проектируешь кеширование по **контракту** `backend/caching/spec.md` (`R-CACHE-*`) и **Python-реализации** `backend/caching/references/python/implementation.md`.

## Инструкции

1. **Прочитай** требования `python-style/*`. Коды в обосновании, не в коде. Связанные: `cqrs` (кеш read-проекций), `backend/hexagonal/python/...` (cache-порт в core/), `observability` (hit-rate метрика), `auth-patterns` (`auth-patterns/token-validated-by-library` JWK-кеш).

2. **Где** (`R-CACHE-WHERE-*`): кешируй read-heavy + редко меняющиеся read-проекции (`OrderSummary`), не агрегаты, не write-path, не результат авторизации. Money — только с коротким TTL + явной invalidation.

3. **Backend/конфиг** (`R-CACHE-CFG-*`): `redis.asyncio` (не in-memory dict в проде), JSON-сериализация (**не pickle**), per-cache explicit TTL через `pydantic-settings`; кеш за `Protocol`-портом в `core/`, реализация в `adapters/out/cache/`.

4. **Ключи** (`R-CACHE-KEY-*`): namespace-префикс (`user-profiles:{id}`), kebab-case, explicit, sensitive — хешировать.

5. **TTL/Invalidation** (`R-CACHE-TTL/INV-*`): каждый кеш — explicit TTL ≤ 24ч; evict на write того же ресурса / по доменному событию; eventual consistency задекларируй; нет evict-all без причины.

6. **Паттерн/Stampede** (`R-CACHE-PATTERN/STAMP-*`): cache-aside дефолт (один паттерн на кеш); для hot-ключей — distributed lock (`redis.lock`) или refresh-ahead; нет write-behind для money.

7. **Observability** (`R-CACHE-OBS-*`): hits/misses/evictions через prometheus-client; hit-rate alert. Самопроверка (§9) + предложи `ucp-py-caching-review`.

## Антипаттерны, которые НЕ генерировать

- Кеш агрегата целиком (`caching/cache-projections-not-aggregates`); кеш на write-path (`caching/no-cache-on-write-path`); кеш авторизации (`caching/no-caching-authorization-results`); money без TTL (`caching/money-data-needs-explicit-invalidation`).
- `pickle`-сериализация (`caching/values-serialized-as-json`); in-memory dict в multi-instance проде (`caching/distributed-cache-in-production`); один глобальный TTL (`caching/explicit-ttl-per-cache`).
- Sensitive в ключе plain-text (`caching/no-sensitive-data-in-keys`); infinite TTL (`caching/explicit-ttl-per-cache`); TTL > 24ч (`caching/ttl-matches-data-nature`).
- Evict-all без причины (`caching/no-routine-full-flush`); write-behind для money (`caching/cache-aside-is-default`); `asyncio.Lock` для distributed-кеша (`caching/stampede-protection`).

После работы скилла — обязательно `ucp-py-caching-review`.

$ARGUMENTS
