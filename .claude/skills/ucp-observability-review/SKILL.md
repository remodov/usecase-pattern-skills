---
name: ucp-observability-review
description: Ревью наблюдаемости Java/Spring-сервиса (требования observability/*) — structured logging с MDC без PII, Micrometer-метрики, OpenTelemetry tracing, Actuator health-checks, context propagation, SLO и alerts.
when_to_use: Изменения в logback*.xml, MetricsConfig/OtelConfig/HealthIndicator/MdcFilter, management/logging-блоках application.yml.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью observability

Ты ревьюишь логирование, метрики, tracing, health-checks и context propagation в Java/Spring-сервисе на соответствие требованиям `observability/*`.

## Зависимости

- **`.claude/docs/backend/observability/spec.md`** — индекс всех правил (полный текст с примерами — `references/<lang>/implementation.md`). Подгруппы: `R-OBS-LOG-*` (logging), `R-OBS-MTR-*` (metrics), `R-OBS-TRC-*` (tracing), `R-OBS-HC-*` (health checks), `R-OBS-CFG-*` (config), `R-OBS-CTX-*` (MDC), `R-OBS-SLO-*` (SLO/alerts).
- Парные: `backend/auth-patterns/spec.md` (`auth-patterns/no-pii-in-logs-and-events` — PII в логах ЗАПРЕЩЕНО, главное правило observability ↔ security), `backend/rest-api/spec.md` (`rest-api/trace-context-header` — traceparent), `backend/resilience/spec.md` (`R-RES-OBS-*` — CB metrics), `backend/caching/spec.md` (`R-CACHE-OBS-*`), `backend/kafka/spec.md` (`R-KFK-OBS-*` — consumer lag).

## Инструкции


**Гейты проекта.** Часть требований домена закрыта проверками, которые заводит `ucp-bootstrap-design` (каталог — `_meta/project-gates.md`). Если проверка в проекте не заведена, требования, ссылающиеся на неё, фактически держатся ревью — это **отдельная находка**, и она важнее единичного нарушения.

1. **Прочти индекс правил** `.claude/docs/backend/observability/spec.md`. Цитируй конкретные коды (`observability/no-pii-in-logs`, `observability/context-set-at-edge-and-cleared`).

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на `*Logback*`, `logback*.xml`, `*MetricsConfig*`, `*OtelConfig*`, `*HealthIndicator*`, `*MdcFilter*`.
   - `application*.yml` с `management.*`, `logging.*`, `otel.*`.
   - Файлы с импортами `org.slf4j.*`, `io.micrometer.*`, `io.opentelemetry.*`.
   - Любой код с `log.info/warn/error/debug`, `MeterRegistry`, `Tracer`, `MDC`, `@WithSpan`.

3. **Прогон по подгруппам:**
   - **`R-OBS-LOG-*`** — JSON в prod-профиле, `@Slf4j` Lombok, `{}` placeholders (не concat), уровни (ERROR/WARN/INFO правильно), MDC fields в каждой записи, нет PII (см. `auth-patterns/no-pii-in-logs-and-events`), нет `System.out`/`printStackTrace`, ERROR с stack trace через 2-arg, нет full request body.
   - **`R-OBS-MTR-*`** — Micrometer + Prometheus registry; стандартные dimensions через `management.metrics.tags`; RED/USE auto-метрики; custom business metrics через MeterRegistry; tags низкой cardinality (не user_id/request_id); `/actuator/prometheus` не публично без auth.
   - **`R-OBS-TRC-*`** — OTel auto-инструментация; traceparent propagation; manual spans с try-finally; span attributes без PII; sampling 1-10% (не 100%); trace-id в MDC через OTel appender.
   - **`R-OBS-HC-*`** — separate liveness/readiness; custom HealthIndicator per external system с TTL; нет business-state в health; liveness не зависит от внешних систем; нет business-операций в health-probe; `/actuator/info` с git sha + version.
   - **`R-OBS-CFG-*`** — отдельный management port; exposure explicit list (не `*`); не exposed `/actuator/env`/`/heapdump` публично; logback-spring.xml с разными профилями (text dev, JSON prod).
   - **`R-OBS-CTX-*`** — MdcFilter populates request-Id; OTel auto-добавляет traceId/spanId; @Async через TaskDecorator; userId после JWT; **обязательно** MDC.clear() в finally.
   - **`R-OBS-SLO-*`** — SLO defined для critical endpoints; multi-window burn rate alerts; error budget; alerts с runbook'ами; не alert на каждый ERROR.

4. **Ищи паттерны-нарушения:**
   - `log.info("Email: {}", user.getEmail())` или `log.error("PII: {}", customer)` — `observability/no-pii-in-logs` + `auth-patterns/no-pii-in-logs-and-events` критическое.
   - `System.out.println` / `e.printStackTrace()` / `System.err.println` — `observability/no-direct-stdout-logging`.
   - `log.info("Message " + value)` (string-concat) — `observability/parameterized-log-messages`.
   - `log.error("Failed: " + e.getMessage())` без передачи `e` как exception arg — `observability/parameterized-log-messages`.
   - `log.info("Body: {}", request)` где request содержит PII — `observability/no-pii-in-logs` + `observability/no-pii-in-logs`.
   - `Counter.builder("...").tag("user_id", userId)` или `Tag.of("request_id", id)` — `observability/low-cardinality-labels` (cardinality explosion).
   - `MeterRegistry meterRegistry = ...` без явного Prometheus registry в config — `observability/metrics-are-exported`.
   - `management.endpoints.web.exposure.include: '*'` или `prometheus` без network policy — `observability/management-endpoints-restricted` / `observability/management-endpoints-restricted`.
   - `otel.traces.sampler.arg: 1.0` в `application-prod.yml` — `observability/sampling-strategy`.
   - `span.setAttribute("customer.email", ...)` или span с PII — `observability/manual-spans-are-closed`.
   - `var span = tracer.spanBuilder(...).startSpan(); ... business logic ... span.end();` без try/finally — `observability/manual-spans-are-closed`.
   - `@Async` без custom TaskDecorator с MDC propagation — `observability/context-propagated-to-async` / `observability/context-propagated-to-async`.
   - HealthIndicator делает `restTemplate.exchange(...)` каждый запрос (без TTL-кеша) — `observability/health-check-is-technical` / `resilience/cached-health-probe-per-system`.
   - `if (orderCount > 1000) return Health.down()` — `observability/health-check-is-technical`.
   - liveness probe возвращает DOWN при недоступности БД — `observability/liveness-and-readiness-split`.
   - `application-prod.yml` exposes `env`, `heapdump`, `threaddump`, `loggers` без security — `observability/management-endpoints-restricted`.
   - Один port для business + actuator (`management.server.port` отсутствует) — `observability/separate-management-port`.
   - `MDC.put("requestId", ...)` без `MDC.clear()` в `finally` — `observability/context-set-at-edge-and-cleared` (security incident — leaked context).
   - `MDC.put` в Service / Handler / Controller (не в filter) — `observability/context-set-at-edge-and-cleared`.
   - Alerts на каждый ERROR в логах без burn-rate — `observability/burn-rate-alerting`.

5. **При ревью logback-spring.xml:**
   - `<springProfile name="prod">` использует `LogstashEncoder` или `EcsEncoder`.
   - `<springProfile name="dev,test">` — текстовый pattern.
   - `<includeMdcKeyName>` для traceId/requestId/userId.
   - root level: `INFO` (не DEBUG в проде).

6. **При ревью application.yml:**
   - `management.server.port: 8081` (отдельный port).
   - `management.endpoints.web.exposure.include: health,info,metrics,prometheus` (explicit, не `*`).
   - `management.metrics.tags.{service,env,version}` — стандартизованы.
   - `otel.traces.sampler.arg: 0.1` (не `1.0` в проде).
   - `logging.level.root: INFO` в prod profile.
   - `management.endpoint.health.probes.enabled: true` для liveness/readiness.

7. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/shared/review-format/spec.md` (`review-format/*`).

8. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично:**
     - PII в логах / span-attributes / metrics (`observability/no-pii-in-logs`, `observability/manual-spans-are-closed`) — security incident, GDPR/PII-compliance.
     - MDC без `MDC.clear()` — leaked context cross-request, чужой userId в логах другого пользователя.
     - High-cardinality metric tags — Prometheus OOM.
     - liveness зависит от внешних систем — restart loop в K8s.
     - Exposed `/actuator/env`/`/heapdump` без auth публично — info disclosure.
     - Sampling 100% tracing в проде — storage explosion + cost.
   - **Предупреждение:**
     - `e.printStackTrace()` / `System.out` — silent dropping.
     - String-concat в log args — performance.
     - INFO на каждый HTTP request — log noise.
     - `@Async` без TaskDecorator — traces разрываются.
     - Health-probe без TTL-кеша — DDoS внешней системы.
   - **Замечание:**
     - Не-стандартизованные dimensions (`app=foo` vs `service=foo`).
     - Default log levels для dependencies слишком verbose.
     - Отсутствие `git.commit.id` в `/actuator/info`.

## Что не входит

- Resilience4j metrics — `ucp-resilience-review` (`R-RES-OBS-*`).
- Cache hit rate metrics — `ucp-caching-review` (`R-CACHE-OBS-*`).
- Kafka consumer lag — `ucp-kafka-review` (`R-KFK-OBS-*`).
- PII detection in code (вне логов/spans) — `ucp-auth-review` (`auth-patterns/no-pii-in-logs-and-events`).
- Alerting rules в Prometheus/Grafana — это infra-уровень, не codified в этом скилле.
- Service Mesh observability (Istio sidecar metrics) — отдельная тема.

$ARGUMENTS
