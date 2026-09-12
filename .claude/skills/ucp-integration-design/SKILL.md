---
name: ucp-integration-design
description: Сгенерировать скелет outbound-интеграции с внешней системой на Java/Spring — port в core/, client-generator с openapi-generator (spring-restclient), out-adapter с CB/Bulkhead/Retry, Mapper, HealthIndicator, exception hierarchy.
when_to_use: Триггеры — «сделай адаптер для X», «новый клиент к Y», «подключаем интеграцию с Z». При новом outbound-клиенте или внешней системе.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# Outbound-интеграция — проектирование

Ты проектируешь и генерируешь полный скелет outbound-интеграции с внешней системой по требованиям `resilience/*`. Цель — сервис получает законченный, рабочий, проходящий `ucp-resilience-review` модуль для интеграции, не «сборную солянку из 7 ручных шагов».

## Инструкции

1. **Прочитай требования** в порядке:
   - `.claude/docs/backend/resilience/spec.md` — главный (правила `R-RES-*`).
   - `.claude/docs/backend/auth-patterns/spec.md` — `auth-patterns/money-commands-need-idempotency-key` для решения по retry.
   - `.claude/docs/backend/rest-api/spec.md` — `R-OAS-*` (OpenAPI для генерации clients), `R-HDR-*` (заголовки).
   - `.claude/docs/backend/java/spring-bootstrap/spec.md` — `BS-*` для gradle multi-module setup.
   - `.claude/docs/backend/usecase-pattern/spec.md` — на Уровне 3 для размещения port в `core/port/out/client/`.

2. **Уточни параметры интеграции** (один по одному, если пользователь не дал):
   - **Имя системы** (slug): `twilio`, `yandex-pay`, `sber`, `fns-receipt`. Имя = идентификатор для всех артефактов: модули `<system>-client-generator`, `<system>-out-adapter`, beans `@Bean("<system>RestClient")`, R4J instances `<system>`.
   - **OpenAPI-спека:** URL внешней документации, путь к локальному YAML, либо «нет спеки → сгенерируй минимальную из описания операций». Если спеки нет — пометь как **TODO для пользователя**.
   - **Типы операций:**
     - **Read-heavy** (GET-эквиваленты): `findOrder`, `getStatus`, `getCatalog` → idempotent, `@Retry` ОК (`resilience/retry-only-when-safe`).
     - **Write с Idempotency-Key:** `register`, `confirmPayment` с заголовком `Idempotency-Key` (см. `auth-patterns/money-commands-need-idempotency-key`) → `@Retry` ОК.
     - **Write без Idempotency-Key:** `createUser`, `sendSms` → `@Retry` ЗАПРЕЩЁН (`resilience/retry-only-when-safe`), только CB+Bulkhead.
     - **Long-running:** ответ `>30s` или требует polling → задача для async pattern (`resilience/async-calls-need-time-limit`), не sync-вызов. Генерируется task-queue, не sleep-loop.
   - **Критичность:**
     - **Money / денежные операции** → CB failure rate `30%` (`resilience/breaker-window-and-thresholds`), fallback = task-queue, **не** null/zero.
     - **Non-money** → CB failure rate `50%` (default).
   - **Авторизация:** `none` (публичный API), `apiKey` (header `Authorization: <key>`), `bearer` (JWT/static), `oauth2-clientCredentials`, `mTLS`. См. `auth-patterns/service-to-service-authenticated`/`auth-patterns/service-to-service-authenticated`.

3. **Определи уровень зрелости проекта** (см. `backend/usecase-pattern/spec.md` §2). Outbound-интеграции с domain port в `core/` уместны на **Уровне 3** (DDD + Hexagonal). На Уровне 1–2 — `<System>Client` инжектится в `<Operation>CommandHandler` напрямую, без port-абстракции. Если Уровень 1–2 — упрости вывод (без отдельного `<System>Port`-интерфейса).

4. **Произведи код.** Lombok-defaults обязательны (`java-style/boilerplate-is-generated`–`java-style/builder-used-sparingly`). Не цитируй коды правил в комментариях кода (`java-style/no-rule-codes-or-history-in-code`).

   ### 4.1. Доменный port (`core/`, Уровень 3)
   ```
   core/src/main/java/<pkg>/core/port/out/client/
     <System>Port.java           — interface с domain-методами
   core/src/main/java/<pkg>/core/port/out/
     <Op>Command.java, <Op>Result.java — record'ы запроса и ответа порта (в эталоне: PartnerRequest, PartnerResponseDto)
   core/src/main/java/<pkg>/core/exception/
     <System>PortException.java  — abstract base, extends RuntimeException
   ```

   ### 4.2. Client-generator module
   - Создать gradle-модуль `<system>-client-generator/` с `build.gradle.kts`:
     - Плагин `org.openapi.generator`.
     - `generatorName = "spring-restclient"` (`resilience/client-generated-from-contract`). Для legacy-проектов на Retrofit2 — указать в комментарии «допустим `okhttp-gson`, но новый код — spring-restclient».
     - `inputSpec = "$projectDir/src/main/resources/openapi/<system>.openapi.yaml"`.
     - `outputDir = "$buildDir/generated/sources/openapi"` (не коммитится, `resilience/client-generated-from-contract`).
     - `apiPackage = "<pkg>.<system>.generated.api"`, `modelPackage = "<pkg>.<system>.generated.model"`.
     - `configOptions`: `useSpringBoot3 = true`, `useJakartaEe = true`.
   - В `src/main/resources/openapi/<system>.openapi.yaml`:
     - Если пользователь дал YAML — скопировать.
     - Если нет — minimal-spec с одной phantom-операцией + комментарий «**TODO:** заменить на реальную спеку от <system>».

   ### 4.3. Out-adapter module
   ```
   <system>-out-adapter/
     build.gradle.kts            — depends on :<system>-client-generator + :core
     src/main/java/<pkg>/adapter/out/<system>/
       <System>ClientConfig.java         — @Configuration с @Bean RestClient + Settings
       <System>ClientSettings.java       — @ConfigurationProperties("client.<system>")
       <System>ClientAdapter.java        — implements <System>Port
       <System>Mapper.java               — @Component, generated DTO ↔ domain
       <System>HealthIndicator.java      — implements HealthIndicator
       exception/
         <System>Exception.java          — extends <System>PortException
         <System>ClientException.java    — 4xx
         <System>ServerException.java    — 5xx
   ```

   **`<System>ClientSettings.java`:**
   ```java
   @ConfigurationProperties("client.<system>")
   @Validated
   public record <System>ClientSettings(
       @NotNull String baseUrl,
       @NotNull Duration connectTimeout,    // R-RES-TO-1: 2-5s
       @NotNull Duration readTimeout,        // 10-30s, до 60s для тяжёлых; >60s → task-queue
       @NotNull Duration callTimeout,        // ≥ connect + read + 1s buffer
       @Min(1) int maxConcurrent,            // R-RES-ISO-2: pool sizing
       String apiKey                         // null для AUTH=none; обязательно для AUTH=apiKey
   ) {}
   ```

   **`<System>ClientConfig.java`** (для `spring-restclient`):
   ```java
   @Configuration
   @RequiredArgsConstructor
   @EnableConfigurationProperties(<System>ClientSettings.class)
   public class <System>ClientConfig {
       @Bean("<system>RestClient")
       RestClient <system>RestClient(<System>ClientSettings settings) {
           // R-RES-ISO-1: per-system pool + dispatcher
           var requestFactory = ClientHttpRequestFactoryBuilder.jdk()
               .withCustomizer(builder -> builder
                   .connectTimeout(settings.connectTimeout())
                   // ... per-system connection pool
               ).build();
           return RestClient.builder()
               .baseUrl(settings.baseUrl())
               .requestFactory(requestFactory)
               .defaultHeader("Authorization", "Bearer " + settings.apiKey())  // если AUTH=apiKey/bearer
               .build();
       }

       @Bean
       <System>DefaultApi <system>Api(@Qualifier("<system>RestClient") RestClient restClient) {
           var apiClient = new ApiClient(restClient);  // generated по spring-restclient
           apiClient.setBasePath(...);
           return new <System>DefaultApi(apiClient);
       }
   }
   ```

   **`<System>ClientAdapter.java`** (главный артефакт; правила `resilience/breaker-on-adapter-method`, `resilience/breaker-on-adapter-method`):
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class <System>ClientAdapter implements <System>Port {

       private final <System>DefaultApi <system>Api;
       private final <System>Mapper mapper;
       // private final <X>TaskQueue taskQueue;  // если есть fallback на task-queue

       // ВАРИАНТ A: read-heavy / write с Idempotency-Key — все три аннотации
       @CircuitBreaker(name = "<system>", fallbackMethod = "find<X>Fallback")
       @Bulkhead(name = "<system>")
       @Retry(name = "<system>")
       @Override
       public <X>Result find<X>(<X>Command cmd) {
           try {
               var response = <system>Api.<op>(mapper.toApi(cmd));
               return mapper.toDomain(response);
           } catch (HttpClientErrorException e) {
               throw new <System>ClientException(e);
           } catch (HttpServerErrorException e) {
               throw new <System>ServerException(e);
           }
       }

       // ВАРИАНТ B: write без Idempotency-Key — БЕЗ @Retry (R-RES-RE-X1)
       @CircuitBreaker(name = "<system>", fallbackMethod = "create<X>Fallback")
       @Bulkhead(name = "<system>")
       @Override
       public <X>Result create<X>(<X>Command cmd) { ... }

       // Fallback: для money — task-queue + 202 (R-RES-FB-1); для read — cached/empty
       private <X>Result find<X>Fallback(<X>Command cmd, Throwable t) {
           log.warn("<system> unavailable, falling back", t);
           // money: taskQueue.enqueue(...); return <X>Result.queued(...);
           // read: return <X>Result.empty();   // или из локального кеша
       }
   }
   ```

   **`<System>Mapper.java`** (`resilience/mapper-between-client-and-port`):
   - MapStruct interface (по умолчанию `@Mapper(componentModel = "spring")`).
   - Если есть assemble-логика / enum-translation вручную — Plain Java class `@Component` (как в `jooq/mapper-is-explicit-class`).
   - **Никогда** не возвращай generated DTO из port-метода. Адаптер — последняя точка, где видны generated-типы.

   **`<System>HealthIndicator.java`** (`R-RES-HC-*`):
   ```java
   @Component
   @RequiredArgsConstructor
   @Slf4j
   public class <System>HealthIndicator implements HealthIndicator {

       private final <System>DefaultApi <system>Api;
       private final AtomicReference<CachedHealth> cache = new AtomicReference<>();
       private static final Duration TTL = Duration.ofSeconds(30);

       @Override
       public Health health() {
           var cached = cache.get();
           if (cached != null && !cached.isExpired(TTL)) {
               return cached.health();
           }
           var fresh = probe();
           cache.set(new CachedHealth(fresh, Instant.now()));
           return fresh;
       }

       private Health probe() {
           try {
               // light probe — НЕ business-операция (R-RES-HC-X2)
               <system>Api.healthCheck();   // или OPTIONS /, или дешёвый GET
               return Health.up().build();
           } catch (Exception e) {
               return Health.down(e).build();
           }
       }

       private record CachedHealth(Health health, Instant probed) {
           boolean isExpired(Duration ttl) {
               return Duration.between(probed, Instant.now()).compareTo(ttl) > 0;
           }
       }
   }
   ```

   **Exception hierarchy:**
   ```java
   public class <System>Exception extends <System>PortException {
       public <System>Exception(String msg, Throwable cause) { super(msg, cause); }
   }
   public class <System>ClientException extends <System>Exception {  // 4xx
       public <System>ClientException(HttpClientErrorException e) {
           super("<System> client error: " + e.getStatusCode(), e);
       }
   }
   public class <System>ServerException extends <System>Exception {  // 5xx
       public <System>ServerException(HttpServerErrorException e) {
           super("<System> server error: " + e.getStatusCode(), e);
       }
   }
   ```

   ### 4.4. Patch для `bootstrap/src/main/resources/application.yml`
   ```yaml
   client.<system>:
     base-url: ${<SYSTEM>_BASE_URL:https://api.<system>.com}
     connect-timeout: 5s
     read-timeout: 30s
     call-timeout: 36s
     max-concurrent: 20
     api-key: ${<SYSTEM>_API_KEY:}     # если AUTH=apiKey

   resilience4j:
     circuitbreaker:
       configs.default: ...            # если уже не определён
       instances.<system>:
         base-config: default
         failure-rate-threshold: 50    # 30 для money
     bulkhead.instances.<system>:
       max-concurrent-calls: 16        # max-concurrent × 0.8
       max-wait-duration: 100ms
     retry.instances.<system>:         # только если применимо (см. шаг 2)
       max-attempts: 3
       wait-duration: 500ms
       enable-exponential-backoff: true
       exponential-backoff-multiplier: 2.0
       retry-exceptions:
         - java.io.IOException
         - org.springframework.web.client.HttpServerErrorException
       ignore-exceptions:
         - org.springframework.web.client.HttpClientErrorException

   management:
     health:
       <system>:
         enabled: true
   ```

   ### 4.5. settings.gradle.kts patch
   ```kotlin
   include(":<system>-client-generator")
   include(":<system>-out-adapter")
   ```

   ### 4.6. bootstrap/build.gradle.kts patch
   ```kotlin
   dependencies {
       implementation(project(":<system>-out-adapter"))
   }
   ```

5. **Самопроверка перед выдачей.** Пройди эти пункты (`R-RES-*`):
   - Per-system bean'ы (`@Bean("<system>RestClient")`), не shared.
   - Timeouts: `connect < read < call`, `call ≥ connect + read + buffer`.
   - `@CircuitBreaker(name = "<system>")`, `@Bulkhead(name = "<system>")` на каждом public-методе adapter.
   - `@Retry` только если read-heavy ИЛИ write с Idempotency-Key.
   - `4xx`-исключения в `ignore-exceptions` retry-конфига.
   - Fallback не возвращает `null`/`Money.ZERO` для money.
   - HealthIndicator имеет TTL-кеш и light probe.
   - Generated DTO не уходит из port-метода.
   - В коде нет `Thread.sleep` — sync-цикл polling запрещён (`resilience/no-long-synchronous-waits`).

6. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

## Что НЕ делает этот скилл

- Не пишет UseCase / Handler, который дёргает `<System>Port`. Это `ucp-pattern-design`.
- Не пишет тесты. Это `ucp-test-design` (но в выводе указывается чек-лист).
- Не модифицирует REST-контроллеры (inbound). Это `ucp-api-design`.
- Не настраивает базовый gradle multi-module setup, jOOQ codegen, Liquibase. Это `ucp-bootstrap-design`.
- Не делает аналогичную работу для inbound (нашего REST API). Inbound — `ucp-api-design`.

После работы этого скилла **обязательно** запускается `ucp-resilience-review` на новом `<system>-out-adapter/` — это финальная верификация.

$ARGUMENTS
