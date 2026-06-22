---
name: ucp-go-caching-design
lang: go
description: Спроектировать кеширование в Go-сервисе (net/http + chi) по UCP (коды R-CACHE-*) — cache-порт в core/, go-redis/v9 + JSON, explicit TTL, evict на write, singleflight/SetNX от stampede, promauto-метрики, testcontainers-go в тестах.
when_to_use: Добавление кеша. Триггеры — «закешируй X», «redis-кеш для Y», «cache-aside на Go».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Caching — проектирование (Go / net/http + chi)

Ты проектируешь кеширование по **контракту** `backend/caching/caching-rules.md` (`R-CACHE-*`) и **Go-реализации** `backend/caching/go/caching-style-guide.md`.

В Go нет декларативного `@Cacheable`: кеш — явный cache-aside через тонкий cache-порт (`interface`) в `core/` и реализацию в `adapters/out/cache/`. Ошибки — значения (`apperr.Kind`) по контракту error-handling.

## Инструкции

1. **Прочитай** контракт + Go-style-guide. Коды в обосновании, не в коде. Связанные: `backend/caching/caching-rules.md`, `backend/caching/go/caching-style-guide.md`. Смежные: `cqrs` (кеш read-проекций), `backend/hexagonal/go/...` (cache-порт в core/), `backend/observability/go/...` (hit-rate метрика), `backend/auth-patterns/...` (`AUTH-5` JWK-кеш).

2. **Где** (`R-CACHE-WHERE-*`): кешируй read-heavy + редко меняющиеся read-проекции (`CustomerSummary`, `OrderSummary`), не агрегаты, не write-path, не результат авторизации. Money — только с TTL 5–30 секунд + evict на каждом write.

3. **Backend/конфиг** (`R-CACHE-CFG-*`): backend — Redis (`redis/go-redis/v9`), не `sync.Map` / in-memory в multi-instance проде; сериализация — JSON (`encoding/json`), **никогда `encoding/gob`**; per-cache explicit TTL через `CacheConfig`-struct с env-тегами; cache-порт — `interface` в `core/<domain>/cache_port.go`, реализация в `adapters/out/cache/`.

4. **Ключи** (`R-CACHE-KEY-*`): namespace-префикс kebab-case (`"customer-profiles:" + customerID`), explicit string-join через разделитель, sensitive — хешировать через `crypto/sha256`.

5. **TTL/Invalidation** (`R-CACHE-TTL/INV-*`): каждый кеш — explicit TTL ≠ 0, ≤ 24ч для бизнес-данных; evict на write того же ресурса / по доменному событию (`OnCustomerUpdated`); ошибку evict-а — Warn+логируй, не возвращай (best-effort); eventual consistency задекларируй в OpenAPI.

6. **Паттерн/Stampede** (`R-CACHE-PATTERN/STAMP-*`): cache-aside — дефолт (один паттерн на кеш); для single-instance hot-ключей — `golang.org/x/sync/singleflight`; для Redis multi-instance — distributed lock через `SetNX`; для самых hot-ключей — refresh-ahead (фоновая горутина с `time.Ticker`); нет write-behind для money.

7. **Observability** (`R-CACHE-OBS-*`): `cache_hits_total`, `cache_misses_total`, `cache_evictions_total` через `promauto.NewCounterVec` с label `cache`; evict логируется `slog.DebugContext`; Redis-side метрики — через Redis Exporter, не в коде. Самопроверка по чеклисту из style-guide §«Чеклист подключения» + предложи `ucp-go-caching-review`.

## Антипаттерны, которые НЕ генерировать

- Кеш агрегата целиком (`R-CACHE-WHERE-X2`); кеш на write-path (`R-CACHE-WHERE-X1`); кеш авторизации (`R-CACHE-WHERE-X5`); money без TTL (`R-CACHE-WHERE-X3`).
- `encoding/gob` (`R-CACHE-CFG-X1`); `sync.Map` / in-memory в multi-instance проде (`R-CACHE-CFG-X2`); один глобальный TTL для всех кешей (`R-CACHE-CFG-X3`); `nil`-имплементация порта вместо `NoopCache` (`R-CACHE-CFG-X4`).
- `fmt.Sprintf("%v", args...)` как ключ (`R-CACHE-KEY-X1`); указатель на struct в ключе (`R-CACHE-KEY-X2`); один namespace для разных сущностей (`R-CACHE-KEY-X3`); sensitive plain-text в ключе (`R-CACHE-KEY-X4`).
- `c.redis.Set(ctx, key, val, 0)` (infinite TTL, `R-CACHE-TTL-X1`); TTL > 24ч для бизнес-данных (`R-CACHE-TTL-X2`); money-кеш без TTL или TTL > 1м без строгой invalidation (`R-CACHE-TTL-X3`).
- `FLUSHDB` / wildcard-удаление без причины (`R-CACHE-INV-X1`); полагаться только на TTL для money/orders (`R-CACHE-INV-X2`).
- Write-behind для money/critical-данных (`R-CACHE-PATTERN-X1`); смешение паттернов на одном кеше (`R-CACHE-PATTERN-X2`); `sync.Mutex` как защита distributed-кеша (`R-CACHE-STAMP-X2`).
- Отсутствие `cache_hits_total` / `cache_misses_total` (`R-CACHE-OBS-X1`).

После работы скилла — обязательно `ucp-go-caching-review`.

$ARGUMENTS
