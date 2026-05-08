# Resilience Style Guide

Свод правил защиты Java/Spring-сервисов команды UCP от отказов внешних систем: timeouts, circuit breaker, retry, bulkhead, fallback, health checks. Каждое правило идентифицируется кодом (`R-RES-CB-3`, `R-RES-OAS-X1`) — скилл `ucp-resilience-review` цитирует эти коды в findings.

Гайд опирается на [Resilience4j](https://resilience4j.readme.io/) ([версия 2.2+](https://github.com/resilience4j/resilience4j)) с интеграцией через `resilience4j-spring-boot3`. Spring Cloud Circuit Breaker как фасад **не используется** — Resilience4j-аннотации проще и не требуют дополнительного слоя абстракции.

Гайд опирается на:
- `BS-17`/`BS-18` (`spring-bootstrap-style-guide.md`) — стек persistence (касается task-queue retry).
- `AUTH-19` (`auth-patterns-style-guide.md`) — `Idempotency-Key` для money-команд (определяет, можно ли retry).
- `R-OAS-*` (REST API style guide) — OpenAPI-first контракт (определяет связку с OpenAPI generator).

---

## Содержание

1. [Где какая защита — `R-RES-WHERE-*`](#1-где-какая-защита)
2. [Per-system isolation — `R-RES-ISO-*`](#2-per-system-isolation)
3. [Timeouts — `R-RES-TO-*`](#3-timeouts)
4. [Circuit Breaker — `R-RES-CB-*`](#4-circuit-breaker)
5. [Retry — `R-RES-RE-*`](#5-retry)
6. [Bulkhead — `R-RES-BH-*`](#6-bulkhead)
7. [Fallback — `R-RES-FB-*`](#7-fallback)
8. [Конфигурация — `R-RES-CFG-*`](#8-конфигурация)
9. [Связка с OpenAPI generator — `R-RES-OAS-*`](#9-связка-с-openapi-generator)
10. [Health checks — `R-RES-HC-*`](#10-health-checks)
11. [Async и polling — `R-RES-ASYNC-*`](#11-async-и-polling)
12. [Observability — `R-RES-OBS-*`](#12-observability)
13. [Антипаттерны — сводка `R-RES-*-X*`](#13-антипаттерны)

---

## 1. Где какая защита

### 1.1 Обязательно

- **R-RES-WHERE-1.** Защита **outbound HTTP** к внешним системам (платежи, фискализация, страхование, любые сторонние API) — обязательна полным набором: timeout + CircuitBreaker + Bulkhead + (опционально) Retry. Без CB первый «slow burn» внешней системы расплескивается на весь thread pool сервиса.
- **R-RES-WHERE-2.** Защита **internal service-to-service** (вызовы между нашими микросервисами) — обязательны timeout + CircuitBreaker. Bulkhead — по необходимости (если сервис тяжёлый или критичный).
- **R-RES-WHERE-3.** Защита **schedulers и outbox-relay** делается через **task-queue retry** (DB-driven, см. `R-RES-RE-5`), не через Resilience4j. Resilience4j покрывает in-memory транзиенты <5s; task-queue — durable retry для долгих отказов (>30s) и переживания рестарта сервиса.
- **R-RES-WHERE-4.** Защита **inbound (наш REST)** — это `RateLimiter` и edge-уровень. По умолчанию — на API Gateway (Spring Cloud Gateway, Kong, Istio), не в каждом сервисе. `@RateLimiter` на контроллерах допустим только если gateway недоступен (legacy-инсталляция).

### 1.2 Запрещено

- **R-RES-WHERE-X1.** Resilience4j вокруг локальных операций (репозиторий, JOOQ, in-memory вычисления). CB не имеет смысла — нет транзиентов «иногда работает, иногда нет», и любой failure на этом уровне — реальная ошибка, не отказ среды.

---

## 2. Per-system isolation

### 2.1 Обязательно

- **R-RES-ISO-1.** На **каждую внешнюю систему** — отдельный `OkHttpClient` (или `RestClient` / `WebClient`) **с собственным**:
  - `ConnectionPool` — ограничивает реальные TCP/HTTP-соединения.
  - `Dispatcher` (только для `OkHttpClient`) — ограничивает максимум одновременных HTTP-запросов.
  - `CircuitBreaker` instance — изолирует состояние «открыт/закрыт».
  - `Bulkhead` instance — изолирует concurrency (см. `R-RES-BH-1`).

  Конфиг в Spring `@Configuration`-классе:
  ```java
  @Bean("sberOkHttpClient")
  OkHttpClient sberOkHttpClient(SberClientSettings settings) {
      var dispatcher = new Dispatcher();
      dispatcher.setMaxRequestsPerHost(settings.maxConcurrent());  // напр. 20
      var pool = new ConnectionPool(settings.maxIdleConnections(), 5, MINUTES);
      return new OkHttpClient.Builder()
          .connectTimeout(settings.connectTimeoutSec(), SECONDS)
          .readTimeout(settings.readTimeoutSec(), SECONDS)
          .callTimeout(settings.callTimeoutSec(), SECONDS)
          .dispatcher(dispatcher)
          .connectionPool(pool)
          .addInterceptor(new RequestsInterceptor(parser))
          .build();
  }
  ```

- **R-RES-ISO-2.** Connection pool sizing — per-system: pool = `maxConcurrent` × 1.2 (запас на keep-alive idle). Total pool size всех систем ≤ HikariCP размер пула / 2 (чтобы внешние клиенты не съели соединения с БД).

- **R-RES-ISO-3.** Имя bean'а и инстансов R4J — **`<system>`** одинаково для CB / Bulkhead / Retry: `sber`, `odnakassa`, `insurance`, `receipt`. Это позволяет адаптеру использовать одно имя в `@CircuitBreaker(name = "sber")`, `@Bulkhead(name = "sber")`, `@Retry(name = "sber")`.

### 2.2 Запрещено

- **R-RES-ISO-X1.** Один shared `OkHttpClient` или `Dispatcher` на несколько внешних систем. При зависании одной системы её застрявшие коннекты блокируют ресурсы других.
- **R-RES-ISO-X2.** Дефолтные настройки `OkHttpClient.Builder()` без явного pool/dispatcher — приходит global defaults (200 idle), shared между всеми. Анти-паттерн.

---

## 3. Timeouts

### 3.1 Обязательно

- **R-RES-TO-1.** Timeout hierarchy: `connectTimeout < readTimeout < callTimeout`.
  - `connectTimeout` — TCP/TLS handshake. Локальные DC: `2s`. Через интернет: `5s`. Никогда `>10s`.
  - `readTimeout` — между байтами ответа. Зависит от слоупока внешней системы. Типовые: `10s` (быстрые API), `30s` (тяжёлые), `60s` (отчёты/экспорт). Если `>60s` — задача для async-pattern (`R-RES-WHERE-3`), не для sync-вызова.
  - `callTimeout` — общий cap на запрос. Всегда `≥ connectTimeout + readTimeout + buffer 1s`.

- **R-RES-TO-2.** Timeouts конфигурируются per-system через `<system>ClientSettings` (`@ConfigurationProperties("client.<system>")`):
  ```yaml
  client.sber:
    connect-timeout: 5s
    read-timeout: 30s
    call-timeout: 36s
    max-concurrent: 20
  client.odnakassa:
    connect-timeout: 5s
    read-timeout: 60s        # OdnaKassa возвращает большие multiset-ответы
    call-timeout: 66s
    max-concurrent: 30
  ```
  Расхождения от типовых (`R-RES-TO-1`) — комментарием в yml с обоснованием.

- **R-RES-TO-3.** Если на эндпоинте есть `traceparent` (см. `R-HDR-4` REST guide) и TimeBudget — адаптер уважает оставшееся время. При `remainingBudget < callTimeout` — `RequestsInterceptor` ставит client-side timeout = `min(callTimeout, remainingBudget - 100ms buffer)`.

### 3.2 Запрещено

- **R-RES-TO-X1.** Один глобальный `OkHttpClient.Builder().build()` без timeouts — дефолт ∞. Зависание = thread навсегда.
- **R-RES-TO-X2.** `callTimeout < readTimeout` или `callTimeout < connectTimeout`. Внутреннее противоречие: первый сработает раньше, второй никогда.
- **R-RES-TO-X3.** `readTimeout > 60s` для синхронного вызова из HTTP-handler'а. Перевести в task-queue (`R-RES-WHERE-3`) или async-pattern (`R-ASYNC-1` REST guide).

---

## 4. Circuit Breaker

### 4.1 Обязательно

- **R-RES-CB-1.** `@CircuitBreaker(name = "<system>")` — на **public-методе out-adapter**, который вызывает внешнюю систему. Не на generated client (см. `R-RES-OAS-2`), не на handler'е, не на репозитории.
  ```java
  @Component
  @RequiredArgsConstructor
  public class SberClientAdapter implements PaymentPort {
      private final SberOrderServicesApi sberApi;

      @CircuitBreaker(name = "sber", fallbackMethod = "registerFallback")
      @Bulkhead(name = "sber")
      @Retry(name = "sber")
      @Override
      public RegisterResult register(RegisterCommand cmd) { ... }
  }
  ```

- **R-RES-CB-2.** Sliding window — **count-based** (`COUNT_BASED`, не `TIME_BASED`) для outbound в БД-нагруженных сервисах. Размер окна: `slidingWindowSize: 50` (типовое). Минимум вызовов до открытия: `minimumNumberOfCalls: 10`.

- **R-RES-CB-3.** Failure rate threshold: `50%` (по умолчанию). Понижение до `30%` оправдано только для критичных систем (платежи): «лучше быстро открыть, чем тянуть».

- **R-RES-CB-4.** `waitDurationInOpenState`: `30s` (типовое). За это время мы не делаем ни одного call'а — строго fast-fail. После — half-open с `permittedNumberOfCallsInHalfOpenState: 3`. Если все 3 успешны — closed; иначе — назад в open.

- **R-RES-CB-5.** Slow call rate threshold: `slowCallDurationThreshold: <readTimeout> / 2`. Это срабатывает раньше, чем сама ошибка по timeout — ловит «system is slow but not yet broken».

- **R-RES-CB-6.** При open-state CB — выбрасывается `CallNotPermittedException` (Resilience4j). Адаптер маппит её в port-specific exception (`PaymentPortException.SystemUnavailable`), а handler — в `503 Service Unavailable` или `409 Conflict` (зависит от UC).

### 4.2 Запрещено

- **R-RES-CB-X1.** `@CircuitBreaker` на репозитории, JOOQ-вызове, внутреннем сервисе. Локальный код не имеет «транзиентного» режима.
- **R-RES-CB-X2.** Custom CB на try/catch + `AtomicInteger` failure counter. Изобретать собственный — гарантированный bug-source. Resilience4j отлажен, integrated с metrics.
- **R-RES-CB-X3.** `@CircuitBreaker` без `name` или с одним общим `name = "default"` для разных систем. Sber и OdnaKassa делят CB-state — открытие одной закрывает другую.

---

## 5. Retry

Retry особенно опасен. Большинство retry-багов прода — это «дважды списали деньги».

### 5.1 Обязательно

- **R-RES-RE-1.** `@Retry(name = "<system>")` допустим **только** при одном из условий:
  1. Метод — read (GET-эквивалент): `findOrder`, `getStatus`. Чтение идемпотентно.
  2. Команда выполняется с `Idempotency-Key` (см. `AUTH-19`). Внешняя система обязана сама дедуплицировать.

- **R-RES-RE-2.** Конфиг retry:
  ```yaml
  resilience4j.retry.instances.sber:
    max-attempts: 3
    wait-duration: 500ms
    enable-exponential-backoff: true
    exponential-backoff-multiplier: 2.0
    retry-exceptions:
      - java.io.IOException
      - org.springframework.web.client.HttpServerErrorException
    ignore-exceptions:
      - org.springframework.web.client.HttpClientErrorException  # 4xx — НЕ ретраим
  ```

- **R-RES-RE-3.** `max-attempts: 3` (включая первую попытку). `5` — верхний предел. Больше — это уже task-queue.

- **R-RES-RE-4.** Граница in-memory retry vs task-queue:
  - **In-memory (Resilience4j Retry)** — транзиенты `<5s` в сумме. Connection reset, single-instance hiccup, momentary 503.
  - **Task-queue (DB-driven scheduler)** — отказы `>30s`. Внешняя система реально лежит, недоступна минуты/часы. Переживает рестарт сервиса.
  - **5–30s** — обсуждать в дизайне. Обычно task-queue, потому что синхронная блокировка handler'а на 30s = таймаут upstream-вызова.

- **R-RES-RE-5.** Task-queue retry — отдельный паттерн через таблицу `*_task` с полями `status`, `retry_count`, `next_attempt_at`, `last_error`. Scheduler poll'ит каждые `5s`, фильтрует по `status='IN_PROGRESS' AND next_attempt_at <= now()`. После N неудачных попыток — `status='FAILED'` + alert. Пример: `OrderConfirmationTask`, `ReceiptCreationTask`.

### 5.2 Запрещено

- **R-RES-RE-X1.** `@Retry` на write-методе без `Idempotency-Key`. На 5xx ответ может быть «не дошло» или «дошло и завершилось, ответ потерялся». Retry = двойная операция = двойной платёж.
- **R-RES-RE-X2.** `@Retry` на `4xx`-ответы. Это контрактные ошибки клиента — повтор не поможет.
- **R-RES-RE-X3.** `@Retry` без `enable-exponential-backoff`. Линейный retry = 3 запроса подряд за 1.5s, удваивает нагрузку на и без того лежачую внешнюю систему.
- **R-RES-RE-X4.** `Spring Retry` (`@Retryable` из `spring-retry`) для outbound. Legacy-механизм без интеграции с CB и Bulkhead. Использовать Resilience4j.

---

## 6. Bulkhead

### 6.1 Обязательно

- **R-RES-BH-1.** `@Bulkhead(name = "<system>")` — обязательный слой **отдельно** от connection pool. Connection pool ограничивает TCP-соединения; bulkhead — concurrent invocations (Java threads). Это два разных уровня защиты:
  - При залипании одного call'а — pool забит долго (ждёт TCP-таймаут).
  - Bulkhead раньше отказывает новым вызовам (`BulkheadFullException`), не давая им забивать thread pool сервиса.

- **R-RES-BH-2.** Тип — **semaphore-based** (`type: SEMAPHORE`), не `thread-pool`. Причина: thread-pool bulkhead создаёт собственный пул и теряет MDC/SecurityContext без явного контекстного wrapping. Semaphore работает в текущем thread.

- **R-RES-BH-3.** Sizing: `maxConcurrentCalls = <pool max-concurrent> × 0.8`. Запас 20% — bulkhead должен срабатывать **раньше** исчерпания pool'а. `maxWaitDuration: 100ms` (короткое ожидание, иначе теряется fail-fast смысл).
  ```yaml
  resilience4j.bulkhead.instances.sber:
    max-concurrent-calls: 16     # pool sber max-concurrent = 20
    max-wait-duration: 100ms
  ```

### 6.2 Запрещено

- **R-RES-BH-X1.** Thread-pool bulkhead (`type: THREADPOOL`) для outbound. Создаёт second pool, MDC/Security теряются без `@WithSpan` или ручного DelegatingSecurityContextExecutor. Semaphore-based достаточен.

---

## 7. Fallback

### 7.1 Обязательно

- **R-RES-FB-1.** Fallback допустим в трёх случаях:
  - **Cached read** — отдать данные из локального кеша / последнего успешного ответа: `getProductCatalog` → cached версия (`Cache-Control: stale-if-error`).
  - **Default value для read** — отдать пустой список / нейтральный объект, когда отсутствие данных — норма: `getRecommendations` → `[]`.
  - **Async-mode для write** — ответить клиенту `202 Accepted` + создать task в task-queue для последующей обработки: `createOrder` при отказе Sber → задача в очередь, ответ клиенту «обрабатывается».

- **R-RES-FB-2.** Контракт fallback-метода: same return type, дополнительный last-параметр `Throwable` (или конкретное исключение). Сигнатура:
  ```java
  @CircuitBreaker(name = "sber", fallbackMethod = "registerFallback")
  public RegisterResult register(RegisterCommand cmd) { ... }

  private RegisterResult registerFallback(RegisterCommand cmd, Throwable t) {
      log.warn("Sber unavailable, queuing for retry", t);
      taskQueue.enqueue(toRegisterTask(cmd));
      return RegisterResult.queued(taskId);
  }
  ```

### 7.2 Запрещено

- **R-RES-FB-X1.** Fallback с `null` / `0` / пустой `Money` для money-операций. Возврат `Money.ZERO` за «не удалось списать» = бизнес-баг.
- **R-RES-FB-X2.** Fallback, который тихо проглатывает ошибку и возвращает «success». Клиент не узнает, что операция не выполнена, пока не наступит несоответствие в данных.
- **R-RES-FB-X3.** Fallback, делающий другой outbound-вызов (например, во второй провайдер платежей) без обёртки этого второго вызова в свой CB. Cascading failure.

---

## 8. Конфигурация

### 8.1 Обязательно

- **R-RES-CFG-1.** Конфиг Resilience4j — через `application.yml` (declarative), не через `@Bean CustomCircuitBreakerConfig`. Это позволяет менять параметры через Spring Cloud Config / Vault без redeploy.
- **R-RES-CFG-2.** Defaults — в секции `default`, переопределения — per-instance:
  ```yaml
  resilience4j.circuitbreaker:
    configs.default:
      sliding-window-type: COUNT_BASED
      sliding-window-size: 50
      minimum-number-of-calls: 10
      failure-rate-threshold: 50
      wait-duration-in-open-state: 30s
      permitted-number-of-calls-in-half-open-state: 3
    instances:
      sber:
        base-config: default
        failure-rate-threshold: 30   # критичная система — порог ниже
      odnakassa:
        base-config: default
  ```
- **R-RES-CFG-3.** Имена instances — same as system: `sber`, `odnakassa`, `insurance`, `receipt`. Совпадают с именами beans (`R-RES-ISO-3`).

### 8.2 Запрещено

- **R-RES-CFG-X1.** Программная конфигурация через `CircuitBreakerConfig.custom()...` без причины. Скрытая конфигурация, не управляется через Cloud Config.

---

## 9. Связка с OpenAPI generator

Главный практический вопрос: **где вешать Resilience4j-аннотации, если outbound client сгенерирован OpenAPI generator'ом?**

### 9.1 Обязательно

- **R-RES-OAS-1.** Аннотации `@CircuitBreaker` / `@Retry` / `@Bulkhead` — на **public-методе out-adapter класса**, который оборачивает вызов generated client. Не на generated interface, не в `executeCall<T>`-helper.
  ```java
  // generated by openapi-generator (НЕ модифицируем):
  public interface SberOrderServicesApi {
      Call<RegisterResponse> register(RegisterRequest req, String correlationId);
  }

  // наш adapter:
  @Component
  public class SberClientAdapter implements PaymentPort {
      @CircuitBreaker(name = "sber", fallbackMethod = "registerFallback")
      @Bulkhead(name = "sber")
      @Retry(name = "sber")
      public RegisterResult register(RegisterCommand cmd) {
          return executeCall(sberApi.register(toApiRequest(cmd), null));
      }
  }
  ```

  Причины:
  - Generated interface перегенерируется при каждом `compileJava` — модификации потеряются.
  - Адаптер — это и есть публичная граница порта (`PaymentPort`), на которой имеет смысл говорить о resilience.
  - Аннотации видны в коде adapter, не в скрытом helper'е.

- **R-RES-OAS-2.** Для **новых сервисов** — `openapi-generator` target = `spring-restclient` (Spring 6.1+). Это даёт:
  - Native `RestClient.Builder` интеграцию.
  - Observability через Spring `Observation` API без обвязки.
  - Tracing через OTel auto-configure.
  - Совместимость с `@CircuitBreaker` через AOP без дополнительной обвязки.

  Для **legacy-сервисов** (Retrofit2 уже в проде) — допустимо оставить, но новые out-adapter — на `spring-restclient`.

- **R-RES-OAS-3.** OpenAPI-спецификация внешнего API хранится в `<system>-client-generator/src/main/resources/openapi/<system>.openapi.yaml`. Codegen в `build/generated/sources/openapi/`, не коммитится. Регенерация — на `compileJava`.

- **R-RES-OAS-4.** Между generated interface и port-интерфейсом из `core/` — **обязательно** mapper (Plain Java или MapStruct), который переводит generated DTO в domain-команды. Generated DTO — детали транспорта, не доменные типы. Адаптер использует mapper, не возвращает generated DTO наверх.

### 9.2 Запрещено

- **R-RES-OAS-X1.** Аннотации на generated interface (`SberOrderServicesApi`). Регенерация затрёт.
- **R-RES-OAS-X2.** `@CircuitBreaker` в `executeCall<T>` helper с backendName-строкой как параметром. Теряется compile-time проверка имени, ошибки на runtime («unknown circuit breaker «sbr»»).
- **R-RES-OAS-X3.** Возврат generated DTO из public-метода out-adapter (`PaymentPort.register` возвращает `SberRegisterResponse`). Доменный port должен возвращать domain-типы.

---

## 10. Health checks

### 10.1 Обязательно

- **R-RES-HC-1.** На каждую внешнюю систему — `HealthIndicator` бин: `SberHealthIndicator implements HealthIndicator`.
- **R-RES-HC-2.** Health-probe — **cached**, TTL `30s` (типовое). Не каждый actuator-call ходит в Sber. Реализация: `@Cacheable("health.sber")` или ручной `Instant lastProbe + Health lastResult`.
- **R-RES-HC-3.** Probe-метод — **light**: `GET /health` или `OPTIONS /` (если внешняя система не имеет health-endpoint), не реальный бизнес-вызов. Health-call не должен дёргать `register` или `confirmPayment`.
- **R-RES-HC-4.** Health отражается в `/actuator/health/<system>`. K8s `livenessProbe` смотрит на `/actuator/health/liveness` (overall), `readinessProbe` — на `/actuator/health/readiness` (включая внешние). Если Sber down — pod может вылететь из Service backend pool.

### 10.2 Запрещено

- **R-RES-HC-X1.** Sync-probe на каждый `/actuator/health` запрос (без кеша). При высокочастотных K8s probes (каждые 5s) это DDoS внешней системы силами наших же health-check'ов.
- **R-RES-HC-X2.** Health-probe, делающий business-операцию (`registerTestOrder`, `getRealTransactions`). Изменяет состояние, нагружает систему, плодит test-данные.

---

## 11. Async и polling

### 11.1 Обязательно

- **R-RES-ASYNC-1.** Если внешняя система требует polling (как страхование из bus-tickets — «отправили запрос → ждём результат»), polling реализуется через **task-queue**, не через `Thread.sleep` в синхронном handler'е:
  - Команда создаёт `<X>PollingTask` в БД (`status=IN_PROGRESS`, `next_attempt_at=now()+5s`).
  - Возвращает клиенту `202 Accepted` (см. `R-ASYNC-1` REST guide).
  - Scheduler (`@Scheduled` каждые 5s) опрашивает задачи, дёргает внешнюю систему, обновляет статус.
  - При успехе — `status=COMPLETED`, продолжение бизнес-флоу через event/saga.

- **R-RES-ASYNC-2.** В sync-методе адаптера допустим `Thread.sleep` только если total wait `<2s` (короткий transient retry с фиксированным backoff). Иначе — task-queue.

- **R-RES-ASYNC-3.** Для async outbound (`CompletableFuture`-возврат из adapter) — `@TimeLimiter(name = "<system>")` обязателен. Отдельная аннотация (Resilience4j Retry/Bulkhead/CB не поддерживают timeout sами для CompletableFuture).

### 11.2 Запрещено

- **R-RES-ASYNC-X1.** `Thread.sleep(N)` в цикле в синхронном handler'е, опрашивающем внешнюю систему. Блокирует worker-thread на N×iterations секунд. При нагрузке исчерпает thread-pool за минуты.
- **R-RES-ASYNC-X2.** Любая `Thread.sleep > 5s` — это запах «должно было быть task-queue».

---

## 12. Observability

### 12.1 Обязательно

- **R-RES-OBS-1.** Resilience4j metrics — через Micrometer (`resilience4j-micrometer` dependency). Автоматически экспортирует:
  - `resilience4j_circuitbreaker_state{name,state=closed|open|half_open}`
  - `resilience4j_circuitbreaker_calls{name,kind=successful|failed|ignored,...}`
  - `resilience4j_retry_calls{name,kind=successful_without_retry|...}`
  - `resilience4j_bulkhead_available_concurrent_calls{name}`

- **R-RES-OBS-2.** OTel-spans на adapter-методах — атрибут `circuit_breaker.state` (current state в момент вызова) и `external.system` (имя системы). Это даёт связку «slow trace → CB был half-open».

- **R-RES-OBS-3.** Логирование — структурированное (см. observability-style-guide, в планах). При каждом state-transition CB — лог уровня WARN с system, prev_state, new_state, failure_rate. Не на каждый успешный call.

### 12.2 Запрещено

- **R-RES-OBS-X1.** Отключение metrics через `management.metrics.enable.resilience4j=false` без причины. Без них SRE не увидит «у нас CB Sber стабильно half-open» до прода.

---

## 13. Антипаттерны

Сводка ссылок на запрещающие правила (X-коды) — единая точка для быстрой проверки.

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Shared OkHttpClient/pool на разные системы | `R-RES-ISO-X1` | per-system bean + pool |
| `OkHttpClient` без timeouts | `R-RES-TO-X1` | `connect/read/call` явно |
| `callTimeout < readTimeout` | `R-RES-TO-X2` | `callTimeout ≥ connect+read+buffer` |
| Sync `readTimeout > 60s` | `R-RES-TO-X3` | task-queue |
| `@CircuitBreaker` на репозитории / JOOQ-вызове | `R-RES-CB-X1`, `R-RES-WHERE-X1` | только на adapter-методе с outbound HTTP |
| Custom CB на try/catch + counter | `R-RES-CB-X2` | Resilience4j |
| `@CircuitBreaker(name = "default")` для всех систем | `R-RES-CB-X3` | per-system name |
| `@Retry` на write без Idempotency-Key | `R-RES-RE-X1` | только GET или с Idempotency-Key |
| `@Retry` на 4xx | `R-RES-RE-X2` | только на 5xx + IOException |
| `@Retry` без exp backoff | `R-RES-RE-X3` | `enable-exponential-backoff: true` |
| `@Retryable` Spring-Retry для outbound | `R-RES-RE-X4` | Resilience4j Retry |
| Thread-pool bulkhead для outbound | `R-RES-BH-X1` | semaphore-based |
| Fallback с `null` / `Money.ZERO` для money | `R-RES-FB-X1` | task-queue + 202 Accepted |
| Тихий fallback с success | `R-RES-FB-X2` | явный fallback с queueing |
| Каскадный fallback в другой провайдер без CB | `R-RES-FB-X3` | каждый провайдер — свой CB |
| Программный `CircuitBreakerConfig.custom()` | `R-RES-CFG-X1` | `application.yml` declarative |
| Аннотации на generated `<X>Api` interface | `R-RES-OAS-X1` | на adapter-методе |
| CB в `executeCall<T>` helper с backendName строкой | `R-RES-OAS-X2` | аннотации на adapter-методе |
| Возврат generated DTO из port-метода | `R-RES-OAS-X3` | mapper → domain |
| Sync health-probe без кеша | `R-RES-HC-X1` | TTL 30s |
| Health-probe с business-операцией | `R-RES-HC-X2` | light GET/OPTIONS |
| `Thread.sleep` цикл в sync-handler'e | `R-RES-ASYNC-X1` | task-queue |
| `Thread.sleep > 5s` в коде | `R-RES-ASYNC-X2` | task-queue |
| Отключение R4J metrics | `R-RES-OBS-X1` | оставить включённым |

Финальная сводка: правил «Обязательно» — около 40, «Запрещено» — около 25.

---

## Миграционный план для существующих сервисов

Для сервисов, у которых сейчас ad-hoc resilience (как bus-tickets — Resilience4j задекларирован, но не используется):

| Шаг | Что | Эффект |
|---|---|---|
| 1 | **Per-system OkHttpClient** (`R-RES-ISO-1`) — разделить shared dispatcher/pool по системам | Изоляция: зависание Sber не блокирует OdnaKassa |
| 2 | **`@CircuitBreaker` на out-adapter методах** (`R-RES-CB-1`) с `application.yml` конфигом | Fast-fail при отказе системы вместо timeout-чейна |
| 3 | **`@Bulkhead` per-system** (`R-RES-BH-1`) с semaphore | Раннее отвержение новых call'ов до исчерпания pool |
| 4 | **HealthIndicator per-system** (`R-RES-HC-1`) с TTL-кешем | K8s знает «у нас Sber лёг» через 30s, не через 5min логов |
| 5 | **Sleep-loop polling → task-queue** (`R-RES-ASYNC-1`) — переписать `InsuranceClientAdapter` polling на DB-driven | Освобождение worker-threads под нагрузкой |
| 6 | **Новые out-adapter — `spring-restclient`** (`R-RES-OAS-2`), Retrofit2 — только в legacy-сервисах | Native Spring observability/tracing без обвязки |

Шаги независимы — каждый отдельным PR без блокировок.
