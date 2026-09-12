---
name: ucp-go-caching-review
lang: go
description: Ревью кеширования Go-сервиса (net/http + chi) по UCP (требования caching/*) — cache-порт как interface, go-redis/v9 + JSON, per-cache TTL из CacheConfig, namespace-ключи kebab-case, evict на write, stampede singleflight/SetNX, метрики promauto.
when_to_use: Изменения в adapters/out/cache/*.go, core/**/cache_port.go, CacheConfig, invalidation-логики в Handler'ах или событийных обработчиках.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Caching (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/caching/spec.md` (`R-CACHE-*`)
и **Go-реализации** `backend/caching/references/go/implementation.md`.
Помни парадигму: в Go нет декларативного `@Cacheable` — кеш реализуется явно через cache-aside в `core/`
(Handler читает/пишет через cache-порт-`interface`) и адаптер `adapters/out/cache/` (`redis/go-redis/v9`).
Ошибки — **значения** (`apperr.Kind` + `errors.As`), не исключения.

## Зависимости

- **`.claude/docs/backend/caching/spec.md`** — общий контракт (`R-CACHE-WHERE-*`/`CFG-*`/`KEY-*`/`TTL-*`/`INV-*`/`PATTERN-*`/`STAMP-*`/`OBS-*`).
- **`.claude/docs/backend/caching/references/go/implementation.md`** — Go-реализация (cache-порт, go-redis/v9, JSON, CacheConfig через envconfig, singleflight/SetNX, promauto, testcontainers-go).
- Парные: `backend/caching/spec.md` (кеш read-проекций), `backend/error-handling/references/go/implementation.md` (apperr.Kind + errors.As), `backend/observability/spec.md` (hit-rate), `backend/auth-patterns/spec.md` (`auth-patterns/token-validated-by-library`).

## Инструкции

1. **Прочти** общий `caching/spec.md` и `references/go/implementation.md` (идиомы). Цитируй конкретные коды (`caching/no-sensitive-data-in-keys`, `caching/values-serialized-as-json`), не только префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `core/**/cache_port.go` — интерфейс cache-порта.
   - `adapters/out/cache/*.go` — Redis-реализация, ключи, TTL, eviction, метрики.
   - `core/**/*handler.go` — cache-aside-логика в Handler'ах (get-or-load + evict на write).
   - `adapters/in/events/*.go` — invalidation как side-effect событийных обработчиков.
   - `config/config.go` — `CacheConfig` (TTL, адрес Redis).
   - `git diff` на изменённые `.go`.
   - **`Grep`**: `encoding/gob` (запрещённая сериализация), `redis.Set(ctx, key, val, 0)` (infinite TTL), `sync.Mutex` / `sync.Map` как защита distributed-кеша, `FLUSHDB` / wildcard `DEL`, отсутствие `promauto` в `adapters/out/cache/`.

3. **Прогон по подгруппам.**

   ### `R-CACHE-WHERE-*` — где кешируем
   - Кешируются read-проекции (`*Summary`, `*View`)? Кеш агрегата целиком (`Order{Items, Payment}`) → `caching/cache-projections-not-aggregates`.
   - Write-path Handler (`CreateOrder`, `ConfirmPayment`) делает cache-read → `caching/no-cache-on-write-path`.
   - Money-данные (`Balance`, `CreditLimit`) без TTL и evict → `caching/money-data-needs-explicit-invalidation`.
   - Кеш результата ABAC-проверки → `caching/no-caching-authorization-results` (security risk при изменении ролей).

   ### `R-CACHE-CFG-*` — конфигурация
   - Backend — `redis/go-redis/v9`? `sync.Map` / ristretto в multi-instance проде → `caching/distributed-cache-in-production`.
   - Сериализация — `encoding/json`? `encoding/gob` → `caching/values-serialized-as-json` (security risk + fragility).
   - Per-cache TTL через `CacheConfig`? Один глобальный `DEFAULT_TTL` → `caching/explicit-ttl-per-cache`.
   - `nil`-имплементация кеш-порта вместо explicit `NoopCache` → `caching/no-cache-without-manager`.
   - Тесты — Testcontainers Redis (`testcontainers-go`)? Мок cache-порта теряет поведение TTL/eviction → замечание к `caching/tests-use-real-cache`.

   ### `R-CACHE-KEY-*` — ключи
   - Namespace-префикс kebab-case (`"customer-profiles:" + id`) присутствует? Без префикса → `caching/cache-name-is-namespace`.
   - Составные ключи — явный join через разделитель? `fmt.Sprintf("%v", args...)` → `caching/explicit-cache-key`.
   - Указатель на struct (`fmt.Sprintf("%p", &req)`) в ключе → `caching/explicit-cache-key`.
   - Email/phone/токен plain-text в ключе → `caching/no-sensitive-data-in-keys` (хешируй через `crypto/sha256`).

   ### `R-CACHE-TTL-*` — TTL
   - Каждый именованный кеш имеет explicit TTL? `c.redis.Set(ctx, key, val, 0)` → `caching/explicit-ttl-per-cache` (infinite в go-redis).
   - TTL > 24h для бизнес-данных → `caching/ttl-matches-data-nature`.
   - Money-кеш без TTL или TTL > 1м без строгой invalidation → `caching/money-data-needs-explicit-invalidation`.
   - TTL берётся из `CacheConfig`, не хардкодится в методе?

   ### `R-CACHE-INV-*` — invalidation
   - На каждом write-методе того же ресурса — evict затронутых ключей? Ошибка evict-а логируется `slog.WarnContext`, не возвращается (best-effort)?
   - Write меняет несколько кешей → evict всех затронутых?
   - При доменных событиях — invalidation как side-effect обработчика?
   - `c.redis.Del(ctx, "namespace:*")` (wildcard) или `FLUSHDB` → `caching/no-routine-full-flush`.
   - Только TTL для money/orders → `caching/ttl-is-not-consistency`.
   - Eventual consistency не задекларирована в OpenAPI → `caching/staleness-is-declared`.

   ### `R-CACHE-PATTERN-*` — паттерны
   - Один паттерн на именованный кеш? Миксуется cache-aside + write-through для одного namespace → `caching/cache-aside-is-default`.
   - Write-behind для money/critical: запись в кеш, в БД асинхронно → `caching/cache-aside-is-default` (crash до flush = потеря данных).
   - refresh-ahead реализован через горутину (`time.NewTicker` на 80% TTL)?

   ### `R-CACHE-STAMP-*` — stampede
   - Single-instance: используется `singleflight.Group` для защиты hot-ключей?
   - Multi-instance Redis: distributed lock через `c.redis.SetNX(ctx, lockKey, "1", 5*time.Second)`? `sync.Mutex` / `sync.Map` как защита distributed-кеша → `caching/stampede-protection`.
   - Hot endpoints (>100 RPS) без stampede-защиты → `caching/stampede-protection`.

   ### `R-CACHE-OBS-*` — observability
   - `cache_hits_total`, `cache_misses_total`, `cache_evictions_total` через `promauto.NewCounterVec` с label `cache`?
   - Отсутствие этих метрик → `caching/cache-metrics-enabled`.
   - Eviction логируется на `slog.DebugContext`, не `InfoContext`?
   - Hit rate alert (< 70% для долгих кешей) задекларирован в конфиге мониторинга?

4. **Cross-check:** кешируемые read-проекции → `ucp-go-cqrs-review`; cache-порт в `core/` → `ucp-go-hexagonal-review`; hit-rate метрика/алерты → `ucp-go-observability-review`; ABAC-кеш → `ucp-auth-review` (`auth-patterns/token-validated-by-library`). Проверь наличие `errcheck`+`errorlint` в линтере (`.golangci.yml`).

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `encoding/gob` сериализация (`caching/values-serialized-as-json`), кеш ABAC-результата (`caching/no-caching-authorization-results`), money без TTL/invalidation (`caching/money-data-needs-explicit-invalidation`/`caching/money-data-needs-explicit-invalidation`), write-behind для money (`caching/cache-aside-is-default`), `sync.Mutex` как distributed-lock (`caching/stampede-protection`), sensitive plain-text в ключе (`caching/no-sensitive-data-in-keys`).
   - **Предупреждение** — кеш агрегата целиком (`caching/cache-projections-not-aggregates`), `sync.Map` в multi-instance проде (`caching/distributed-cache-in-production`), `0` TTL / TTL > 24h (`R-CACHE-TTL-X1/X2`), `FLUSHDB`/wildcard evict без причины (`caching/no-routine-full-flush`), stampede на hot endpoint без защиты (`caching/stampede-protection`).
   - **Замечание** — один глобальный TTL (`caching/explicit-ttl-per-cache`), микс паттернов (`caching/cache-aside-is-default`), отсутствие `cache_hits_total`/`cache_misses_total` (`caching/cache-metrics-enabled`), мок порта вместо Testcontainers.

## Что не входит

- Какие read-проекции кешировать — `ucp-go-cqrs-review`.
- Cache-порт в `core/` — `ucp-go-hexagonal-review`.
- Hit-rate метрика/алерты — `ucp-go-observability-review`.
- Retry/CB-конфиг — `ucp-go-resilience-review`.

$ARGUMENTS
