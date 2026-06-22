---
name: ucp-go-caching-review
lang: go
description: Ревью кеширования Go-сервиса (net/http + chi) по UCP (коды R-CACHE-*) — cache-порт как interface, go-redis/v9 + JSON, per-cache TTL из CacheConfig, namespace-ключи kebab-case, evict на write, stampede singleflight/SetNX, метрики promauto.
when_to_use: Изменения в adapters/out/cache/*.go, core/**/cache_port.go, CacheConfig, invalidation-логики в Handler'ах или событийных обработчиках.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Caching (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/caching/caching-rules.md` (`R-CACHE-*`)
и **Go-реализации** `backend/caching/go/caching-style-guide.md`.
Помни парадигму: в Go нет декларативного `@Cacheable` — кеш реализуется явно через cache-aside в `core/`
(Handler читает/пишет через cache-порт-`interface`) и адаптер `adapters/out/cache/` (`redis/go-redis/v9`).
Ошибки — **значения** (`apperr.Kind` + `errors.As`), не исключения.

## Зависимости

- **`.claude/docs/backend/caching/caching-rules.md`** — общий контракт (`R-CACHE-WHERE-*`/`CFG-*`/`KEY-*`/`TTL-*`/`INV-*`/`PATTERN-*`/`STAMP-*`/`OBS-*`).
- **`.claude/docs/backend/caching/go/caching-style-guide.md`** — Go-реализация (cache-порт, go-redis/v9, JSON, CacheConfig через envconfig, singleflight/SetNX, promauto, testcontainers-go).
- Парные: `backend/caching/caching-rules.md` (кеш read-проекций), `backend/error-handling/go/error-handling-style-guide.md` (apperr.Kind + errors.As), `backend/observability/observability-rules.md` (hit-rate), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-5`).

## Инструкции

1. **Прочти** общий `caching-rules.md` (коды) и Go-style-guide (идиомы). Цитируй конкретные коды (`R-CACHE-KEY-X4`, `R-CACHE-CFG-X1`), не только префикс.

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
   - Кешируются read-проекции (`*Summary`, `*View`)? Кеш агрегата целиком (`Order{Items, Payment}`) → `R-CACHE-WHERE-X2`.
   - Write-path Handler (`CreateOrder`, `ConfirmPayment`) делает cache-read → `R-CACHE-WHERE-X1`.
   - Money-данные (`Balance`, `CreditLimit`) без TTL и evict → `R-CACHE-WHERE-X3`.
   - Кеш результата ABAC-проверки → `R-CACHE-WHERE-X5` (security risk при изменении ролей).

   ### `R-CACHE-CFG-*` — конфигурация
   - Backend — `redis/go-redis/v9`? `sync.Map` / ristretto в multi-instance проде → `R-CACHE-CFG-X2`.
   - Сериализация — `encoding/json`? `encoding/gob` → `R-CACHE-CFG-X1` (security risk + fragility).
   - Per-cache TTL через `CacheConfig`? Один глобальный `DEFAULT_TTL` → `R-CACHE-CFG-X3`.
   - `nil`-имплементация кеш-порта вместо explicit `NoopCache` → `R-CACHE-CFG-X4`.
   - Тесты — Testcontainers Redis (`testcontainers-go`)? Мок cache-порта теряет поведение TTL/eviction → замечание к `R-CACHE-CFG-5`.

   ### `R-CACHE-KEY-*` — ключи
   - Namespace-префикс kebab-case (`"customer-profiles:" + id`) присутствует? Без префикса → `R-CACHE-KEY-X3`.
   - Составные ключи — явный join через разделитель? `fmt.Sprintf("%v", args...)` → `R-CACHE-KEY-X1`.
   - Указатель на struct (`fmt.Sprintf("%p", &req)`) в ключе → `R-CACHE-KEY-X2`.
   - Email/phone/токен plain-text в ключе → `R-CACHE-KEY-X4` (хешируй через `crypto/sha256`).

   ### `R-CACHE-TTL-*` — TTL
   - Каждый именованный кеш имеет explicit TTL? `c.redis.Set(ctx, key, val, 0)` → `R-CACHE-TTL-X1` (infinite в go-redis).
   - TTL > 24h для бизнес-данных → `R-CACHE-TTL-X2`.
   - Money-кеш без TTL или TTL > 1м без строгой invalidation → `R-CACHE-TTL-X3`.
   - TTL берётся из `CacheConfig`, не хардкодится в методе?

   ### `R-CACHE-INV-*` — invalidation
   - На каждом write-методе того же ресурса — evict затронутых ключей? Ошибка evict-а логируется `slog.WarnContext`, не возвращается (best-effort)?
   - Write меняет несколько кешей → evict всех затронутых?
   - При доменных событиях — invalidation как side-effect обработчика?
   - `c.redis.Del(ctx, "namespace:*")` (wildcard) или `FLUSHDB` → `R-CACHE-INV-X1`.
   - Только TTL для money/orders → `R-CACHE-INV-X2`.
   - Eventual consistency не задекларирована в OpenAPI → `R-CACHE-INV-X3`.

   ### `R-CACHE-PATTERN-*` — паттерны
   - Один паттерн на именованный кеш? Миксуется cache-aside + write-through для одного namespace → `R-CACHE-PATTERN-X2`.
   - Write-behind для money/critical: запись в кеш, в БД асинхронно → `R-CACHE-PATTERN-X1` (crash до flush = потеря данных).
   - refresh-ahead реализован через горутину (`time.NewTicker` на 80% TTL)?

   ### `R-CACHE-STAMP-*` — stampede
   - Single-instance: используется `singleflight.Group` для защиты hot-ключей?
   - Multi-instance Redis: distributed lock через `c.redis.SetNX(ctx, lockKey, "1", 5*time.Second)`? `sync.Mutex` / `sync.Map` как защита distributed-кеша → `R-CACHE-STAMP-X2`.
   - Hot endpoints (>100 RPS) без stampede-защиты → `R-CACHE-STAMP-X1`.

   ### `R-CACHE-OBS-*` — observability
   - `cache_hits_total`, `cache_misses_total`, `cache_evictions_total` через `promauto.NewCounterVec` с label `cache`?
   - Отсутствие этих метрик → `R-CACHE-OBS-X1`.
   - Eviction логируется на `slog.DebugContext`, не `InfoContext`?
   - Hit rate alert (< 70% для долгих кешей) задекларирован в конфиге мониторинга?

4. **Cross-check:** кешируемые read-проекции → `ucp-go-cqrs-review`; cache-порт в `core/` → `ucp-go-hexagonal-review`; hit-rate метрика/алерты → `ucp-go-observability-review`; ABAC-кеш → `ucp-auth-review` (`AUTH-5`). Проверь наличие `errcheck`+`errorlint` в линтере (`.golangci.yml`).

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `encoding/gob` сериализация (`R-CACHE-CFG-X1`), кеш ABAC-результата (`R-CACHE-WHERE-X5`), money без TTL/invalidation (`R-CACHE-WHERE-X3`/`R-CACHE-TTL-X3`), write-behind для money (`R-CACHE-PATTERN-X1`), `sync.Mutex` как distributed-lock (`R-CACHE-STAMP-X2`), sensitive plain-text в ключе (`R-CACHE-KEY-X4`).
   - **Предупреждение** — кеш агрегата целиком (`R-CACHE-WHERE-X2`), `sync.Map` в multi-instance проде (`R-CACHE-CFG-X2`), `0` TTL / TTL > 24h (`R-CACHE-TTL-X1/X2`), `FLUSHDB`/wildcard evict без причины (`R-CACHE-INV-X1`), stampede на hot endpoint без защиты (`R-CACHE-STAMP-X1`).
   - **Замечание** — один глобальный TTL (`R-CACHE-CFG-X3`), микс паттернов (`R-CACHE-PATTERN-X2`), отсутствие `cache_hits_total`/`cache_misses_total` (`R-CACHE-OBS-X1`), мок порта вместо Testcontainers.

## Что не входит

- Какие read-проекции кешировать — `ucp-go-cqrs-review`.
- Cache-порт в `core/` — `ucp-go-hexagonal-review`.
- Hit-rate метрика/алерты — `ucp-go-observability-review`.
- Retry/CB-конфиг — `ucp-go-resilience-review`.

$ARGUMENTS
