---
name: ucp-node-observability-design
lang: node
description: Спроектировать наблюдаемость NestJS-сервиса (Node) по UCP — nestjs-pino JSON/DI, prom-client RED/USE, OTel-node автоинструментация + sampling, @nestjs/terminus live/ready, management-порт, AsyncLocalStorage, SLO + burn-rate alerts.
when_to_use: Триггеры — «настрой логи/метрики/трейсинг», «pino», «prometheus в NestJS». При настройке observability.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Observability — проектирование (Node / nestjs-pino + prom-client + OTel)

Ты проектируешь наблюдаемость по **контракту** `backend/observability/spec.md` (`R-OBS-*`) и
**Node-реализации** `backend/observability/references/node/implementation.md`.

## Инструкции

1. **Прочитай** требования `node-style/*`. Коды в обосновании, не в коде. Связанные: `backend/node/nest-bootstrap/...` (`NESTBOOT-*` health/wiring), `backend/resilience/...` (health-check внешних, `R-RES-HC-*`), `backend/auth-patterns/...` (PII-гигиена `auth-patterns/no-pii-in-logs-and-events`).

2. **Logging** (`R-OBS-LOG-*`): `nestjs-pino` через DI (`@InjectPinoLogger`), не `new Logger()` и не `console`. JSON в проде / `pino-pretty` локально по `NODE_ENV`. Структурные поля — merge-объект первым аргументом (`{ orderId }`, не template-literal). `{ err }` для ошибок — pino-сериализатор выводит stack. `redact` для PII (`req.headers.authorization`, `*.password`, `*.email`). Нет `console.log`.

3. **Metrics** (`R-OBS-MTR-*`): `prom-client` через `@willsoto/nestjs-prometheus`; endpoint `/metrics`; `register.setDefaultLabels({ service, env, version })`; RED-histogram по шаблону роута (`/orders/:id`, не сырой URL); `collectDefaultMetrics()` — eventloop lag, heap, GC; бизнес-`Counter`/`Histogram`; snake_case+единица (`payment_processing_seconds`); **низкая cardinality** (не `user_id`/`order_id`).

4. **Tracing** (`R-OBS-TRC-*`): `NodeSDK` + `getNodeAutoInstrumentations()` в `tracing.ts`, **импортировать до** `NestFactory.create` (иначе модули не пропатчены); охватывает http/express/nestjs-core/pg/kafkajs/ioredis. Manual span через `startActiveSpan` (callback-форма, `end()` в `finally`). Span-атрибуты — бизнес-контекст без PII. Sampling 1–10% в проде + 100% errors (`OTEL_TRACES_SAMPLER=parentbased_traceidratio`); `trace_id`/`span_id` в логах через `@opentelemetry/instrumentation-pino`.

5. **Health** (`R-OBS-HC-*`): `@nestjs/terminus` — раздельные `/health/live` (только процесс / event-loop) и `/health/ready` (`TypeOrmHealthIndicator`/pg + критичные зависимости); custom `HealthIndicator` на критичные внешние системы с TTL-кешем; `/info`: git sha, build time, имя сервиса.

6. **Config/Context** (`R-OBS-CFG/CTX-*`): отдельный management-порт `:9090` (второй Nest-app) только для `/metrics` и `/health/*`; `genReqId: (req) => req.headers['x-request-id'] ?? randomUUID()` — request-scoped logger через AsyncLocalStorage; `userId` в контекст после JWT-валидации в guard/interceptor (`logger.assign({ userId })`); **AsyncLocalStorage нативно проходит через `await`/Promise** — рвётся только на `worker_threads` и BullMQ (передавать `requestId`/`traceparent` явно в payload).

7. **SLO** (`R-OBS-SLO-*`): SLO + error budget + multi-window burn-rate alerts + runbook. Самопроверка (§8) + предложи `ucp-node-observability-review`.

## Антипаттерны, которые НЕ генерировать

- PII в логах/спанах (`observability/no-pii-in-logs`/`observability/manual-spans-are-closed`); `console.log`/`console.error` (`observability/no-direct-stdout-logging`); `logger.error(err.message)` без `{ err }` (`observability/parameterized-log-messages`); `JSON.stringify` в template-literal аргументе (`observability/parameterized-log-messages`).
- High-cardinality labels (`observability/low-cardinality-labels`); нестандартные labels (`observability/standard-metric-dimensions`); `/metrics` без сетевой защиты (`observability/management-endpoints-restricted`).
- `tracing.ts` импортирован после `NestFactory.create` (`observability/sampling-strategy` — модули не пропатчены); sampling 100% в проде (`observability/sampling-strategy`); manual span без `finally`/callback-формы — утечка span (`observability/manual-spans-are-closed`); разрыв trace при offload в worker/BullMQ без передачи контекста (`observability/context-propagated-to-async`).
- Liveness зависит от DB/Redis (`observability/liveness-and-readiness-split`) — restart-loop; бизнес-состояние в health (`observability/health-check-is-technical`); health-probe бизнес-операцией (`observability/health-check-is-technical`).
- Один порт business + management (`observability/separate-management-port`); общий мутируемый контекст вместо per-request ALS-store (`observability/context-set-at-edge-and-cleared`) — `userId` соседнего запроса в логах = compliance-инцидент; обогащение контекста вне middleware/guard/interceptor (`observability/context-set-at-edge-and-cleared`); потеря контекста при offload без явной передачи (`observability/context-propagated-to-async`).
- Alert на каждый ERROR (`observability/burn-rate-alerting`); SLO без error budget (`observability/slo-with-error-budget`); алерты без runbook (`observability/alerts-have-runbooks`).

После работы скилла — обязательно `ucp-node-observability-review`.

$ARGUMENTS
