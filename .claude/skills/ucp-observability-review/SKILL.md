---
name: ucp-observability-review
description: Ревью наблюдаемости — structured logging (JSON в проде, MDC с traceId/requestId/userId, нет PII в логах, @Slf4j через Lombok, {} placeholders), Micrometer-метрики (стандартные dimensions service/env/version, RED/USE, custom business metrics, низкая cardinality tags), OpenTelemetry tracing (auto-инструментация, traceparent propagation, sampling 1-10% + 100% errors, span attributes без PII), Actuator health-checks (separate liveness/readiness, custom HealthIndicator с TTL), config (отдельный management port, exposure explicit list), context propagation (MDC filter с finally clear, TaskDecorator для @Async), SLO + alerts (multi-window burn rate, error budget, runbooks). Опирается на коды R-OBS-*.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью observability

Ты ревьюишь логирование, метрики, tracing, health-checks и context propagation в Java/Spring-сервисе на соответствие Observability Style Guide.

## Зависимости

- **`.claude/docs/observability-style-guide.md`** — единственный источник правил. Подгруппы: `R-OBS-LOG-*` (logging), `R-OBS-MTR-*` (metrics), `R-OBS-TRC-*` (tracing), `R-OBS-HC-*` (health checks), `R-OBS-CFG-*` (config), `R-OBS-CTX-*` (MDC), `R-OBS-SLO-*` (SLO/alerts).
- Парные: `auth-patterns-style-guide.md` (`AUTH-16` — PII в логах ЗАПРЕЩЕНО, главное правило observability ↔ security), `rest-api-rules.md` (`R-HDR-4` — traceparent), `resilience-style-guide.md` (`R-RES-OBS-*` — CB metrics), `caching-style-guide.md` (`R-CACHE-OBS-*`), `kafka-style-guide.md` (`R-KFK-OBS-*` — consumer lag).

## Инструкции

1. **Прочти style guide** из `.claude/docs/observability-style-guide.md`. Цитируй конкретные коды (`R-OBS-LOG-X1`, `R-OBS-CTX-X1`).

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - `git diff` на `*Logback*`, `logback*.xml`, `*MetricsConfig*`, `*OtelConfig*`, `*HealthIndicator*`, `*MdcFilter*`.
   - `application*.yml` с `management.*`, `logging.*`, `otel.*`.
   - Файлы с импортами `org.slf4j.*`, `io.micrometer.*`, `io.opentelemetry.*`.
   - Любой код с `log.info/warn/error/debug`, `MeterRegistry`, `Tracer`, `MDC`, `@WithSpan`.

3. **Прогон по подгруппам:**
   - **`R-OBS-LOG-*`** — JSON в prod-профиле, `@Slf4j` Lombok, `{}` placeholders (не concat), уровни (ERROR/WARN/INFO правильно), MDC fields в каждой записи, нет PII (см. `AUTH-16`), нет `System.out`/`printStackTrace`, ERROR с stack trace через 2-arg, нет full request body.
   - **`R-OBS-MTR-*`** — Micrometer + Prometheus registry; стандартные dimensions через `management.metrics.tags`; RED/USE auto-метрики; custom business metrics через MeterRegistry; tags низкой cardinality (не user_id/request_id); `/actuator/prometheus` не публично без auth.
   - **`R-OBS-TRC-*`** — OTel auto-инструментация; traceparent propagation; manual spans с try-finally; span attributes без PII; sampling 1-10% (не 100%); trace-id в MDC через OTel appender.
   - **`R-OBS-HC-*`** — separate liveness/readiness; custom HealthIndicator per external system с TTL; нет business-state в health; liveness не зависит от внешних систем; нет business-операций в health-probe; `/actuator/info` с git sha + version.
   - **`R-OBS-CFG-*`** — отдельный management port; exposure explicit list (не `*`); не exposed `/actuator/env`/`/heapdump` публично; logback-spring.xml с разными профилями (text dev, JSON prod).
   - **`R-OBS-CTX-*`** — MdcFilter populates request-Id; OTel auto-добавляет traceId/spanId; @Async через TaskDecorator; userId после JWT; **обязательно** MDC.clear() в finally.
   - **`R-OBS-SLO-*`** — SLO defined для critical endpoints; multi-window burn rate alerts; error budget; alerts с runbook'ами; не alert на каждый ERROR.

4. **Ищи паттерны-нарушения:**
   - `log.info("Email: {}", user.getEmail())` или `log.error("PII: {}", customer)` — `R-OBS-LOG-X1` + `AUTH-16` критическое.
   - `System.out.println` / `e.printStackTrace()` / `System.err.println` — `R-OBS-LOG-X2`.
   - `log.info("Message " + value)` (string-concat) — `R-OBS-LOG-X3`.
   - `log.error("Failed: " + e.getMessage())` без передачи `e` как exception arg — `R-OBS-LOG-X4`.
   - `log.info("Body: {}", request)` где request содержит PII — `R-OBS-LOG-X1` + `R-OBS-LOG-X5`.
   - `Counter.builder("...").tag("user_id", userId)` или `Tag.of("request_id", id)` — `R-OBS-MTR-X1` (cardinality explosion).
   - `MeterRegistry meterRegistry = ...` без явного Prometheus registry в config — `R-OBS-MTR-X3`.
   - `management.endpoints.web.exposure.include: '*'` или `prometheus` без network policy — `R-OBS-MTR-X4` / `R-OBS-CFG-X3`.
   - `otel.traces.sampler.arg: 1.0` в `application-prod.yml` — `R-OBS-TRC-X1`.
   - `span.setAttribute("customer.email", ...)` или span с PII — `R-OBS-TRC-X2`.
   - `var span = tracer.spanBuilder(...).startSpan(); ... business logic ... span.end();` без try/finally — `R-OBS-TRC-X3`.
   - `@Async` без custom TaskDecorator с MDC propagation — `R-OBS-CTX-X3` / `R-OBS-TRC-X4`.
   - HealthIndicator делает `restTemplate.exchange(...)` каждый запрос (без TTL-кеша) — `R-OBS-HC-X3` / `R-RES-HC-X1`.
   - `if (orderCount > 1000) return Health.down()` — `R-OBS-HC-X1`.
   - liveness probe возвращает DOWN при недоступности БД — `R-OBS-HC-X2`.
   - `application-prod.yml` exposes `env`, `heapdump`, `threaddump`, `loggers` без security — `R-OBS-CFG-X1`.
   - Один port для business + actuator (`management.server.port` отсутствует) — `R-OBS-CFG-X2`.
   - `MDC.put("requestId", ...)` без `MDC.clear()` в `finally` — `R-OBS-CTX-X1` (security incident — leaked context).
   - `MDC.put` в Service / Handler / Controller (не в filter) — `R-OBS-CTX-X2`.
   - Alerts на каждый ERROR в логах без burn-rate — `R-OBS-SLO-X1`.

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

7. **Формат findings, локализация, серьёзность, резюме** — см. `.claude/docs/review-finding-format.md` (`RFF-*`).

8. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично:**
     - PII в логах / span-attributes / metrics (`R-OBS-LOG-X1`, `R-OBS-TRC-X2`) — security incident, GDPR/PII-compliance.
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
- PII detection in code (вне логов/spans) — `ucp-auth-review` (`AUTH-16`).
- Alerting rules в Prometheus/Grafana — это infra-уровень, не codified в этом скилле.
- Service Mesh observability (Istio sidecar metrics) — отдельная тема.

$ARGUMENTS
