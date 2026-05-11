---
name: ucp-observability-design
description: Сгенерировать observability-инфраструктуру под Observability Style Guide — Logback config с JSON для prod, Micrometer + Prometheus registry с стандартизованными tags, OpenTelemetry автоинструментация + sampling, Spring Boot Actuator с liveness/readiness и custom HealthIndicator, MdcFilter с requestId + TaskDecorator для @Async, application.yml блок management.* + otel.* + logging.*, опционально custom business metrics. Решает: где placement (filter MDC, JWT-after-auth для userId), как propagate context через async, какой sampling rate (1-10% дефолт), какой logback profile config (text dev / JSON prod), какие endpoints exposed (whitelist). Применяется при настройке observability в новом сервисе или upgrade existing. Триггеры: «настрой observability», «добавь метрики и tracing», «нужен structured logging», «MDC и traceId».
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Observability — проектирование

Ты генерируешь observability-инфраструктуру (logging + metrics + tracing + health + context propagation) под Observability Style Guide.

## Инструкции

1. **Прочитай** `.claude/docs/observability-style-guide.md` (`R-OBS-*`). Опционально — `auth-patterns-style-guide.md` (`AUTH-16` PII), `rest-api-rules.md` (`R-HDR-4` traceparent), `validation-style-guide.md` (`R-VLD-CFG-*`).

2. **Уточни параметры:**
   - **Сервис** — имя для `service` tag (`order-service`).
   - **Tracing backend** — Jaeger / Tempo / Datadog APM. Влияет на `otel.exporter.otlp.endpoint`.
   - **Metrics backend** — Prometheus pull / Datadog push / OTel Collector.
   - **Logging backend** — Loki / ELK / Datadog Logs. JSON-формат — стандарт; encoder выбор зависит от бэкенда (`LogstashEncoder` универсальный, `EcsEncoder` если Elastic-стек).
   - **Sampling rate** — 1-10% типично; для money/critical — может быть выше (50-100% если low-volume).
   - **Custom business metrics** — нужны? Какие (`order_created_total`, `payment_duration_seconds`)?

3. **Произведи код.** Lombok-defaults обязательны. Не цитируй коды правил в комментариях.

   ### 3.1. Зависимости (build.gradle.kts)

   ```kotlin
   dependencies {
       // Logging
       implementation("net.logstash.logback:logstash-logback-encoder:7.4")

       // Metrics
       implementation("org.springframework.boot:spring-boot-starter-actuator")
       implementation("io.micrometer:micrometer-registry-prometheus")

       // Tracing (OpenTelemetry автоинструментация)
       implementation("io.opentelemetry.instrumentation:opentelemetry-spring-boot-starter")
       implementation("io.opentelemetry.instrumentation:opentelemetry-logback-mdc-1.0")
   }
   ```

   ### 3.2. application.yml patch

   ```yaml
   spring.application.name: ${SERVICE_NAME:order-service}

   server.port: 8080

   management:
     server:
       port: 8081                              # отдельный port (R-OBS-CFG-1)
     endpoints:
       web:
         exposure:
           include: health,info,metrics,prometheus    # explicit (R-OBS-CFG-2)
     endpoint:
       health:
         probes:
           enabled: true                       # liveness/readiness (R-OBS-HC-1)
         show-details: always                  # ограничить через Spring Security
     health:
       livenessstate:
         enabled: true
       readinessstate:
         enabled: true
     metrics:
       distribution:
         percentiles-histogram:
           http.server.requests: true
         slo:
           http.server.requests: 100ms,500ms,1s,5s
       tags:                                   # стандартизованы (R-OBS-MTR-2)
         service: ${spring.application.name}
         env: ${ENV:dev}
         version: ${BUILD_VERSION:unknown}

   otel:
     service.name: ${spring.application.name}
     traces:
       sampler: parentbased_traceidratio
       sampler.arg: 0.1                        # 10% prod (R-OBS-TRC-5)
     exporter:
       otlp:
         endpoint: ${OTEL_COLLECTOR_ENDPOINT:http://otel-collector:4317}

   logging:
     level:
       root: INFO
       org.springframework.web.servlet.DispatcherServlet: INFO
   ```

   ### 3.3. logback-spring.xml

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <configuration>
       <springProfile name="dev,test">
           <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
               <encoder>
                   <pattern>%d{HH:mm:ss.SSS} %-5level [%thread] %X{traceId:-} %X{requestId:-} %logger{30} - %msg%n</pattern>
               </encoder>
           </appender>
       </springProfile>
       <springProfile name="prod,staging">
           <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
               <encoder class="net.logstash.logback.encoder.LogstashEncoder">
                   <includeMdcKeyName>traceId</includeMdcKeyName>
                   <includeMdcKeyName>spanId</includeMdcKeyName>
                   <includeMdcKeyName>requestId</includeMdcKeyName>
                   <includeMdcKeyName>userId</includeMdcKeyName>
                   <customFields>{"service":"${SERVICE_NAME:-unknown}","env":"${ENV:-dev}"}</customFields>
               </encoder>
           </appender>
           <!-- OTel appender вкладывает traceId/spanId в MDC автоматически -->
           <appender name="OTEL" class="io.opentelemetry.instrumentation.logback.mdc.v1_0.OpenTelemetryAppender">
               <appender-ref ref="STDOUT"/>
           </appender>
       </springProfile>
       <root level="INFO">
           <appender-ref ref="STDOUT"/>
       </root>
   </configuration>
   ```

   ### 3.4. MdcFilter (request-Id, MDC.clear() в finally)

   ```java
   @Component
   @Order(Ordered.HIGHEST_PRECEDENCE)
   public class MdcFilter extends OncePerRequestFilter {

       private static final String REQUEST_ID_HEADER = "X-Request-Id";
       private static final String MDC_REQUEST_ID = "requestId";

       @Override
       protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp,
                                        FilterChain chain) throws ServletException, IOException {
           var requestId = Optional.ofNullable(req.getHeader(REQUEST_ID_HEADER))
               .filter(s -> !s.isBlank())
               .orElseGet(() -> UUID.randomUUID().toString());
           MDC.put(MDC_REQUEST_ID, requestId);
           resp.setHeader(REQUEST_ID_HEADER, requestId);
           try {
               chain.doFilter(req, resp);
           } finally {
               MDC.clear();   // R-OBS-CTX-X1: обязательно
           }
       }
   }
   ```

   ### 3.5. UserId в MDC после JWT (опционально, если есть auth)

   ```java
   @Component
   public class UserIdMdcFilter extends OncePerRequestFilter {

       @Override
       protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp,
                                        FilterChain chain) throws ServletException, IOException {
           var auth = SecurityContextHolder.getContext().getAuthentication();
           if (auth != null && auth.isAuthenticated() && auth.getName() != null) {
               MDC.put("userId", auth.getName());
           }
           try {
               chain.doFilter(req, resp);
           } finally {
               MDC.remove("userId");
           }
       }
   }
   ```

   ### 3.6. TaskDecorator для async-MDC propagation

   ```java
   @Configuration
   public class AsyncConfig {

       @Bean
       TaskDecorator mdcTaskDecorator() {
           return runnable -> {
               var copyOfContextMap = MDC.getCopyOfContextMap();
               return () -> {
                   try {
                       if (copyOfContextMap != null) MDC.setContextMap(copyOfContextMap);
                       runnable.run();
                   } finally {
                       MDC.clear();
                   }
               };
           };
       }

       @Bean
       TaskExecutor applicationTaskExecutor(TaskDecorator decorator) {
           var executor = new ThreadPoolTaskExecutor();
           executor.setCorePoolSize(8);
           executor.setMaxPoolSize(32);
           executor.setQueueCapacity(100);
           executor.setThreadNamePrefix("app-async-");
           executor.setTaskDecorator(decorator);
           executor.initialize();
           return executor;
       }
   }
   ```

   ### 3.7. Custom business metrics (если нужны)

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
               .register(registry);
           this.paymentProcessingTimer = Timer.builder("payment_processing_seconds")
               .description("Payment processing duration")
               .publishPercentiles(0.5, 0.95, 0.99)
               .register(registry);
           this.orderAmountSummary = DistributionSummary.builder("order_amount_rubles")
               .baseUnit("rubles")
               .register(registry);
       }

       public void recordOrderCreated(String type) {
           orderCreatedCounter.increment();
       }

       public Timer.Sample startPaymentTimer() {
           return Timer.start();
       }

       public void recordPaymentDuration(Timer.Sample sample) {
           sample.stop(paymentProcessingTimer);
       }

       public void recordOrderAmount(BigDecimal amount) {
           orderAmountSummary.record(amount.doubleValue());
       }
   }
   ```

   ### 3.8. /actuator/info с git/build info

   build.gradle.kts:
   ```kotlin
   plugins {
       id("com.gorylenko.gradle-git-properties") version "2.4.1"
   }
   springBoot {
       buildInfo()
   }
   ```

   application.yml:
   ```yaml
   management.info:
     git:
       mode: full
     build:
       enabled: true
   ```

4. **Самопроверка перед выдачей** (`R-OBS-*`):
   - Logback-spring.xml с двумя профилями (text dev / JSON prod).
   - JSON-encoder включает MDC keys (traceId, requestId, userId).
   - `management.metrics.tags` стандартизованы (service, env, version).
   - `management.endpoints.web.exposure.include` — explicit list.
   - `management.server.port` отдельный.
   - `otel.traces.sampler.arg: 0.1` (10%, не 100%).
   - MdcFilter с MDC.clear() в finally.
   - TaskDecorator для @Async.
   - HealthIndicator per external system — генерируется через `ucp-resilience-design` или `ucp-integration-design` (отдельные скиллы).

5. **Структура вывода:**
   1. **Решения** — backend (Loki/ELK/Datadog), sampling rate, нужны ли custom metrics.
   2. **Дерево новых файлов** — Logback config, MdcFilter, AsyncConfig, OrderMetrics (если нужны).
   3. **Каждый файл — отдельный code block** с путём.
   4. **Patch для existing файлов** — `application.yml`, `bootstrap/build.gradle.kts`.
   5. **Заметки по реализации:**
      - Команды: `./gradlew bootJar`, `curl :8081/actuator/health`, `curl :8081/actuator/prometheus`.
      - **TODO для пользователя:** настроить OTel Collector endpoint в env-vars; настроить Prometheus scraping config (scrape_configs.job: order-service, target: localhost:8081); настроить Loki/ELK ingestion для JSON-логов; alerts в Prometheus AlertManager (см. Style Guide §7).
   6. **Финальный шаг:** «после генерации запусти `ucp-observability-review` для верификации».

## Что НЕ делает

- HealthIndicator для внешних систем (Sber, OdnaKassa) — `ucp-resilience-design` / `ucp-integration-design`.
- Resilience4j metrics — генерируются автоматически через `ucp-integration-design`.
- Cache metrics — `ucp-caching-design` (auto через Spring Cache).
- Kafka consumer lag metrics — `ucp-kafka-design` (auto через spring-kafka).
- Alerts в Prometheus / runbooks — это infra-уровень, не код сервиса.

После — обязательно `ucp-observability-review` для верификации.

$ARGUMENTS
