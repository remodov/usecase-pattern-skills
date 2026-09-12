---
name: ucp-resilience-review
description: Ревью защиты Java/Spring-сервиса от отказов внешних систем — per-system isolation OkHttpClient/pool/bulkhead, @CircuitBreaker/@Bulkhead/@Retry на out-adapter методах, retry только при идемпотентности, HealthIndicator per-system с TTL.
when_to_use: Ревью out-adapter, *ClientConfig, application.yml с resilience4j-блоком, новых HTTP-клиентов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью resilience

Ты ревьюишь Java/Spring-код out-adapter'ов, *ClientConfig классы, application.yml с resilience4j-конфигом — на соответствие требованиям `resilience/*`. Главные точки контроля: per-system isolation, аннотации resilience на adapter-методах, retry-policy с учётом идемпотентности, bulkhead semaphore, sleep-loop в sync-handler'ах, связка с OpenAPI generator.

## Зависимости

- **`.claude/docs/backend/resilience/spec.md`** — индекс всех правил (полный текст с примерами — `references/<lang>/implementation.md`). Каждое нарушение цитируется кодом из подгрупп: `R-RES-WHERE-*` (где какая защита), `R-RES-ISO-*` (per-system isolation), `R-RES-TO-*` (timeouts), `R-RES-CB-*` (circuit breaker), `R-RES-RE-*` (retry), `R-RES-BH-*` (bulkhead), `R-RES-FB-*` (fallback), `R-RES-CFG-*` (конфигурация), `R-RES-OAS-*` (связка с OpenAPI generator), `R-RES-HC-*` (health checks), `R-RES-ASYNC-*` (async и polling), `R-RES-OBS-*` (observability).
- Парные документы: `backend/auth-patterns/spec.md` (`auth-patterns/money-commands-need-idempotency-key` для idempotency-зависимого retry), `backend/rest-api/spec.md` (`R-OAS-*` для OpenAPI-first).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/resilience/spec.md`. Цитируй конкретные коды правил (`resilience/breaker-on-adapter-method`, `resilience/breaker-on-adapter-method`), не префикс.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на недавно изменённые файлы в `*-out-adapter/`, `common-client-config/`.
   - Найди новые/изменённые `*ClientConfig`, `*ClientAdapter`, `application*.yml` с `resilience4j` блоком, `*HealthIndicator`.
   - Найди файлы с `Thread.sleep` — кандидаты на нарушение `resilience/no-long-synchronous-waits`.
   - Найди файлы с импортами `io.github.resilience4j.*` — место аннотаций.

3. **Прогон по подгруппам кодов.** Проверяй каждое применимое правило:
   - **`R-RES-WHERE-*`** — Resilience4j используется только для outbound HTTP / inter-service, не для repository / JOOQ / локальных операций.
   - **`R-RES-ISO-*`** — каждая внешняя система имеет свой `OkHttpClient` / `RestClient` bean с собственным pool/dispatcher, не shared. Имена beans/instances совпадают с system name.
   - **`R-RES-TO-*`** — connectTimeout < readTimeout < callTimeout, обоснования отклонений от типовых в yml-комментариях.
   - **`R-RES-CB-*`** — `@CircuitBreaker(name = "<system>")` на public-методе adapter (не на generated client, не на helper, не на репозитории), sliding-window count-based, failure rate 50% (30% для критичных), wait 30s, half-open 3 calls, slow-call threshold = readTimeout/2.
   - **`R-RES-RE-*`** — retry только при идемпотентности (GET либо `Idempotency-Key` per `auth-patterns/money-commands-need-idempotency-key`); не на 4xx; exp backoff обязателен; not Spring-Retry; in-memory <5s vs task-queue >30s.
   - **`R-RES-BH-*`** — `@Bulkhead(name = "<system>")` semaphore-based (не thread-pool); maxConcurrent = pool × 0.8 (срабатывает раньше pool exhaustion); maxWait 100ms.
   - **`R-RES-FB-*`** — fallback допустим для cached read / default для read / async-mode (queue + 202 Accepted) для write; не для money с null/zero; не silent success; не каскадный fallback без своего CB.
   - **`R-RES-CFG-*`** — конфиг через `application.yml` с `configs.default` и `instances.<name>` (Spring Cloud Config friendly), не через `@Bean CircuitBreakerConfig.custom()`.
   - **`R-RES-OAS-*`** — аннотации на adapter-методе (не на generated `<X>Api`); для нового кода `openapi-generator` target = `spring-restclient`; mapper между generated DTO и domain-типами обязателен; generated DTO не уходит наверх из port-метода.
   - **`R-RES-HC-*`** — `<System>HealthIndicator` per system, cached с TTL 30s, light probe (не business-операция).
   - **`R-RES-ASYNC-*`** — sleep-loop в sync-handler запрещён (использовать task-queue); `Thread.sleep > 5s` — запах task-queue; для CompletableFuture-возврата — `@TimeLimiter`.
   - **`R-RES-OBS-*`** — `resilience4j-micrometer` подключён, metrics не отключены, OTel-spans содержат `circuit_breaker.state`.

4. **При ревью кода ищи паттерны-нарушения:**
   - `OkHttpClient.Builder().build()` без явных timeouts — `resilience/timeout-hierarchy`.
   - Один `OkHttpClient` bean / один `Dispatcher` для нескольких систем — `resilience/client-per-external-system`.
   - `@CircuitBreaker(name = "default")` или без `name` — `resilience/instance-names-match-system`.
   - `@CircuitBreaker` на `*Repository` / `*Service` / handler без HTTP — `resilience/no-protection-around-local-operations`.
   - `@Retry` без `@CircuitBreaker` или без `enable-exponential-backoff` — `resilience/retry-with-backoff-and-limit`.
   - `@Retryable` (Spring-Retry) на adapter-методе — `resilience/retry-with-backoff-and-limit`.
   - Custom `try { ... } catch { failures.incrementAndGet(); ... }` — `resilience/no-custom-breaker`.
   - `Thread.sleep` в коде adapter / handler / use-case — `resilience/no-long-synchronous-waits` или `resilience/no-long-synchronous-waits`.
   - `@CircuitBreaker` или `@Retry` непосредственно на generated `*Api` interface — `resilience/breaker-on-adapter-method`.
   - `<X>Api` сгенерирован Retrofit2 для нового сервиса — `resilience/client-generated-from-contract` (предложить `spring-restclient`).
   - Public-метод out-adapter возвращает generated DTO (`SberRegisterResponse`, etc.) — `R-RES-OAS-X3`.
   - `HealthIndicator.health()` без кеша / делает business-операцию — `resilience/cached-health-probe-per-system` / `resilience/cached-health-probe-per-system`.
   - Fallback-метод возвращает `Money.ZERO` / `null` / пустую коллекцию для money-результата — `resilience/fallback-does-not-fake-success`.
   - В `application.yml` `resilience4j.circuitbreaker.instances` отсутствует / пуст, при этом аннотации в коде — конфиг разъехался.
   - `management.metrics.enable.resilience4j: false` — `resilience/resilience-state-is-observable`.

5. **При ревью `*ClientConfig` / `application.yml`:**
   - На каждую внешнюю систему — отдельный bean OkHttpClient/RestClient с уникальным `@Qualifier` или `@Bean(name)`.
   - Connection pool sizing: `maxConcurrent × 1.2`. Total всех систем ≤ HikariCP / 2.
   - Configs `resilience4j.{circuitbreaker,bulkhead,retry}.instances.<system>` определены с `base-config: default`.

6. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`). Read-проверка строки обязательна. В качестве `<КодПравила>` — конкретный код (`resilience/breaker-on-adapter-method`, `resilience/breaker-on-adapter-method`).

7. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — нарушения, ведущие к регрессу под нагрузкой или денежным багам:
     - shared OkHttp pool на разные системы (`resilience/client-per-external-system`)
     - `@Retry` на write без Idempotency-Key (`resilience/retry-only-when-safe`) — может списать дважды
     - sleep-loop в sync-handler (`resilience/no-long-synchronous-waits`) — исчерпает thread-pool
     - тихий fallback с success для money (`resilience/fallback-does-not-fake-success`, `resilience/fallback-does-not-fake-success`)
     - аннотации на generated interface (`resilience/breaker-on-adapter-method`) — затрутся
     - отсутствие CB на adapter-методе outbound (`resilience/breaker-on-adapter-method`)
   - **Предупреждение** — отклонения от конвенций:
     - `name = "default"` вместо per-system (`resilience/instance-names-match-system`)
     - thread-pool bulkhead вместо semaphore (`resilience/bulkhead-is-semaphore-based`)
     - sync-probe без кеша в HealthIndicator (`resilience/cached-health-probe-per-system`)
     - Retrofit2 для нового сервиса (`resilience/client-generated-from-contract`)
   - **Замечание** — стилистика:
     - timeouts отличаются от типовых без комментария-обоснования (`resilience/timeout-hierarchy`)
     - программный `CircuitBreakerConfig.custom()` вместо yml (`resilience/declarative-configuration`)

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
