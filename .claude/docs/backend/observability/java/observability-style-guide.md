# Observability Style Guide

Свод правил наблюдаемости в Java/Spring-сервисах команды UCP: structured logging с MDC, Micrometer-метрики (RED/USE), OpenTelemetry tracing, Actuator health-checks, propagation context через async, SLO + alerts. Каждое правило идентифицируется кодом (`R-OBS-LOG-1`, `R-OBS-MTR-X1`) — скилл `ucp-observability-review` цитирует эти коды в findings.

Гайд опирается на:
- [Spring Boot Actuator](https://docs.spring.io/spring-boot/reference/actuator/index.html) (Spring Boot 3+).
- [Micrometer](https://docs.micrometer.io/micrometer/reference/) — metrics facade с экспортом в Prometheus.
- [OpenTelemetry Java agent + spring-boot-starter](https://opentelemetry.io/docs/zero-code/java/agent/) — distributed tracing.
- [Logback / Logstash encoder](https://github.com/logfellow/logstash-logback-encoder) — JSON-логи.

Не покрывает: alerting rules в Prometheus/Grafana (это infra-уровень), log aggregation infrastructure (Elasticsearch, Loki), Service Mesh observability (Istio sidecar metrics — отдельная тема).

Связанные стандарты:
- `R-RES-OBS-*` (Resilience) — CB/Bulkhead/Retry metrics уже codified.
- `R-CACHE-OBS-*` (Caching) — cache hit rate metrics.
- `R-KFK-OBS-*` (Kafka) — consumer lag, traceparent propagation.
- `AUTH-16` (Auth) — PII в логах **запрещено** (главное правило observability ↔ security).
- `R-HDR-4` (REST) — `traceparent` W3C Trace Context.

---

## Содержание

1. [Logging — `R-OBS-LOG-*`](#1-logging)
2. [Metrics — `R-OBS-MTR-*`](#2-metrics)
3. [Tracing — `R-OBS-TRC-*`](#3-tracing)
4. [Health checks — `R-OBS-HC-*`](#4-health-checks)
5. [Конфигурация — `R-OBS-CFG-*`](#5-конфигурация)
6. [Context propagation (MDC) — `R-OBS-CTX-*`](#6-context-propagation-mdc)
7. [SLO и алерты — `R-OBS-SLO-*`](#7-slo-и-алерты)
8. [Антипаттерны — сводка `R-OBS-*-X*`](#8-антипаттерны)

---

## 1. Logging

### 1.1 Обязательно

- **R-OBS-LOG-1.** **Structured JSON в проде.** Дев-окружение — текстовый Logback-pattern для читаемости; прод — JSON через `logstash-logback-encoder` или Spring Boot 3 `EcsEncoder`. JSON парсится Loki/ELK/Datadog без regex.

- **R-OBS-LOG-2.** **`@Slf4j` через Lombok** на классе. Никаких `LoggerFactory.getLogger(MyClass.class)` руками — лишний boilerplate.
  ```java
  @Component
  @RequiredArgsConstructor
  @Slf4j
  public class OrderService { ... }
  ```

- **R-OBS-LOG-3.** **Параметризованные логи** через `{}`-плейсхолдеры:
  ```java
  log.info("Order created: orderId={} customerId={}", order.getId(), order.getCustomerId());
  ```
  Не string-concat (`"Order created: " + order.getId()`) — выполняет toString даже если уровень disabled.

- **R-OBS-LOG-4.** **Уровни логов:**
  - `ERROR` — actionable failure, требует разбора. Всегда с stack trace через 2-arg log: `log.error("Failed to charge order {}", orderId, ex)`.
  - `WARN` — recoverable degradation: CB open, retry attempt, fallback использован.
  - `INFO` — important business events: «order confirmed», «user registered», application start. **Не каждый HTTP-запрос** (это уже в access-log).
  - `DEBUG` — детали для отладки. Включается per-environment, не на проде.
  - `TRACE` — сверх-детально. Прод никогда.

- **R-OBS-LOG-5.** **MDC поля** в каждой записи: `traceId`, `spanId` (auto через OTel), `requestId` (из `X-Request-Id` header или generated), `userId` (из JWT через filter). Эти поля автоматически попадают в JSON через MDC-encoder.

- **R-OBS-LOG-6.** **Логи на границах**:
  - Inbound REST request — access-log (`spring.mvc.log-request-details: false`, отдельный логгер `org.springframework.web.servlet.DispatcherServlet`); INFO-уровень на handler entry/exit для критичных команд.
  - Outbound HTTP — INFO на request, WARN на 4xx/5xx, ERROR на network failure.
  - Domain events — INFO на publish.
  - Schedulers — INFO на start/end batch с count.

### 1.2 Запрещено

- **R-OBS-LOG-X1.** **PII в логах.** Email, phone, ФИО, адрес, паспорт, токены, пароли — `R-OBS-LOG-X1` **критическое нарушение**. Маскировать (`***@***.com`) или вообще не логировать. См. `AUTH-16`.

- **R-OBS-LOG-X2.** **`System.out.println` / `e.printStackTrace()` / `System.err.println`.** Не попадают в structured pipeline, теряют MDC, не алертируются.

- **R-OBS-LOG-X3.** **String-concat в log-message** при низком уровне (DEBUG/TRACE). `log.debug("Heavy: " + bigObject.serialize())` выполняет `serialize()` всегда. Используй `log.debug("Heavy: {}", bigObject)` — Slf4j ленив.

- **R-OBS-LOG-X4.** **`log.error(...)` без stack trace** для exception. `log.error("Failed: " + e.getMessage())` теряет stack — используй 2-arg `log.error("Failed: {}", context, e)`.

- **R-OBS-LOG-X5.** **Полный request body в логах** для money/PII-эндпоинтов. Логируй только идентификаторы (`orderId`), не payload.

- **R-OBS-LOG-X6.** **INFO-логи на каждый HTTP-запрос**. Если все handler'ы пишут «Handling request X», выйдет шум. Access-log делает это отдельно с правильным форматированием.

---

## 2. Metrics

### 2.1 Обязательно

- **R-OBS-MTR-1.** Micrometer — обязательная зависимость через `spring-boot-starter-actuator` + `io.micrometer:micrometer-registry-prometheus`. Endpoint `/actuator/prometheus` exposed для scraping.

- **R-OBS-MTR-2.** **Стандартные dimensions (tags)** на каждой метрике:
  - `service` — имя сервиса (`order-service`).
  - `env` — окружение (`prod`, `staging`, `dev`).
  - `version` — git short-sha или semver build (через `management.metrics.tags.version: ${BUILD_VERSION}`).
  Настраиваются через `management.metrics.tags.*` в `application.yml` — **не дублируй в каждой custom-метрике**.

- **R-OBS-MTR-3.** **RED method для HTTP** (auto через Spring Boot Actuator):
  - `http_server_requests_seconds_count{uri,method,status}` — rate.
  - `http_server_requests_seconds_count{status=~"5.."}` — errors.
  - `http_server_requests_seconds{quantile="0.95"}` — duration p95.

- **R-OBS-MTR-4.** **USE method для resources** (auto через Spring Boot):
  - `jvm_memory_used_bytes` / `jvm_memory_max_bytes` — utilization.
  - `executor_active_threads` / `executor_pool_size_threads` — saturation.
  - `jvm_gc_pause_seconds` — saturation indicator.
  - `hikaricp_connections_active` / `hikaricp_connections_max` — DB pool saturation.

- **R-OBS-MTR-5.** **Custom business metrics** через `MeterRegistry`:
  ```java
  @Component
  @RequiredArgsConstructor
  public class OrderMetrics {

      private final Counter orderCreatedCounter;
      private final Timer paymentProcessingTimer;
      private final DistributionSummary orderAmountSummary;

      public OrderMetrics(MeterRegistry registry) {
          this.orderCreatedCounter = Counter.builder("order_created_total")
              .description("Total orders created")
              .tag("type", "B2C")
              .register(registry);
          this.paymentProcessingTimer = Timer.builder("payment_processing_seconds")
              .publishPercentiles(0.5, 0.95, 0.99)
              .register(registry);
          this.orderAmountSummary = DistributionSummary.builder("order_amount_rubles")
              .baseUnit("rubles")
              .register(registry);
      }
  }
  ```
  Типы: `Counter` (монотонно растущий), `Gauge` (текущее значение), `Timer` (длительность), `DistributionSummary` (произвольные значения).

- **R-OBS-MTR-6.** **Имена метрик** — snake_case, единицы в имени (`payment_duration_seconds`, не просто `payment_duration`). Соглашение Prometheus.

- **R-OBS-MTR-7.** **Tags — низкая cardinality.** Допустимо: `status_code` (3 значения: `success`/`client_error`/`server_error` — не само число), `endpoint` (десятки путей), `payment_method` (CARD/SBP/CRYPTO). Запрещено: `user_id`, `order_id`, `request_id` — миллионы значений = OOM в Prometheus.

### 2.2 Запрещено

- **R-OBS-MTR-X1.** **High-cardinality tags** (`user_id`, `request_id`, `order_id` как value). Prometheus хранит time series per unique combination tags — миллион ID = миллион time series = OOM.

- **R-OBS-MTR-X2.** **Не-стандартизованные dimensions** (один service пишет `app=foo`, другой `service_name=foo`). Стандарт `service`/`env`/`version` через `management.metrics.tags.*`.

- **R-OBS-MTR-X3.** **`micrometer-core` без registry**. Без Prometheus registry метрики собираются in-memory и теряются на рестарте.

- **R-OBS-MTR-X4.** **`/actuator/prometheus` без auth** в публичной сети. Internal scraper-only через network policy / VPN.

---

## 3. Tracing

### 3.1 Обязательно

- **R-OBS-TRC-1.** **OpenTelemetry автоинструментация** через `opentelemetry-spring-boot-starter` (Spring Boot 3+). Авто-spans для:
  - HTTP server requests (Spring MVC).
  - HTTP client (RestClient, RestTemplate, WebClient).
  - JDBC (через JDBC instrumentation).
  - Kafka producer/consumer.
  - Spring Cache.

- **R-OBS-TRC-2.** **`traceparent` propagation** (W3C Trace Context, см. `R-HDR-4`). Spring + OTel автоматически:
  - Извлекает из incoming HTTP headers.
  - Пропагирует в outgoing HTTP / Kafka headers.
  - Связывает spans в distributed trace.

- **R-OBS-TRC-3.** **Manual spans** для use case handlers и значимых операций:
  ```java
  @Component
  @RequiredArgsConstructor
  @Transactional
  public class ConfirmOrderCommandHandler implements UseCaseHandler<ConfirmOrderCommand, Order> {

      private final Tracer tracer;

      @Override
      public Order handle(ConfirmOrderCommand cmd) {
          var span = tracer.spanBuilder("confirmOrder")
              .setAttribute("order.id", cmd.orderId())
              .startSpan();
          try (var scope = span.makeCurrent()) {
              // бизнес-логика
              return order;
          } finally {
              span.end();
          }
      }
  }
  ```
  Альтернатива — аннотация `@WithSpan(value = "confirmOrder")` (требует OTel javaagent или extension).

- **R-OBS-TRC-4.** **Span attributes** — business context, не PII:
  - `order.id`, `customer.id` (внутренние ID — ОК).
  - `order.status`, `payment.method`.
  - `external.system` (для outbound HTTP).
  - `circuit_breaker.state` (для Resilience).

- **R-OBS-TRC-5.** **Sampling**: 1–10% в проде по умолчанию, **100% для error-traces** (tail-based sampling если поддерживается collector'ом). Это даёт достаточный набор «нормальных» traces и не пропускает ошибки.
  ```yaml
  otel:
    traces:
      sampler: parentbased_traceidratio
      sampler.arg: 0.1   # 10%
  ```

- **R-OBS-TRC-6.** **`trace-id` в логах** через MDC. OTel автоматически подставляет `traceId`/`spanId` через `OpenTelemetryAppender` в Logback. Это даёт связку «лог-запись → distributed trace».

### 3.2 Запрещено

- **R-OBS-TRC-X1.** **Sampling 100% в проде** для среднего/высоконагруженного сервиса. Tracing storage (Tempo, Jaeger) переполняется за часы; стоимость зашкаливает.

- **R-OBS-TRC-X2.** **PII в span attributes** (`customer.email`, `order.detail` с PII). Tracing-данные часто менее защищены чем main DB.

- **R-OBS-TRC-X3.** **Manual span без `try-finally` / try-with-resources**. Span не закроется → утечка spans в коллекторе, искажение traces.

- **R-OBS-TRC-X4.** **Trace context разрывается на `@Async` без TaskDecorator**. См. `R-OBS-CTX-3`.

---

## 4. Health checks

### 4.1 Обязательно

- **R-OBS-HC-1.** Spring Boot Actuator с **разделением liveness и readiness**:
  ```yaml
  management:
    endpoint:
      health:
        probes:
          enabled: true
        show-details: always           # для internal monitoring; ограничить через Spring Security
    health:
      livenessstate:
        enabled: true
      readinessstate:
        enabled: true
  ```
  - `/actuator/health/liveness` — UP пока процесс отвечает. Не должен зависеть от внешних систем; иначе K8s рестартует pod при кратковременной недоступности БД.
  - `/actuator/health/readiness` — UP когда сервис готов принимать трафик: БД подключена, dependencies прогреты, кеши warm-up завершён.

- **R-OBS-HC-2.** **Custom HealthIndicator** для каждой критичной внешней системы (см. `R-RES-HC-1`):
  - DB через `DataSourceHealthContributor` — auto.
  - Redis через `RedisHealthIndicator` — auto.
  - External HTTP — custom HealthIndicator с TTL-кешем (см. `R-RES-HC-2`).

- **R-OBS-HC-3.** **`/actuator/info`** содержит:
  - `git.commit.id` (через `git-commit-id-plugin`).
  - `build.version` (Maven/Gradle version).
  - `build.time`.
  - `service.name`.
  Нужно для отладки «какая версия сейчас в проде».

### 4.2 Запрещено

- **R-OBS-HC-X1.** **Business-state в health check** (`if (orderCount > N) return DOWN`). Health — техническое состояние процесса. Бизнес-метрики — отдельные SLO.

- **R-OBS-HC-X2.** **Liveness зависит от внешних систем** (DB/Redis). При временной недоступности K8s рестартует pod, не помогает — после restart те же системы будут недоступны → loop. Только readiness.

- **R-OBS-HC-X3.** **Health-probe делает business-операцию** (`registerTestOrder`). См. `R-RES-HC-X2` — ddos самих себя через health-checks.

---

## 5. Конфигурация

### 5.1 Обязательно

- **R-OBS-CFG-1.** **Management port отдельный** от business port:
  ```yaml
  server.port: 8080            # business
  management.server.port: 8081 # actuator
  ```
  Это позволяет: (а) ограничить /actuator на сетевом уровне (только internal); (б) не блокировать business-traffic при actuator-нагрузке.

- **R-OBS-CFG-2.** **Exposed endpoints** — только нужные:
  ```yaml
  management:
    endpoints:
      web:
        exposure:
          include: health,info,metrics,prometheus
  ```
  Дефолт Spring — только `/actuator/health` и `/actuator/info`. Production-grade — explicit list.

- **R-OBS-CFG-3.** **Spring Boot defaults** для metrics:
  ```yaml
  management:
    metrics:
      distribution:
        percentiles-histogram:
          http.server.requests: true
        slo:
          http.server.requests: 100ms,500ms,1s,5s
      tags:
        service: ${spring.application.name}
        env: ${ENV:dev}
        version: ${BUILD_VERSION:unknown}
  ```

- **R-OBS-CFG-4.** **Logback-spring.xml** с двумя профилями:
  ```xml
  <configuration>
      <springProfile name="dev,test">
          <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
              <encoder>
                  <pattern>%d{HH:mm:ss.SSS} %-5level [%thread] %X{traceId:-} %logger{30} - %msg%n</pattern>
              </encoder>
          </appender>
      </springProfile>
      <springProfile name="prod,staging">
          <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
              <encoder class="net.logstash.logback.encoder.LogstashEncoder">
                  <includeMdcKeyName>traceId</includeMdcKeyName>
                  <includeMdcKeyName>requestId</includeMdcKeyName>
                  <includeMdcKeyName>userId</includeMdcKeyName>
              </encoder>
          </appender>
      </springProfile>
      <root level="INFO">
          <appender-ref ref="STDOUT"/>
      </root>
  </configuration>
  ```

### 5.2 Запрещено

- **R-OBS-CFG-X1.** **Exposing `/actuator/env`, `/actuator/heapdump`, `/actuator/threaddump`** в проде без authentication. `env` показывает все configs включая возможные секреты в plain (если они попали туда мимо Vault).

- **R-OBS-CFG-X2.** **Один port для business + actuator** в проде. Невозможно отделить scraping-traffic от business-traffic.

- **R-OBS-CFG-X3.** **`management.endpoints.web.exposure.include: '*'`** в проде. Открывает `env`, `beans`, `mappings`, `loggers` — security risk.

---

## 6. Context propagation (MDC)

### 6.1 Обязательно

- **R-OBS-CTX-1.** **Request-ID filter** populates MDC на каждом входящем HTTP request:
  ```java
  @Component
  @Order(Ordered.HIGHEST_PRECEDENCE)
  public class MdcFilter extends OncePerRequestFilter {

      @Override
      protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp,
                                       FilterChain chain) throws ServletException, IOException {
          var requestId = Optional.ofNullable(req.getHeader("X-Request-Id"))
              .orElseGet(() -> UUID.randomUUID().toString());
          MDC.put("requestId", requestId);
          try {
              chain.doFilter(req, resp);
          } finally {
              MDC.clear();   // обязательно — иначе утечка контекста между request'ами в thread pool
          }
      }
  }
  ```

- **R-OBS-CTX-2.** **`traceId` / `spanId` в MDC** — автоматически через OTel Logback appender (`io.opentelemetry.instrumentation.logback-mdc-1.0`). Не добавлять руками.

- **R-OBS-CTX-3.** **Async/CompletableFuture** — пропагация контекста через `TaskDecorator`:
  ```java
  @Bean
  public TaskDecorator mdcTaskDecorator() {
      return runnable -> {
          var copyOfContext = MDC.getCopyOfContextMap();
          return () -> {
              try {
                  if (copyOfContext != null) MDC.setContextMap(copyOfContext);
                  runnable.run();
              } finally {
                  MDC.clear();
              }
          };
      };
  }

  @Bean
  public TaskExecutor taskExecutor(TaskDecorator decorator) {
      var executor = new ThreadPoolTaskExecutor();
      executor.setTaskDecorator(decorator);
      // ...
      executor.initialize();
      return executor;
   }
  ```
  Без декоратора `traceId`/`requestId` теряются на async-границе → traces разрываются.

- **R-OBS-CTX-4.** **`userId` в MDC** — populates после JWT-валидации в Security filter chain:
  ```java
  if (authentication != null && authentication.isAuthenticated()) {
      MDC.put("userId", authentication.getName());
  }
  ```

### 6.2 Запрещено

- **R-OBS-CTX-X1.** **MDC без `MDC.clear()` в finally**. Утечка context в thread pool — следующий request unrelated user видит чужой `userId` в логах = compliance incident.

- **R-OBS-CTX-X2.** **`MDC.put` в произвольных местах кода** (handler, service). Только в filter / interceptor. Иначе `MDC.clear` логика не очевидна.

- **R-OBS-CTX-X3.** **Async без TaskDecorator** для CompletableFuture / @Async — traces разрываются на границе thread.

---

## 7. SLO и алерты

### 7.1 Обязательно

- **R-OBS-SLO-1.** **Каждый critical-endpoint** имеет SLO:
  - `/api/v1/orders` POST — 99.9% successful (non-5xx) в течение rolling 30-day window.
  - p95 latency < 500ms.
  - Это business-цели, не «alert на каждую ошибку».

- **R-OBS-SLO-2.** **Multi-window multi-burn-rate alerts** (см. [Google SRE Workbook](https://sre.google/workbook/alerting-on-slos/)):
  - Fast burn (1h window, burn rate > 14.4) → alert «у нас 5% бюджета сгорает за час».
  - Slow burn (6h window, burn rate > 6) → alert «у нас 5% бюджета сгорает за 6 часов».
  - Точные значения зависят от SLO target. Цель — не алертить на каждую проблему, только на нарушения SLO.

- **R-OBS-SLO-3.** **Alert на error budget exhaustion** — отдельный алерт когда бюджет ошибок остался < 10%. Это команда «нужно срочно фокус на reliability, не на features».

- **R-OBS-SLO-4.** **Alerts отдельные от SLO**:
  - Infrastructure (`jvm_memory_used / jvm_memory_max > 0.9`, `hikaricp_connections_active / max > 0.9`) — оперативные алерты SRE.
  - Domain (`order_failed_total` rate > N) — бизнес-метрики, могут не нарушать SLO но требуют внимания.
  - Resilience (`resilience4j_circuitbreaker_state{state=open}`) — see `R-RES-OBS-*`.
  - Cache hit rate `< 70%` — `R-CACHE-OBS-2`.
  - Kafka consumer lag — `R-KFK-OBS-2`.

### 7.2 Запрещено

- **R-OBS-SLO-X1.** **Alert на каждый ERROR** в логах. Alert fatigue → команда игнорирует. Фильтруй: ERROR класса `ServiceUnavailableException` повторяющийся 100 раз в минуту = один алерт; единичные `ValidationException` = не алерт.

- **R-OBS-SLO-X2.** **SLO без error budget**. Если 100% target — нечем оперировать; 99.9% даёт 43 минуты downtime в месяц как бюджет.

- **R-OBS-SLO-X3.** **Алерты без runbook'ов**. PagerDuty в 3 ночи без инструкции «что делать» = эскалация без действия.

---

## 8. Антипаттерны

| Антипаттерн | Правило | Корректно |
|---|---|---|
| PII в логах (email, phone, токены) | `R-OBS-LOG-X1` (см. `AUTH-16`) | маскировать или не логировать |
| `System.out.println` / `e.printStackTrace()` | `R-OBS-LOG-X2` | `@Slf4j` log.error |
| String-concat в log args | `R-OBS-LOG-X3` | `{}` placeholders |
| `log.error("Failed: " + e.getMessage())` без stack | `R-OBS-LOG-X4` | `log.error("Failed: {}", ctx, e)` |
| Полный request body в логах | `R-OBS-LOG-X5` | только id |
| INFO на каждый HTTP-запрос | `R-OBS-LOG-X6` | access-log отдельно |
| `user_id` / `request_id` как metric tag | `R-OBS-MTR-X1` | бизнес-категории |
| Не-стандартизованные dimensions | `R-OBS-MTR-X2` | `service`/`env`/`version` через `management.metrics.tags` |
| Micrometer без registry | `R-OBS-MTR-X3` | Prometheus registry обязателен |
| `/actuator/prometheus` без auth публично | `R-OBS-MTR-X4` | internal-only через network policy |
| Sampling 100% tracing в проде | `R-OBS-TRC-X1` | 1-10% + 100% errors |
| PII в span attributes | `R-OBS-TRC-X2` | только internal IDs |
| Manual span без try-finally | `R-OBS-TRC-X3` | try-with-resources / finally |
| Trace разрывается на @Async | `R-OBS-TRC-X4` (см. `R-OBS-CTX-X3`) | TaskDecorator |
| Business-state в health check | `R-OBS-HC-X1` | техническое состояние; бизнес → SLO |
| Liveness зависит от DB | `R-OBS-HC-X2` | только readiness |
| Health-probe делает business-операцию | `R-OBS-HC-X3` | light probe |
| Exposing `/actuator/env` без auth | `R-OBS-CFG-X1` | exposure: explicit list |
| Один port для business + actuator | `R-OBS-CFG-X2` | management.server.port: 8081 |
| `exposure.include: '*'` в проде | `R-OBS-CFG-X3` | explicit list |
| MDC без `MDC.clear()` в finally | `R-OBS-CTX-X1` | try { ... } finally { MDC.clear(); } |
| `MDC.put` в произвольных местах | `R-OBS-CTX-X2` | только в filter/interceptor |
| Alert на каждый ERROR | `R-OBS-SLO-X1` | по burn-rate |
| SLO без error budget | `R-OBS-SLO-X2` | 99.9% даёт 43min/month |
| Alerts без runbook | `R-OBS-SLO-X3` | каждый alert = ссылка на runbook |

Финальная сводка: правил «Обязательно» — около 30, «Запрещено» — около 24.
