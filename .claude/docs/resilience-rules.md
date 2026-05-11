# Resilience — индекс правил

> **Что это.** Сжатый индекс правил `resilience-style-guide.md`: код + формулировка, по разделам. Рабочий вход
> для скиллов — review цитирует код в findings, design сверяется по чек-листу. **Полная версия
> с примерами, code-блоками, обоснованием и под-пунктами — `resilience-style-guide.md`**; открывай её точечно по
> нужному разделу, когда индекса не хватает (под-списки и code-сниппеты сюда не вынесены).
> Коды: `<PREFIX>-<N>` — обязательно, `<PREFIX>-X<N>` — запрещено.

## 1. Где какая защита
**MUST:**
- **R-RES-WHERE-1.** Защита **outbound HTTP** к внешним системам (платежи, фискализация, страхование, любые сторонние API) — обязательна полным набором: timeout + CircuitBreaker + Bulkhead + (опционально) Retry. Без CB первый «slow burn» внешней системы расплескивается на весь thread pool сервиса.
- **R-RES-WHERE-2.** Защита **internal service-to-service** (вызовы между нашими микросервисами) — обязательны timeout + CircuitBreaker. Bulkhead — по необходимости (если сервис тяжёлый или критичный).
- **R-RES-WHERE-3.** Защита **schedulers и outbox-relay** делается через **task-queue retry** (DB-driven, см. `R-RES-RE-5`), не через Resilience4j. Resilience4j покрывает in-memory транзиенты <5s; task-queue — durable retry для долгих отказов (>30s) и переживания рестарта сервиса.
- **R-RES-WHERE-4.** Защита **inbound (наш REST)** — это `RateLimiter` и edge-уровень. По умолчанию — на API Gateway (Spring Cloud Gateway, Kong, Istio), не в каждом сервисе. `@RateLimiter` на контроллерах допустим только если gateway недоступен (legacy-инсталляция).
**MUST NOT:**
- **R-RES-WHERE-X1.** Resilience4j вокруг локальных операций (репозиторий, JOOQ, in-memory вычисления). CB не имеет смысла — нет транзиентов «иногда работает, иногда нет», и любой failure на этом уровне — реальная ошибка, не отказ среды.

## 2. Per-system isolation
**MUST:**
- **R-RES-ISO-1.** На **каждую внешнюю систему** — отдельный `OkHttpClient` (или `RestClient` / `WebClient`) **с собственным**:
- **R-RES-ISO-2.** Connection pool sizing — per-system: pool = `maxConcurrent` × 1.2 (запас на keep-alive idle). Total pool size всех систем ≤ HikariCP размер пула / 2 (чтобы внешние клиенты не съели соединения с БД).
- **R-RES-ISO-3.** Имя bean'а и инстансов R4J — **`<system>`** одинаково для CB / Bulkhead / Retry: `sber`, `odnakassa`, `insurance`, `receipt`. Это позволяет адаптеру использовать одно имя в `@CircuitBreaker(name = "sber")`, `@Bulkhead(name = "sber")`, `@Retry(name = "sber")`.
**MUST NOT:**
- **R-RES-ISO-X1.** Один shared `OkHttpClient` или `Dispatcher` на несколько внешних систем. При зависании одной системы её застрявшие коннекты блокируют ресурсы других.
- **R-RES-ISO-X2.** Дефолтные настройки `OkHttpClient.Builder()` без явного pool/dispatcher — приходит global defaults (200 idle), shared между всеми. Анти-паттерн.

## 3. Timeouts
**MUST:**
- **R-RES-TO-1.** Timeout hierarchy: `connectTimeout < readTimeout < callTimeout`.
- **R-RES-TO-2.** Timeouts конфигурируются per-system через `<system>ClientSettings` (`@ConfigurationProperties("client.<system>")`): Расхождения от типовых (`R-RES-TO-1`) — комментарием в yml с обоснованием.
- **R-RES-TO-3.** Если на эндпоинте есть `traceparent` (см. `R-HDR-4` REST guide) и TimeBudget — адаптер уважает оставшееся время. При `remainingBudget < callTimeout` — `RequestsInterceptor` ставит client-side timeout = `min(callTimeout, remainingBudget - 100ms buffer)`.
**MUST NOT:**
- **R-RES-TO-X1.** Один глобальный `OkHttpClient.Builder().build()` без timeouts — дефолт ∞. Зависание = thread навсегда.
- **R-RES-TO-X2.** `callTimeout < readTimeout` или `callTimeout < connectTimeout`. Внутреннее противоречие: первый сработает раньше, второй никогда.
- **R-RES-TO-X3.** `readTimeout > 60s` для синхронного вызова из HTTP-handler'а. Перевести в task-queue (`R-RES-WHERE-3`) или async-pattern (`R-ASYNC-1` REST guide).

## 4. Circuit Breaker
**MUST:**
- **R-RES-CB-1.** `@CircuitBreaker(name = "<system>")` — на **public-методе out-adapter**, который вызывает внешнюю систему. Не на generated client (см. `R-RES-OAS-2`), не на handler'е, не на репозитории.
- **R-RES-CB-2.** Sliding window — **count-based** (`COUNT_BASED`, не `TIME_BASED`) для outbound в БД-нагруженных сервисах. Размер окна: `slidingWindowSize: 50` (типовое). Минимум вызовов до открытия: `minimumNumberOfCalls: 10`.
- **R-RES-CB-3.** Failure rate threshold: `50%` (по умолчанию). Понижение до `30%` оправдано только для критичных систем (платежи): «лучше быстро открыть, чем тянуть».
- **R-RES-CB-4.** `waitDurationInOpenState`: `30s` (типовое). За это время мы не делаем ни одного call'а — строго fast-fail. После — half-open с `permittedNumberOfCallsInHalfOpenState: 3`. Если все 3 успешны — closed; иначе — назад в open.
- **R-RES-CB-5.** Slow call rate threshold: `slowCallDurationThreshold: <readTimeout> / 2`. Это срабатывает раньше, чем сама ошибка по timeout — ловит «system is slow but not yet broken».
- **R-RES-CB-6.** При open-state CB — выбрасывается `CallNotPermittedException` (Resilience4j). Адаптер маппит её в port-specific exception (`PaymentPortException.SystemUnavailable`), а handler — в `503 Service Unavailable` или `409 Conflict` (зависит от UC).
**MUST NOT:**
- **R-RES-CB-X1.** `@CircuitBreaker` на репозитории, JOOQ-вызове, внутреннем сервисе. Локальный код не имеет «транзиентного» режима.
- **R-RES-CB-X2.** Custom CB на try/catch + `AtomicInteger` failure counter. Изобретать собственный — гарантированный bug-source. Resilience4j отлажен, integrated с metrics.
- **R-RES-CB-X3.** `@CircuitBreaker` без `name` или с одним общим `name = "default"` для разных систем. Sber и OdnaKassa делят CB-state — открытие одной закрывает другую.

## 5. Retry
**MUST:**
- **R-RES-RE-1.** `@Retry(name = "<system>")` допустим **только** при одном из условий: 1. Метод — read (GET-эквивалент): `findOrder`, `getStatus`. Чтение идемпотентно. 2. Команда выполняется с `Idempotency-Key` (см. `AUTH-19`). Внешняя система обязана сама дедуплицировать.
- **R-RES-RE-2.** Конфиг retry:
- **R-RES-RE-3.** `max-attempts: 3` (включая первую попытку). `5` — верхний предел. Больше — это уже task-queue.
- **R-RES-RE-4.** Граница in-memory retry vs task-queue:
- **R-RES-RE-5.** Task-queue retry — отдельный паттерн через таблицу `*_task` с полями `status`, `retry_count`, `next_attempt_at`, `last_error`. Scheduler poll'ит каждые `5s`, фильтрует по `status='IN_PROGRESS' AND next_attempt_at <= now()`. После N неудачных попыток — `status='FAILED'` + alert. Пример: `OrderConfirmationTask`, `ReceiptCreationTask`.
**MUST NOT:**
- **R-RES-RE-X1.** `@Retry` на write-методе без `Idempotency-Key`. На 5xx ответ может быть «не дошло» или «дошло и завершилось, ответ потерялся». Retry = двойная операция = двойной платёж.
- **R-RES-RE-X2.** `@Retry` на `4xx`-ответы. Это контрактные ошибки клиента — повтор не поможет.
- **R-RES-RE-X3.** `@Retry` без `enable-exponential-backoff`. Линейный retry = 3 запроса подряд за 1.5s, удваивает нагрузку на и без того лежачую внешнюю систему.
- **R-RES-RE-X4.** `Spring Retry` (`@Retryable` из `spring-retry`) для outbound. Legacy-механизм без интеграции с CB и Bulkhead. Использовать Resilience4j.

## 6. Bulkhead
**MUST:**
- **R-RES-BH-1.** `@Bulkhead(name = "<system>")` — обязательный слой **отдельно** от connection pool. Connection pool ограничивает TCP-соединения; bulkhead — concurrent invocations (Java threads). Это два разных уровня защиты:
- **R-RES-BH-2.** Тип — **semaphore-based** (`type: SEMAPHORE`), не `thread-pool`. Причина: thread-pool bulkhead создаёт собственный пул и теряет MDC/SecurityContext без явного контекстного wrapping. Semaphore работает в текущем thread.
- **R-RES-BH-3.** Sizing: `maxConcurrentCalls = <pool max-concurrent> × 0.8`. Запас 20% — bulkhead должен срабатывать **раньше** исчерпания pool'а. `maxWaitDuration: 100ms` (короткое ожидание, иначе теряется fail-fast смысл).
**MUST NOT:**
- **R-RES-BH-X1.** Thread-pool bulkhead (`type: THREADPOOL`) для outbound. Создаёт second pool, MDC/Security теряются без `@WithSpan` или ручного DelegatingSecurityContextExecutor. Semaphore-based достаточен.

## 7. Fallback
**MUST:**
- **R-RES-FB-1.** Fallback допустим в трёх случаях:
- **R-RES-FB-2.** Контракт fallback-метода: same return type, дополнительный last-параметр `Throwable` (или конкретное исключение). Сигнатура:
**MUST NOT:**
- **R-RES-FB-X1.** Fallback с `null` / `0` / пустой `Money` для money-операций. Возврат `Money.ZERO` за «не удалось списать» = бизнес-баг.
- **R-RES-FB-X2.** Fallback, который тихо проглатывает ошибку и возвращает «success». Клиент не узнает, что операция не выполнена, пока не наступит несоответствие в данных.
- **R-RES-FB-X3.** Fallback, делающий другой outbound-вызов (например, во второй провайдер платежей) без обёртки этого второго вызова в свой CB. Cascading failure.

## 8. Конфигурация
**MUST:**
- **R-RES-CFG-1.** Конфиг Resilience4j — через `application.yml` (declarative), не через `@Bean CustomCircuitBreakerConfig`. Это позволяет менять параметры через Spring Cloud Config / Vault без redeploy.
- **R-RES-CFG-2.** Defaults — в секции `default`, переопределения — per-instance:
- **R-RES-CFG-3.** Имена instances — same as system: `sber`, `odnakassa`, `insurance`, `receipt`. Совпадают с именами beans (`R-RES-ISO-3`).
**MUST NOT:**
- **R-RES-CFG-X1.** Программная конфигурация через `CircuitBreakerConfig.custom()...` без причины. Скрытая конфигурация, не управляется через Cloud Config.

## 9. Связка с OpenAPI generator
**MUST:**
- **R-RES-OAS-1.** Аннотации `@CircuitBreaker` / `@Retry` / `@Bulkhead` — на **public-методе out-adapter класса**, который оборачивает вызов generated client. Не на generated interface, не в `executeCall<T>`-helper.
- **R-RES-OAS-2.** Для **новых сервисов** — `openapi-generator` target = `spring-restclient` (Spring 6.1+). Это даёт:
- **R-RES-OAS-3.** OpenAPI-спецификация внешнего API хранится в `<system>-client-generator/src/main/resources/openapi/<system>.openapi.yaml`. Codegen в `build/generated/sources/openapi/`, не коммитится. Регенерация — на `compileJava`.
- **R-RES-OAS-4.** Между generated interface и port-интерфейсом из `core/` — **обязательно** mapper (Plain Java или MapStruct), который переводит generated DTO в domain-команды. Generated DTO — детали транспорта, не доменные типы. Адаптер использует mapper, не возвращает generated DTO наверх.
**MUST NOT:**
- **R-RES-OAS-X1.** Аннотации на generated interface (`SberOrderServicesApi`). Регенерация затрёт.
- **R-RES-OAS-X2.** `@CircuitBreaker` в `executeCall<T>` helper с backendName-строкой как параметром. Теряется compile-time проверка имени, ошибки на runtime («unknown circuit breaker «sbr»»).
- **R-RES-OAS-X3.** Возврат generated DTO из public-метода out-adapter (`PaymentPort.register` возвращает `SberRegisterResponse`). Доменный port должен возвращать domain-типы.

## 10. Health checks
**MUST:**
- **R-RES-HC-1.** На каждую внешнюю систему — `HealthIndicator` бин: `SberHealthIndicator implements HealthIndicator`.
- **R-RES-HC-2.** Health-probe — **cached**, TTL `30s` (типовое). Не каждый actuator-call ходит в Sber. Реализация: `@Cacheable("health.sber")` или ручной `Instant lastProbe + Health lastResult`.
- **R-RES-HC-3.** Probe-метод — **light**: `GET /health` или `OPTIONS /` (если внешняя система не имеет health-endpoint), не реальный бизнес-вызов. Health-call не должен дёргать `register` или `confirmPayment`.
- **R-RES-HC-4.** Health отражается в `/actuator/health/<system>`. K8s `livenessProbe` смотрит на `/actuator/health/liveness` (overall), `readinessProbe` — на `/actuator/health/readiness` (включая внешние). Если Sber down — pod может вылететь из Service backend pool.
**MUST NOT:**
- **R-RES-HC-X1.** Sync-probe на каждый `/actuator/health` запрос (без кеша). При высокочастотных K8s probes (каждые 5s) это DDoS внешней системы силами наших же health-check'ов.
- **R-RES-HC-X2.** Health-probe, делающий business-операцию (`registerTestOrder`, `getRealTransactions`). Изменяет состояние, нагружает систему, плодит test-данные.

## 11. Async и polling
**MUST:**
- **R-RES-ASYNC-1.** Если внешняя система требует polling (как страхование из bus-tickets — «отправили запрос → ждём результат»), polling реализуется через **task-queue**, не через `Thread.sleep` в синхронном handler'е:
- **R-RES-ASYNC-2.** В sync-методе адаптера допустим `Thread.sleep` только если total wait `<2s` (короткий transient retry с фиксированным backoff). Иначе — task-queue.
- **R-RES-ASYNC-3.** Для async outbound (`CompletableFuture`-возврат из adapter) — `@TimeLimiter(name = "<system>")` обязателен. Отдельная аннотация (Resilience4j Retry/Bulkhead/CB не поддерживают timeout sами для CompletableFuture).
**MUST NOT:**
- **R-RES-ASYNC-X1.** `Thread.sleep(N)` в цикле в синхронном handler'е, опрашивающем внешнюю систему. Блокирует worker-thread на N×iterations секунд. При нагрузке исчерпает thread-pool за минуты.
- **R-RES-ASYNC-X2.** Любая `Thread.sleep > 5s` — это запах «должно было быть task-queue».

## 12. Observability
**MUST:**
- **R-RES-OBS-1.** Resilience4j metrics — через Micrometer (`resilience4j-micrometer` dependency). Автоматически экспортирует:
- **R-RES-OBS-2.** OTel-spans на adapter-методах — атрибут `circuit_breaker.state` (current state в момент вызова) и `external.system` (имя системы). Это даёт связку «slow trace → CB был half-open».
- **R-RES-OBS-3.** Логирование — структурированное (см. observability-style-guide, в планах). При каждом state-transition CB — лог уровня WARN с system, prev_state, new_state, failure_rate. Не на каждый успешный call.
**MUST NOT:**
- **R-RES-OBS-X1.** Отключение metrics через `management.metrics.enable.resilience4j=false` без причины. Без них SRE не увидит «у нас CB Sber стабильно half-open» до прода.

## 13. Антипаттерны
