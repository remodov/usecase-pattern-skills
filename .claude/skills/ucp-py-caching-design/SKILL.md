---
name: ucp-py-caching-design
lang: python
description: Спроектировать кеширование в FastAPI-сервисе на Python (коды R-CACHE-*) — redis.asyncio/aiocache, cache-aside через cache-порт, кеш read-проекций, JSON-сериализация, explicit TTL, evict на write, защита от stampede.
when_to_use: Добавление кеша. Триггеры — «закешируй X», «redis-кеш для Y», «cache-aside на питоне».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Caching — проектирование (Python / redis.asyncio + aiocache)

Ты проектируешь кеширование по **контракту** `backend/caching/caching-rules.md` (`R-CACHE-*`) и **Python-реализации** `backend/caching/python/caching-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `cqrs` (кеш read-проекций), `backend/hexagonal/python/...` (cache-порт в core/), `observability` (hit-rate метрика), `auth-patterns` (`AUTH-5` JWK-кеш).

2. **Где** (`R-CACHE-WHERE-*`): кешируй read-heavy + редко меняющиеся read-проекции (`OrderSummary`), не агрегаты, не write-path, не результат авторизации. Money — только с коротким TTL + явной invalidation.

3. **Backend/конфиг** (`R-CACHE-CFG-*`): `redis.asyncio` (не in-memory dict в проде), JSON-сериализация (**не pickle**), per-cache explicit TTL через `pydantic-settings`; кеш за `Protocol`-портом в `core/`, реализация в `adapters/out/cache/`.

4. **Ключи** (`R-CACHE-KEY-*`): namespace-префикс (`user-profiles:{id}`), kebab-case, explicit, sensitive — хешировать.

5. **TTL/Invalidation** (`R-CACHE-TTL/INV-*`): каждый кеш — explicit TTL ≤ 24ч; evict на write того же ресурса / по доменному событию; eventual consistency задекларируй; нет evict-all без причины.

6. **Паттерн/Stampede** (`R-CACHE-PATTERN/STAMP-*`): cache-aside дефолт (один паттерн на кеш); для hot-ключей — distributed lock (`redis.lock`) или refresh-ahead; нет write-behind для money.

7. **Observability** (`R-CACHE-OBS-*`): hits/misses/evictions через prometheus-client; hit-rate alert. Самопроверка (§9) + предложи `ucp-py-caching-review`.

## Антипаттерны, которые НЕ генерировать

- Кеш агрегата целиком (`R-CACHE-WHERE-X2`); кеш на write-path (`R-CACHE-WHERE-X1`); кеш авторизации (`R-CACHE-WHERE-X5`); money без TTL (`R-CACHE-WHERE-X3`).
- `pickle`-сериализация (`R-CACHE-CFG-X1`); in-memory dict в multi-instance проде (`R-CACHE-CFG-X2`); один глобальный TTL (`R-CACHE-CFG-X3`).
- Sensitive в ключе plain-text (`R-CACHE-KEY-X4`); infinite TTL (`R-CACHE-TTL-X1`); TTL > 24ч (`R-CACHE-TTL-X2`).
- Evict-all без причины (`R-CACHE-INV-X1`); write-behind для money (`R-CACHE-PATTERN-X1`); `asyncio.Lock` для distributed-кеша (`R-CACHE-STAMP-X2`).

После работы скилла — обязательно `ucp-py-caching-review`.

$ARGUMENTS
