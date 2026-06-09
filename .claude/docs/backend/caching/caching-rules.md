# Caching — индекс правил (язык-нейтральный)

> **Что это.** Сжатый индекс правил: код + интент, по разделам — **общий контракт для всех языков**.
> Рабочий вход скиллов: review цитирует код, design сверяется по чек-листу.
> **Реализация по языкам** — `java/caching-style-guide.md` (Spring Cache + Redis) и
> `python/caching-style-guide.md` (redis.asyncio / aiocache, явный cache-aside); открывай нужный точечно.
> Коды: `R-CACHE-<GROUP>-<N>` — обязательно, `R-CACHE-<GROUP>-X<N>` — запрещено. **Коды общие для всех языков** —
> меняется механизм (`@Cacheable`/`@CacheEvict` ↔ явный cache-aside / `aiocache`-декораторы); принципы (TTL, JSON, invalidation) одни.

## 1. Где кешируем
**MUST:**
- **R-CACHE-WHERE-1.** Кешируй **read-heavy + редко меняющиеся** данные:
- **R-CACHE-WHERE-2.** Кеш **денежных данных** (баланс, лимиты, available credit) допустим, но только с **явной invalidation strategy**: TTL коротким (5–30 секунд), cache-evict на каждом write-методе того же ресурса, для критичных операций — `cache.evict()` перед чтением.
- **R-CACHE-WHERE-3.** Cache-aside (lazy load) — дефолтный паттерн для большинства случаев. Read проходит через cache-read, write делает cache-evict или явный `cache.evict()`.
**MUST NOT:**
- **R-CACHE-WHERE-X1.** **Кеш на write-path.** cache-read на `createOrder()`, `confirmPayment()` — нонсенс, write-операции не возвращают «то же значение для тех же входов».
- **R-CACHE-WHERE-X2.** **Кеширование доменного агрегата целиком.** cache-read на `OrderRepository.findById(id)` → `Order` aggregate с `List<OrderItem>` + `Payment` + `Shipment`. Нарушает границы агрегата (агрегат сам управляет своей целостностью), агрегат может содержать sensitive-данные, и invalidation становится сложной (любой child-update должен evict-ить parent). Кешируй **read-проекции** (`OrderSummary`), не агрегаты.
- **R-CACHE-WHERE-X3.** **Money-данные без TTL и invalidation.** Кешировать баланс пользователя на 1 час = «потратил, но баланс показывает старый» — рекламация и инцидент.
- **R-CACHE-WHERE-X4.** Кеш **бизнес-критичных** данных только для performance-оптимизации, без явной trade-off оценки. Stale-data для money / orders = inconsistent UX.
- **R-CACHE-WHERE-X5.** Кеш **результата валидации / авторизации**. JWT-валидация имеет встроенный JWK кеш (5 минут, см. `AUTH-5`); ABAC-проверки делаются каждый раз — кеш авторизации = security risk при изменении roles.

## 2. Конфигурация
**MUST:**
- **R-CACHE-CFG-1.** В прод-сервисах cache backend — **Redis**, не in-memory cache. Причины:
- **R-CACHE-CFG-2.** Сериализация значений — **JSON** (JSON-сериализатор), **никогда** Java native (native-сериализация (небезопасно)). Причины:
- **R-CACHE-CFG-3.** **Per-cache configuration** — каждый именованный кеш имеет explicit TTL. Не полагайся на default-конфиг для всех кешей; разные данные требуют разного TTL.
- **R-CACHE-CFG-4.** Cache settings — через типизированный конфиг (см. `R-VLD-CFG-1`): В конфиг:
- **R-CACHE-CFG-5.** В тестах — in-memory cache либо `Testcontainers` Redis. Не моки `Cache`-интерфейса (теряется поведение TTL/eviction).
**MUST NOT:**
- **R-CACHE-CFG-X1.** native-сериализация (небезопасно) — security risk, см. `R-CACHE-CFG-2`.
- **R-CACHE-CFG-X2.** in-memory cache (фреймворк default `simple`) в multi-instance проде. Каждый pod = свой кеш, нет консистентности.
- **R-CACHE-CFG-X3.** Один глобальный TTL для всех кешей. Разные данные (профиль / справочники / feature-flags) требуют разного TTL — конкретные значения в биндинге.
- **R-CACHE-CFG-X4.** включение кеша без CacheManager-бина. фреймворк создаст no-op cache, cache-read молча ничего не кеширует — silent skip.

## 3. Ключи
**MUST:**
- **R-CACHE-KEY-1.** **Namespace через имя кеша:** `cacheNames = "user-profiles"` — фреймворк сам префиксует (Redis key: `user-profiles::42`). Префикс отделяет кеши в Redis, упрощает evict-by-namespace.
- **R-CACHE-KEY-2.** Имена cache (slug-style, kebab-case): `user-profiles`, `payment-methods`, `feature-flags`. Не camelCase, не PascalCase.
- **R-CACHE-KEY-3.** Ключ внутри cache — через SpEL **explicit**:
- **R-CACHE-KEY-4.** Кастомный генератор ключей — только для **очень сложных** ключей (где SpEL нечитаем). Реализация: Использование: явное указание генератора ключей.
**MUST NOT:**
- **R-CACHE-KEY-X1.** Дефолтный generator (без `key`-параметра) для методов с **несколькими параметрами**. фреймворк сериализует все аргументы через составной ключ — выглядит как `[arg1, arg2]`, легко ломается при изменении сигнатуры. Указывай `key = "..."` явно.
- **R-CACHE-KEY-X2.** `Object.toString()` или подобное в ключе. Если параметр — DTO с `Object.toString()` дефолтным (`UserProfile@1a2b3c`) — каждый вызов = новый ключ.
- **R-CACHE-KEY-X3.** Один общий cache для разных entity (`cacheNames = "shared-cache"`). Теряется namespacing, evict пересекается, метрики нечитаемы.
- **R-CACHE-KEY-X4.** Encoding sensitive данных в ключе (email, phone, токены) plain-text. Redis-keys видны в logs, monitoring tools. Hash значение (`Hashing.sha256().hashString(email)`) если ключ обязан содержать.

## 4. TTL
**MUST:**
- **R-CACHE-TTL-1.** **Каждый cache имеет explicit TTL.** Никаких infinite-кешей.
- **R-CACHE-TTL-2.** Типовые значения по характеру данных:
- **R-CACHE-TTL-3.** TTL — через конфиг, не хардкод в коде. Это позволяет SRE/admin поднимать/понижать TTL под нагрузку без redeploy.
- **R-CACHE-TTL-4.** Если cached data имеет **естественный invalidation event** (например `orderConfirmed` → invalidate `OrderSummary`) — TTL longer, invalidation does the heavy lifting. Если invalidation не реализуема — TTL коротким (compromise).
**MUST NOT:**
- **R-CACHE-TTL-X1.** Cache с TTL = 0 или infinite. 0 часто трактуется как «no TTL» = forever. Forever в Redis при достижении max-memory приведёт к eviction по LRU/LFU без вашего контроля.
- **R-CACHE-TTL-X2.** TTL **больше 24 часов** для бизнес-данных. Сервис рестартует чаще раза в сутки (deploy), и долгий TTL переживает релизы — могут быть закешированные значения с устаревшей структурой DTO.
- **R-CACHE-TTL-X3.** Money-кеш **без TTL** или TTL > 1 минута без strict invalidation. См. `R-CACHE-WHERE-X3`.

## 5. Invalidation
**MUST:**
- **R-CACHE-INV-1.** На каждом **write-методе** того же агрегата — cache-evict на затронутые кеши:
- **R-CACHE-INV-2.** Если write меняет **несколько кешей** — композитная cache-операция (несколько evict разом):
- **R-CACHE-INV-3.** При **доменных событиях** (`UserUpdatedEvent`) — invalidation через обработчик события: Это паттерн «invalidation as side-effect of domain event», независимый от того, какой именно use case вызвал изменение.
- **R-CACHE-INV-4.** Для **distributed cache invalidation** (Redis pub/sub при изменении на одной из инстансов) — встроенно в Redis backend, отдельной обвязки не нужно.
**MUST NOT:**
- **R-CACHE-INV-X1.** **сброс всего кеша** без причины. Сбрасывает весь cache одной операцией — на холодном старте остальные пользователи получают cache miss → нагрузка на БД спайком. Допустимо только при админских операциях (truncate / rebuild).
- **R-CACHE-INV-X2.** Полагаться только на TTL для consistency. «Подождёт минуту и обновится» — приемлемо для еволюционирующих feature-flags, неприемлемо для money / orders.
- **R-CACHE-INV-X3.** **Eventual consistency без явной декларации.** Если кеш может быть stale — это часть контракта endpoint, документируй в OpenAPI (`description: 'Возможна задержка до 30 секунд'`).

## 6. Паттерны
**MUST:**
- **R-CACHE-PATTERN-1.** **Cache-aside (lazy load + write evict)** — дефолтный паттерн.
- **R-CACHE-PATTERN-2.** **Cache-through (write-through)** — для высокочастотных read + write одного значения. На write кеш обновляется явно (`cache.put(...)`), не evict-ится: Используй когда: данные сразу нужны после write (тот же flow продолжает работать с ними).
- **R-CACHE-PATTERN-3.** **Refresh-ahead** — для критичных hot-данных (главная страница, top-100 продуктов). Реализуется через планировщик job, который перезаливает cache до истечения TTL: Гарантирует «no cache miss for hot keys».
**MUST NOT:**
- **R-CACHE-PATTERN-X1.** **Write-behind** (write в кеш, async в БД позже) для money/critical-данных. Crash сервиса до flush в БД = потеря данных.
- **R-CACHE-PATTERN-X2.** Mix паттернов на одном cache. Если cache `user-profiles` использует cache-aside в одном методе и write-through в другом — invalidation logic становится непонятной. Один cache = один паттерн.

## 7. Cache stampede
**MUST:**
- **R-CACHE-STAMP-1.** Для **локального кеша** (in-memory cache) — `sync = true`: фреймворк блокирует все параллельные вызовы на одном ключе до завершения первого.
- **R-CACHE-STAMP-2.** Для **distributed cache** (Redis) — `sync = true` не помогает (lock только within JVM). Опции:
- **R-CACHE-STAMP-3.** Для **hot keys** (top-products) — `Refresh-ahead` (см. `R-CACHE-PATTERN-3`) — фоновое обновление cache до expiry. Stampede исключён по дизайну.
**MUST NOT:**
- **R-CACHE-STAMP-X1.** Игнорировать stampede для hot endpoints. Под рассчитываемой нагрузкой (>100 RPS на endpoint) cache miss всех вместе = DB latency-инцидент.
- **R-CACHE-STAMP-X2.** Использовать `synchronized`-блок в Java для distributed-cache защиты. JVM-lock не виден другим инстансам.

## 8. Observability
**MUST:**
- **R-CACHE-OBS-1.** фреймворк Cache + Redis автоматически экспортирует через система метрик (`spring-boot-starter-management`):
- **R-CACHE-OBS-2.** **Cache hit rate** — основная метрика здоровья кеша. Расчёт: `hits / (hits + misses)`. Алерт при низком **hit rate** (порог — в биндинге) для долго существующих кешей — означает либо неподходящий TTL, либо слишком частые invalidation.
- **R-CACHE-OBS-3.** Логировать **eviction** (cache-evict) на уровне DEBUG с key. Не INFO/WARN — будет шумно.
- **R-CACHE-OBS-4.** Redis-side метрики: `redis_cluster_state`, `redis_memory_used_bytes`, `redis_keys_total{db}` — мониторятся отдельно (Redis Exporter для Prometheus).
**MUST NOT:**
- **R-CACHE-OBS-X1.** Отключение фреймворк Cache metrics (`management.metrics.enable.cache=false`). Без них SRE не увидит «у нас hit rate 5%, кеш бесполезен».

## 9. Антипаттерны
