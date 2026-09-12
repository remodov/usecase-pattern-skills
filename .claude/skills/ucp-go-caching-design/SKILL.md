---
name: ucp-go-caching-design
lang: go
description: Спроектировать кеширование в Go-сервисе (net/http + chi) по UCP (требования caching/*) — cache-порт в core/, go-redis/v9 + JSON, explicit TTL, evict на write, singleflight/SetNX от stampede, promauto-метрики, testcontainers-go в тестах.
when_to_use: Добавление кеша. Триггеры — «закешируй X», «redis-кеш для Y», «cache-aside на Go».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Caching — проектирование (Go / net/http + chi)

Ты проектируешь кеширование по **контракту** `backend/caching/spec.md` (`R-CACHE-*`) и **Go-реализации** `backend/caching/references/go/implementation.md`.

В Go нет декларативного `@Cacheable`: кеш — явный cache-aside через тонкий cache-порт (`interface`) в `core/` и реализацию в `adapters/out/cache/`. Ошибки — значения (`apperr.Kind`) по контракту error-handling.

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды в обосновании, не в коде. Связанные: `backend/caching/spec.md`, `backend/caching/references/go/implementation.md`. Смежные: `cqrs` (кеш read-проекций), `backend/hexagonal/go/...` (cache-порт в core/), `backend/observability/go/...` (hit-rate метрика), `backend/auth-patterns/...` (`auth-patterns/token-validated-by-library` JWK-кеш).

2. **Где** (`R-CACHE-WHERE-*`): кешируй read-heavy + редко меняющиеся read-проекции (`CustomerSummary`, `OrderSummary`), не агрегаты, не write-path, не результат авторизации. Money — только с TTL 5–30 секунд + evict на каждом write.

3. **Backend/конфиг** (`R-CACHE-CFG-*`): backend — Redis (`redis/go-redis/v9`), не `sync.Map` / in-memory в multi-instance проде; сериализация — JSON (`encoding/json`), **никогда `encoding/gob`**; per-cache explicit TTL через `CacheConfig`-struct с env-тегами; cache-порт — `interface` в `core/<domain>/cache_port.go`, реализация в `adapters/out/cache/`.

4. **Ключи** (`R-CACHE-KEY-*`): namespace-префикс kebab-case (`"customer-profiles:" + customerID`), explicit string-join через разделитель, sensitive — хешировать через `crypto/sha256`.

5. **TTL/Invalidation** (`R-CACHE-TTL/INV-*`): каждый кеш — explicit TTL ≠ 0, ≤ 24ч для бизнес-данных; evict на write того же ресурса / по доменному событию (`OnCustomerUpdated`); ошибку evict-а — Warn+логируй, не возвращай (best-effort); eventual consistency задекларируй в OpenAPI.

6. **Паттерн/Stampede** (`R-CACHE-PATTERN/STAMP-*`): cache-aside — дефолт (один паттерн на кеш); для single-instance hot-ключей — `golang.org/x/sync/singleflight`; для Redis multi-instance — distributed lock через `SetNX`; для самых hot-ключей — refresh-ahead (фоновая горутина с `time.Ticker`); нет write-behind для money.

7. **Observability** (`R-CACHE-OBS-*`): `cache_hits_total`, `cache_misses_total`, `cache_evictions_total` через `promauto.NewCounterVec` с label `cache`; evict логируется `slog.DebugContext`; Redis-side метрики — через Redis Exporter, не в коде. Самопроверка по чеклисту из справочника, раздел «Чеклист подключения» + предложи `ucp-go-caching-review`.

## Антипаттерны, которые НЕ генерировать

- Кеш агрегата целиком (`caching/cache-projections-not-aggregates`); кеш на write-path (`caching/no-cache-on-write-path`); кеш авторизации (`caching/no-caching-authorization-results`); money без TTL (`caching/money-data-needs-explicit-invalidation`).
- `encoding/gob` (`caching/values-serialized-as-json`); `sync.Map` / in-memory в multi-instance проде (`caching/distributed-cache-in-production`); один глобальный TTL для всех кешей (`caching/explicit-ttl-per-cache`); `nil`-имплементация порта вместо `NoopCache` (`caching/no-cache-without-manager`).
- `fmt.Sprintf("%v", args...)` как ключ (`caching/explicit-cache-key`); указатель на struct в ключе (`caching/explicit-cache-key`); один namespace для разных сущностей (`caching/cache-name-is-namespace`); sensitive plain-text в ключе (`caching/no-sensitive-data-in-keys`).
- `c.redis.Set(ctx, key, val, 0)` (infinite TTL, `caching/explicit-ttl-per-cache`); TTL > 24ч для бизнес-данных (`caching/ttl-matches-data-nature`); money-кеш без TTL или TTL > 1м без строгой invalidation (`caching/money-data-needs-explicit-invalidation`).
- `FLUSHDB` / wildcard-удаление без причины (`caching/no-routine-full-flush`); полагаться только на TTL для money/orders (`caching/ttl-is-not-consistency`).
- Write-behind для money/critical-данных (`caching/cache-aside-is-default`); смешение паттернов на одном кеше (`caching/cache-aside-is-default`); `sync.Mutex` как защита distributed-кеша (`caching/stampede-protection`).
- Отсутствие `cache_hits_total` / `cache_misses_total` (`caching/cache-metrics-enabled`).

После работы скилла — обязательно `ucp-go-caching-review`.

$ARGUMENTS
