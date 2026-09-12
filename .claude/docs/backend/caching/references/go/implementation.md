# Caching — реализация на Go (net/http + chi)

Реализация контракта `../spec.md` (коды `R-CACHE-WHERE-*`, `R-CACHE-CFG-*`, `R-CACHE-KEY-*`,
`R-CACHE-TTL-*`, `R-CACHE-INV-*`, `R-CACHE-PATTERN-*`, `R-CACHE-STAMP-*`, `R-CACHE-OBS-*`) на Go-стеке
(stdlib `net/http` + chi, `redis/go-redis/v9`, `prometheus/client_golang`, `go.opentelemetry.io/otel`).

> **Парадигма.** В Go нет декларативного `@Cacheable` Spring: кеш — явный cache-aside через тонкий
> cache-порт в `core/` + реализацию в `adapters/out/cache/`. Порт — `interface` (Go-идиома Protocol),
> реализация — `redis/go-redis/v9` с JSON-сериализацией. Ошибки — значения (`apperr.Kind`) по контракту
> `../error-handling/references/go/implementation.md`.

Структура слоёв UCP: `core/` (порт + Use Case Handlers), `adapters/out/cache/` (Redis-реализация),
`adapters/out/<domain>/` (репозитории, читают через порт), edge (chi-роутер).

---

## 1. Где кешируем (`R-CACHE-WHERE-*`)

`caching/cache-read-heavy-stable-data` — кешируй read-heavy + редко меняющиеся данные: профили (`CustomerSummary`),
справочники (продуктовый каталог), feature-flags. `caching/money-data-needs-explicit-invalidation` — money-данные (`Balance`,
`CreditLimit`) — только с явной invalidation: TTL 5–30 секунд + evict на каждом write + evict перед
критичным чтением. `caching/cache-aside-is-default` — cache-aside (lazy get-or-load + evict на write) — дефолт.

```go
// core/customer/cache_port.go
type CustomerCache interface {
    GetSummary(ctx context.Context, customerID string) (*CustomerSummary, error)
    SetSummary(ctx context.Context, customerID string, v *CustomerSummary, ttl time.Duration) error
    DeleteSummary(ctx context.Context, customerID string) error
}

// adapters/out/cache/customer_cache.go
func (c *RedisCustomerCache) GetSummary(ctx context.Context, customerID string) (*CustomerSummary, error) {
    raw, err := c.redis.Get(ctx, summaryKey(customerID)).Bytes()
    if errors.Is(err, redis.Nil) {
        return nil, nil
    }
    if err != nil {
        return nil, fmt.Errorf("get customer summary %s: %w", customerID, err)
    }
    var v CustomerSummary
    if err := json.Unmarshal(raw, &v); err != nil {
        return nil, fmt.Errorf("unmarshal customer summary %s: %w", customerID, err)
    }
    return &v, nil
}
```

`caching/no-cache-on-write-path` ❌ Кеш на write-path: `CreateOrder`, `ConfirmPayment` не возвращают «то же значение
для тех же входов» — кешировать нечего.

`caching/cache-projections-not-aggregates` ❌ Кеш доменного агрегата целиком (`Order` с `[]OrderItem`, `Payment`, `Shipment`).
Нарушает границы агрегата; invalidation становится сложной. Кешируй read-проекции (`OrderSummary`),
не `Order`.

`caching/money-data-needs-explicit-invalidation` ❌ Money-данные без TTL и invalidation. `Balance` на час = stale для
операций списания.

`caching/cache-read-heavy-stable-data` ❌ Кеш бизнес-критичного без явной trade-off оценки. Stale balance / orders → рекламация.

`caching/no-caching-authorization-results` ❌ Кеш результата валидации / авторизации. ABAC-проверки выполняются каждый раз;
кеш авторизации = security risk при изменении ролей.

---

## 2. Конфигурация (`R-CACHE-CFG-*`)

`caching/distributed-cache-in-production` — backend — Redis (`redis/go-redis/v9`), не `sync.Map` / `ristretto` в multi-instance
проде (каждый под — свой кеш, нет консистентности).

`caching/values-serialized-as-json` — сериализация — JSON (`encoding/json`), **никогда `encoding/gob`** (привязан к Go, ломается
при изменении структуры; аналог Java native-сериализации).

`caching/explicit-ttl-per-cache` — per-cache explicit TTL: каждый именованный кеш конфигурируется отдельно.

`caching/cache-settings-are-typed` — настройки через `kelseyhightower/envconfig` или собственный `Config`-struct с env-тегами:

```go
// config/config.go
type CacheConfig struct {
    RedisAddr          string        `envconfig:"REDIS_ADDR" required:"true"`
    CustomerSummaryTTL time.Duration `envconfig:"CACHE_CUSTOMER_SUMMARY_TTL" default:"15m"`
    ProductCatalogTTL  time.Duration `envconfig:"CACHE_PRODUCT_CATALOG_TTL"  default:"6h"`
    FeatureFlagsTTL    time.Duration `envconfig:"CACHE_FEATURE_FLAGS_TTL"    default:"60s"`
    BalanceTTL         time.Duration `envconfig:"CACHE_BALANCE_TTL"          default:"15s"`
}
```

`caching/tests-use-real-cache` — в тестах — Testcontainers Redis (`testcontainers-go`), не мок cache-порта (теряется
поведение TTL/eviction):

```go
// adapters/out/cache/customer_cache_test.go
func TestGetSummary_CacheMiss(t *testing.T) {
    ctx := context.Background()
    req := testcontainers.ContainerRequest{
        Image:        "redis:7-alpine",
        ExposedPorts: []string{"6379/tcp"},
        WaitingFor:   wait.ForListeningPort("6379/tcp"),
    }
    container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
        ContainerRequest: req, Started: true,
    })
    require.NoError(t, err)
    defer container.Terminate(ctx)

    host, _ := container.Host(ctx)
    port, _ := container.MappedPort(ctx, "6379")
    rdb := redis.NewClient(&redis.Options{Addr: host + ":" + port.Port()})
    cache := NewRedisCustomerCache(rdb, CacheConfig{CustomerSummaryTTL: 5 * time.Minute})

    got, err := cache.GetSummary(ctx, "cust-42")
    require.NoError(t, err)
    assert.Nil(t, got)
}
```

`caching/values-serialized-as-json` ❌ `encoding/gob` сериализация — security risk и fragility при изменении структур.

`caching/distributed-cache-in-production` ❌ `sync.Map` / in-memory dict в multi-instance проде.

`caching/explicit-ttl-per-cache` ❌ Один глобальный TTL (`DEFAULT_TTL=15m`) для всех кешей — профиль и balance требуют
разного TTL.

`caching/no-cache-without-manager` ❌ Возврат `nil`-имплементации порта — cache-read молча ничего не кеширует (silent skip).
Если Redis недоступен в dev — explicit `NoopCache` с предупреждением при старте.

---

## 3. Ключи (`R-CACHE-KEY-*`)

`caching/cache-name-is-namespace` — namespace через имя кеша как префикс ключа (`"customer-profiles:" + customerID`).
Префикс отделяет пространства в Redis, упрощает evict-by-namespace.

`caching/cache-name-is-namespace` — имена namespace — kebab-case: `customer-profiles`, `product-catalog`, `feature-flags`,
`payment-methods`. Не camelCase, не snake_case.

`caching/explicit-cache-key` — ключ — explicit, не «весь объект»:

```go
// adapters/out/cache/keys.go
func summaryKey(customerID string) string      { return "customer-profiles:" + customerID }
func productKey(productID string) string       { return "product-catalog:" + productID }
func featureFlagKey(name string) string        { return "feature-flags:" + name }
func orderSummaryKey(orderID string) string    { return "order-summaries:" + orderID }
```

`caching/custom-key-generator-when-needed` — для составных ключей (несколько параметров) — явный join через разделитель, задокументированный:

```go
func productBySlugKey(categoryID, slug string) string {
    return "product-catalog:by-slug:" + categoryID + ":" + slug
}
```

`caching/explicit-cache-key` ❌ `fmt.Sprintf("%v", args...)` как ключ — ломается при изменении количества аргументов.

`caching/explicit-cache-key` ❌ Указатель на struct (`fmt.Sprintf("%p", &req)`) в ключе — каждый вызов новый ключ.

`caching/cache-name-is-namespace` ❌ `"shared-cache:" + entityID` — один namespace для `Customer` и `Product`. Теряется
namespacing; evict пересекается; метрики нечитаемы.

`caching/no-sensitive-data-in-keys` ❌ Email/phone/токен в ключе plain-text. Redis-ключи видны в мониторинге. Хешируй:

```go
import "crypto/sha256"

func sensitiveKey(email string) string {
    h := sha256.Sum256([]byte(email))
    return "customer-by-email:" + hex.EncodeToString(h[:])
}
```

---

## 4. TTL (`R-CACHE-TTL-*`)

`caching/explicit-ttl-per-cache` — каждый кеш имеет explicit TTL. Никаких `0` и отсутствия `TTL` в `SET`.

`caching/ttl-matches-data-nature` — типовые значения по характеру данных:

| Тип данных | TTL | Код |
|---|---|---|
| `CustomerSummary`, профили | 15 минут | `CustomerSummaryTTL` |
| `ProductCatalog`, справочники | 6 часов | `ProductCatalogTTL` |
| `FeatureFlags` | 60 секунд | `FeatureFlagsTTL` |
| Money (`Balance`, `CreditLimit`) | 5–30 секунд | `BalanceTTL` |

`caching/explicit-ttl-per-cache` — TTL берётся из конфига (`CacheConfig`), не хардкодится в методе:

```go
func (c *RedisCustomerCache) SetSummary(ctx context.Context, id string, v *CustomerSummary, ttl time.Duration) error {
    raw, err := json.Marshal(v)
    if err != nil {
        return fmt.Errorf("marshal customer summary: %w", err)
    }
    return c.redis.Set(ctx, summaryKey(id), raw, ttl).Err()
}

// вызов из Use Case Handler:
if err := c.cache.SetSummary(ctx, id, summary, c.cfg.Cache.CustomerSummaryTTL); err != nil {
    slog.WarnContext(ctx, "cache set failed", "customer_id", id, "error", err)
}
```

`caching/ttl-matches-data-nature` — при наличии явного invalidation-события (`CustomerUpdated`) TTL можно увеличить (инвалидация
делает основную работу); без надёжной invalidation — TTL короче (компромисс).

`caching/explicit-ttl-per-cache` ❌ `c.redis.Set(ctx, key, val, 0)` — `0` в go-redis трактуется как «без TTL» (infinite).

`caching/ttl-matches-data-nature` ❌ TTL > 24 часов для бизнес-данных. Переживает деплои — в кеше могут оказаться значения
с устаревшей структурой DTO.

`caching/money-data-needs-explicit-invalidation` ❌ Money-кеш без TTL или TTL > 1 минуты без строгой invalidation. Баланс устарел →
клиент потратил то, чего нет.

---

## 5. Invalidation (`R-CACHE-INV-*`)

`caching/write-evicts-affected-caches` — на каждом write-методе того же ресурса — evict затронутых ключей:

```go
// core/customer/update_handler.go
func (h *UpdateCustomerHandler) Handle(ctx context.Context, cmd UpdateCustomerCommand) error {
    if err := h.repo.Update(ctx, cmd); err != nil {
        return err
    }
    if err := h.cache.DeleteSummary(ctx, cmd.CustomerID); err != nil {
        slog.WarnContext(ctx, "cache evict failed", "customer_id", cmd.CustomerID, "error", err)
    }
    return nil
}
```

Ошибку evict-а логируем Warn, но не возвращаем — TTL сделает работу, evict — best-effort.

`caching/write-evicts-affected-caches` — write меняет несколько кешей → evict всех затронутых:

```go
func (h *UpdateProductHandler) Handle(ctx context.Context, cmd UpdateProductCommand) error {
    if err := h.repo.Update(ctx, cmd); err != nil {
        return err
    }
    _ = h.cache.DeleteProduct(ctx, cmd.ProductID)
    _ = h.cache.DeleteProductBySlug(ctx, cmd.CategoryID, cmd.Slug)
    return nil
}
```

`caching/invalidate-on-domain-event` — при доменных событиях (`CustomerUpdatedEvent`) — invalidation как side-effect обработчика:

```go
// adapters/in/events/customer_events_handler.go
func (h *CustomerEventHandler) OnCustomerUpdated(ctx context.Context, e CustomerUpdatedEvent) error {
    return h.cache.DeleteSummary(ctx, e.CustomerID)
}
```

`caching/distributed-invalidation-is-built-in` — distributed invalidation встроена в Redis (общий backend для всех инстансов).
Отдельного pub/sub для evict не нужно.

`caching/no-routine-full-flush` ❌ `FLUSHDB` / удаление по wildcard `DEL customer-profiles:*` без причины. Холодный старт
всего namespace → spike на БД.

`caching/ttl-is-not-consistency` ❌ Полагаться только на TTL для money/orders. «Обновится через 30 секунд» — неприемлемо
при операции списания.

`caching/staleness-is-declared` ❌ Eventual consistency без декларации. Если endpoint может вернуть stale-данные —
зафиксируй в OpenAPI (`description: "Значение актуально с задержкой до 30 секунд"`).

---

## 6. Паттерны (`R-CACHE-PATTERN-*`)

`caching/cache-aside-is-default` — **cache-aside** (lazy get-or-load + evict на write) — дефолт:

```go
// core/customer/query_handler.go
func (h *GetCustomerSummaryHandler) Handle(ctx context.Context, q GetCustomerSummaryQuery) (*CustomerSummary, error) {
    if cached, err := h.cache.GetSummary(ctx, q.CustomerID); err == nil && cached != nil {
        cacheHits.WithLabelValues("customer-profiles").Inc()
        return cached, nil
    }
    cacheMisses.WithLabelValues("customer-profiles").Inc()

    summary, err := h.repo.GetSummary(ctx, q.CustomerID)
    if err != nil {
        return nil, err
    }
    if err := h.cache.SetSummary(ctx, q.CustomerID, summary, h.cfg.Cache.CustomerSummaryTTL); err != nil {
        slog.WarnContext(ctx, "cache set failed", "customer_id", q.CustomerID, "error", err)
    }
    return summary, nil
}
```

`caching/cache-aside-is-default` — **write-through** (явный `Set` на write) — для high read+write одного значения,
когда данные нужны сразу после записи:

```go
func (h *UpdateCustomerHandler) Handle(ctx context.Context, cmd UpdateCustomerCommand) error {
    updated, err := h.repo.UpdateAndReturn(ctx, cmd)
    if err != nil {
        return err
    }
    summary := toSummary(updated)
    if err := h.cache.SetSummary(ctx, cmd.CustomerID, summary, h.cfg.Cache.CustomerSummaryTTL); err != nil {
        slog.WarnContext(ctx, "cache write-through failed", "customer_id", cmd.CustomerID, "error", err)
    }
    return nil
}
```

`caching/cache-aside-is-default` — **refresh-ahead** — для hot-данных (`TopProducts`, главная страница).
Фоновая горутина перезаливает кеш до истечения TTL:

```go
// adapters/background/product_cache_refresher.go
func (r *ProductCacheRefresher) Run(ctx context.Context) {
    ticker := time.NewTicker(r.cfg.Cache.ProductCatalogTTL * 80 / 100)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            if err := r.refresh(ctx); err != nil {
                slog.WarnContext(ctx, "product cache refresh failed", "error", err)
            }
        }
    }
}

func (r *ProductCacheRefresher) refresh(ctx context.Context) error {
    top, err := r.repo.GetTopProducts(ctx, 100)
    if err != nil {
        return err
    }
    return r.cache.SetTopProducts(ctx, top, r.cfg.Cache.ProductCatalogTTL)
}
```

`caching/cache-aside-is-default` ❌ **Write-behind** для money/critical-данных. Запись в кеш сейчас, в БД асинхронно —
crash до flush = потеря данных.

`caching/cache-aside-is-default` ❌ Смешение паттернов на одном кеше. Если `order-summaries` использует cache-aside
в одном хендлере и write-through в другом — invalidation-логика ломается. Один cache = один паттерн.

---

## 7. Cache stampede (`R-CACHE-STAMP-*`)

`caching/stampede-protection` — для single-instance (dev, in-process кеш) — `sync.Map` или `singleflight`:

```go
// adapters/out/cache/singleflight_wrapper.go
import "golang.org/x/sync/singleflight"

type SingleflightCustomerCache struct {
    inner CustomerCache
    group singleflight.Group
}

func (c *SingleflightCustomerCache) GetOrLoad(
    ctx context.Context,
    customerID string,
    loader func() (*CustomerSummary, error),
) (*CustomerSummary, error) {
    v, err, _ := c.group.Do(customerID, func() (any, error) {
        if cached, err := c.inner.GetSummary(ctx, customerID); err == nil && cached != nil {
            return cached, nil
        }
        return loader()
    })
    if err != nil {
        return nil, err
    }
    return v.(*CustomerSummary), nil
}
```

`caching/stampede-protection` — для Redis (multi-instance) — distributed lock через `go-redis` `SetNX`:

```go
func (c *RedisCustomerCache) GetOrLoadLocked(
    ctx context.Context,
    customerID string,
    loader func() (*CustomerSummary, error),
    ttl time.Duration,
) (*CustomerSummary, error) {
    if cached, _ := c.GetSummary(ctx, customerID); cached != nil {
        return cached, nil
    }

    lockKey := "lock:customer-profiles:" + customerID
    acquired, err := c.redis.SetNX(ctx, lockKey, "1", 5*time.Second).Result()
    if err != nil || !acquired {
        select {
        case <-ctx.Done():
            return nil, ctx.Err()
        case <-time.After(50 * time.Millisecond):
        }
        return c.GetSummary(ctx, customerID)
    }
    defer c.redis.Del(ctx, lockKey)

    summary, err := loader()
    if err != nil {
        return nil, err
    }
    _ = c.SetSummary(ctx, customerID, summary, ttl)
    return summary, nil
}
```

`caching/stampede-protection` — для hot-ключей (`product-catalog:top-100`) — refresh-ahead (см. `caching/cache-aside-is-default`).
Stampede исключён по дизайну — кеш никогда не пустой.

`caching/stampede-protection` ❌ Игнорировать stampede для hot endpoints под нагрузкой (>100 RPS). Общий cache miss
→ DB latency-инцидент.

`caching/stampede-protection` ❌ `sync.Mutex` / `sync.Map` как защита distributed-кеша. Mutex в одном поде не виден
другим инстансам.

---

## 8. Observability (`R-CACHE-OBS-*`)

`caching/cache-metrics-enabled` — метрики hits/misses/evictions через `prometheus/client_golang` (`promauto`):

```go
// adapters/out/cache/metrics.go
var (
    cacheHits = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cache_hits_total",
            Help: "Cache hits",
        },
        []string{"cache"},
    )
    cacheMisses = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cache_misses_total",
            Help: "Cache misses",
        },
        []string{"cache"},
    )
    cacheEvictions = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cache_evictions_total",
            Help: "Cache evictions (explicit deletes)",
        },
        []string{"cache"},
    )
)
```

Вызов после `Delete*`:

```go
func (c *RedisCustomerCache) DeleteSummary(ctx context.Context, customerID string) error {
    err := c.redis.Del(ctx, summaryKey(customerID)).Err()
    if err == nil {
        cacheEvictions.WithLabelValues("customer-profiles").Inc()
        slog.DebugContext(ctx, "cache evict", "cache", "customer-profiles", "key", customerID)
    }
    return err
}
```

`caching/cache-metrics-enabled` — hit rate = главная метрика: `cache_hits_total / (cache_hits_total + cache_misses_total)`.
Alert при hit rate < 70% для долго существующих кешей — означает неподходящий TTL или слишком частые evict.

`caching/eviction-logged-at-debug` — eviction логируется на уровне `slog.DebugContext`, не `InfoContext`. Logline на каждый
delete будет шумным в проде.

`caching/cache-metrics-enabled` — Redis-side метрики (`redis_memory_used_bytes`, `redis_keys_total`, `redis_cluster_state`) —
через Redis Exporter для Prometheus, не в коде приложения.

`caching/cache-metrics-enabled` ❌ Отсутствие cache-метрик. Без `cache_hits_total` / `cache_misses_total` SRE не увидит
«hit rate 5%, кеш бесполезен».

---

## Чеклист подключения к новому сервису (Go)

- [ ] Кеш-порт — `interface` в `core/<domain>/cache_port.go`; реализация — `adapters/out/cache/`.
- [ ] Кешируются read-проекции (`*Summary`, `*View`), не агрегаты; не write-path; не результаты авторизации.
- [ ] Money-данные: TTL 5–30с + evict на каждом write; evict перед критичным чтением.
- [ ] Backend — Redis (`redis/go-redis/v9`); JSON-сериализация (`encoding/json`); не `gob`, не in-memory в проде.
- [ ] Per-cache TTL через `CacheConfig` из `envconfig`; не хардкод; не глобальный дефолт.
- [ ] TTL никогда `0`; не больше 24ч для бизнес-данных; money ≤ 1м без строгой invalidation.
- [ ] Ключи: namespace-префикс kebab-case, explicit, sensitive-данные хешированы (`sha256`).
- [ ] Evict на write того же ресурса; нет `FLUSHDB` без явной необходимости.
- [ ] Eventual consistency задекларирована в OpenAPI (`description: "Задержка до X секунд"`).
- [ ] Один паттерн на кеш (cache-aside или write-through); нет write-behind для money.
- [ ] Stampede: `singleflight` для single-instance; `SetNX`-lock для Redis multi-instance; refresh-ahead для hot-ключей.
- [ ] `cache_hits_total`, `cache_misses_total`, `cache_evictions_total` через `promauto`; label `cache` = имя namespace.
- [ ] Alert: hit rate < 70% для долгих кешей.
- [ ] Evict логируется на `slog.DebugContext`; не `InfoContext`.
- [ ] В тестах — Testcontainers Redis, не мок порта (проверяется поведение TTL/eviction).
