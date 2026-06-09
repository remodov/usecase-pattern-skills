---
name: ucp-resilience-review
description: Ревью защиты Java/Spring-сервиса от отказов внешних систем (коды R-RES-*) — per-system isolation OkHttpClient/pool/bulkhead, @CircuitBreaker/@Bulkhead/@Retry на out-adapter методах, retry только при идемпотентности, HealthIndicator per-system с TTL.
when_to_use: Ревью out-adapter, *ClientConfig, application.yml с resilience4j-блоком, новых HTTP-клиентов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью resilience

Ты ревьюишь Java/Spring-код out-adapter'ов, *ClientConfig классы, application.yml с resilience4j-конфигом — на соответствие Resilience Style Guide. Главные точки контроля: per-system isolation, аннотации resilience на adapter-методах, retry-policy с учётом идемпотентности, bulkhead semaphore, sleep-loop в sync-handler'ах, связка с OpenAPI generator.

## Зависимости

- **`.claude/docs/backend/resilience/resilience-rules.md`** — индекс всех правил (полный текст с примерами — соответствующий `*-style-guide.md`). Каждое нарушение цитируется кодом из подгрупп: `R-RES-WHERE-*` (где какая защита), `R-RES-ISO-*` (per-system isolation), `R-RES-TO-*` (timeouts), `R-RES-CB-*` (circuit breaker), `R-RES-RE-*` (retry), `R-RES-BH-*` (bulkhead), `R-RES-FB-*` (fallback), `R-RES-CFG-*` (конфигурация), `R-RES-OAS-*` (связка с OpenAPI generator), `R-RES-HC-*` (health checks), `R-RES-ASYNC-*` (async и polling), `R-RES-OBS-*` (observability).
- Парные документы: `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-19` для idempotency-зависимого retry), `backend/rest-api/rest-api-rules.md` (`R-OAS-*` для OpenAPI-first).

## Инструкции

1. **Прочти индекс правил** `.claude/docs/backend/resilience/resilience-rules.md`. Цитируй конкретные коды правил (`R-RES-CB-1`, `R-RES-OAS-X1`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые файлы в `*-out-adapter/`, `common-client-config/`.
   - Найди новые/изменённые `*ClientConfig`, `*ClientAdapter`, `application*.yml` с `resilience4j` блоком, `*HealthIndicator`.
   - Найди файлы с `Thread.sleep` — кандидаты на нарушение `R-RES-ASYNC-X1`.
   - Найди файлы с импортами `io.github.resilience4j.*` — место аннотаций.

3. **Прогон по подгруппам кодов.** Проверяй каждое применимое правило:
   - **`R-RES-WHERE-*`** — Resilience4j используется только для outbound HTTP / inter-service, не для repository / JOOQ / локальных операций.
   - **`R-RES-ISO-*`** — каждая внешняя система имеет свой `OkHttpClient` / `RestClient` bean с собственным pool/dispatcher, не shared. Имена beans/instances совпадают с system name.
   - **`R-RES-TO-*`** — connectTimeout < readTimeout < callTimeout, обоснования отклонений от типовых в yml-комментариях.
   - **`R-RES-CB-*`** — `@CircuitBreaker(name = "<system>")` на public-методе adapter (не на generated client, не на helper, не на репозитории), sliding-window count-based, failure rate 50% (30% для критичных), wait 30s, half-open 3 calls, slow-call threshold = readTimeout/2.
   - **`R-RES-RE-*`** — retry только при идемпотентности (GET либо `Idempotency-Key` per `AUTH-19`); не на 4xx; exp backoff обязателен; not Spring-Retry; in-memory <5s vs task-queue >30s.
   - **`R-RES-BH-*`** — `@Bulkhead(name = "<system>")` semaphore-based (не thread-pool); maxConcurrent = pool × 0.8 (срабатывает раньше pool exhaustion); maxWait 100ms.
   - **`R-RES-FB-*`** — fallback допустим для cached read / default для read / async-mode (queue + 202 Accepted) для write; не для money с null/zero; не silent success; не каскадный fallback без своего CB.
   - **`R-RES-CFG-*`** — конфиг через `application.yml` с `configs.default` и `instances.<name>` (Spring Cloud Config friendly), не через `@Bean CircuitBreakerConfig.custom()`.
   - **`R-RES-OAS-*`** — аннотации на adapter-методе (не на generated `<X>Api`); для нового кода `openapi-generator` target = `spring-restclient`; mapper между generated DTO и domain-типами обязателен; generated DTO не уходит наверх из port-метода.
   - **`R-RES-HC-*`** — `<System>HealthIndicator` per system, cached с TTL 30s, light probe (не business-операция).
   - **`R-RES-ASYNC-*`** — sleep-loop в sync-handler запрещён (использовать task-queue); `Thread.sleep > 5s` — запах task-queue; для CompletableFuture-возврата — `@TimeLimiter`.
   - **`R-RES-OBS-*`** — `resilience4j-micrometer` подключён, metrics не отключены, OTel-spans содержат `circuit_breaker.state`.

4. **При ревью кода ищи паттерны-нарушения:**
   - `OkHttpClient.Builder().build()` без явных timeouts — `R-RES-TO-X1`.
   - Один `OkHttpClient` bean / один `Dispatcher` для нескольких систем — `R-RES-ISO-X1`.
   - `@CircuitBreaker(name = "default")` или без `name` — `R-RES-CB-X3`.
   - `@CircuitBreaker` на `*Repository` / `*Service` / handler без HTTP — `R-RES-CB-X1`.
   - `@Retry` без `@CircuitBreaker` или без `enable-exponential-backoff` — `R-RES-RE-X3`.
   - `@Retryable` (Spring-Retry) на adapter-методе — `R-RES-RE-X4`.
   - Custom `try { ... } catch { failures.incrementAndGet(); ... }` — `R-RES-CB-X2`.
   - `Thread.sleep` в коде adapter / handler / use-case — `R-RES-ASYNC-X1` или `R-RES-ASYNC-X2`.
   - `@CircuitBreaker` или `@Retry` непосредственно на generated `*Api` interface — `R-RES-OAS-X1`.
   - `<X>Api` сгенерирован Retrofit2 для нового сервиса — `R-RES-OAS-2` (предложить `spring-restclient`).
   - Public-метод out-adapter возвращает generated DTO (`SberRegisterResponse`, etc.) — `R-RES-OAS-X3`.
   - `HealthIndicator.health()` без кеша / делает business-операцию — `R-RES-HC-X1` / `R-RES-HC-X2`.
   - Fallback-метод возвращает `Money.ZERO` / `null` / пустую коллекцию для money-результата — `R-RES-FB-X1`.
   - В `application.yml` `resilience4j.circuitbreaker.instances` отсутствует / пуст, при этом аннотации в коде — конфиг разъехался.
   - `management.metrics.enable.resilience4j: false` — `R-RES-OBS-X1`.

5. **При ревью `*ClientConfig` / `application.yml`:**
   - На каждую внешнюю систему — отдельный bean OkHttpClient/RestClient с уникальным `@Qualifier` или `@Bean(name)`.
   - Connection pool sizing: `maxConcurrent × 1.2`. Total всех систем ≤ HikariCP / 2.
   - Configs `resilience4j.{circuitbreaker,bulkhead,retry}.instances.<system>` определены с `base-config: default`.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-finding-format.md` (`RFF-1`..`RFF-16`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`R-RES-CB-1`, `R-RES-OAS-X1`).

7. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — нарушения, ведущие к регрессу под нагрузкой или денежным багам:
     - shared OkHttp pool на разные системы (`R-RES-ISO-X1`)
     - `@Retry` на write без Idempotency-Key (`R-RES-RE-X1`) — может списать дважды
     - sleep-loop в sync-handler (`R-RES-ASYNC-X1`) — исчерпает thread-pool
     - тихий fallback с success для money (`R-RES-FB-X1`, `R-RES-FB-X2`)
     - аннотации на generated interface (`R-RES-OAS-X1`) — затрутся
     - отсутствие CB на adapter-методе outbound (`R-RES-CB-1`)
   - **Предупреждение** — отклонения от конвенций:
     - `name = "default"` вместо per-system (`R-RES-CB-X3`)
     - thread-pool bulkhead вместо semaphore (`R-RES-BH-X1`)
     - sync-probe без кеша в HealthIndicator (`R-RES-HC-X1`)
     - Retrofit2 для нового сервиса (`R-RES-OAS-2`)
   - **Замечание** — стилистика:
     - timeouts отличаются от типовых без комментария-обоснования (`R-RES-TO-2`)
     - программный `CircuitBreakerConfig.custom()` вместо yml (`R-RES-CFG-X1`)

## Что не входит

- Чистая business-логика и UseCase Pattern — `ucp-pattern-review`.
- Domain model, агрегаты — `ucp-ddd-tactical-review`.
- jOOQ persistence layer — `ucp-jooq-review`.
- REST API contract (URL, JSON, ошибки) — `ucp-api-review`.
- Spring Security / RBAC / ABAC — `ucp-auth-review`.
- PostgreSQL runtime (WAL, autovacuum, locks) — `ucp-pg-runtime-review`.
- Java code style (нейминг, импорты) — `ucp-java-style-review`.
- Observability (logging, metrics, tracing) сама по себе — отдельный гайд (в планах). Этот скилл проверяет только resilience-аспекты observability (`R-RES-OBS-*`).

$ARGUMENTS
