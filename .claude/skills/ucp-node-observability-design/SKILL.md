---
name: ucp-node-observability-design
lang: node
description: Спроектировать наблюдаемость NestJS-сервиса (Node) по UCP (коды R-OBS-*) — nestjs-pino JSON/DI, prom-client RED/USE, OTel-node автоинструментация + sampling, @nestjs/terminus live/ready, management-порт, AsyncLocalStorage, SLO + burn-rate alerts.
when_to_use: Триггеры — «настрой логи/метрики/трейсинг», «pino», «prometheus в NestJS». При настройке observability.
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Observability — проектирование (Node / nestjs-pino + prom-client + OTel)

Ты проектируешь наблюдаемость по **контракту** `backend/observability/observability-rules.md` (`R-OBS-*`) и
**Node-реализации** `backend/observability/node/observability-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `backend/node/nest-bootstrap/...` (`NESTBOOT-*` health/wiring), `backend/resilience/...` (health-check внешних, `R-RES-HC-*`), `backend/auth-patterns/...` (PII-гигиена `AUTH-16`).

2. **Logging** (`R-OBS-LOG-*`): `nestjs-pino` через DI (`@InjectPinoLogger`), не `new Logger()` и не `console`. JSON в проде / `pino-pretty` локально по `NODE_ENV`. Структурные поля — merge-объект первым аргументом (`{ orderId }`, не template-literal). `{ err }` для ошибок — pino-сериализатор выводит stack. `redact` для PII (`req.headers.authorization`, `*.password`, `*.email`). Нет `console.log`.

3. **Metrics** (`R-OBS-MTR-*`): `prom-client` через `@willsoto/nestjs-prometheus`; endpoint `/metrics`; `register.setDefaultLabels({ service, env, version })`; RED-histogram по шаблону роута (`/orders/:id`, не сырой URL); `collectDefaultMetrics()` — eventloop lag, heap, GC; бизнес-`Counter`/`Histogram`; snake_case+единица (`payment_processing_seconds`); **низкая cardinality** (не `user_id`/`order_id`).

4. **Tracing** (`R-OBS-TRC-*`): `NodeSDK` + `getNodeAutoInstrumentations()` в `tracing.ts`, **импортировать до** `NestFactory.create` (иначе модули не пропатчены); охватывает http/express/nestjs-core/pg/kafkajs/ioredis. Manual span через `startActiveSpan` (callback-форма, `end()` в `finally`). Span-атрибуты — бизнес-контекст без PII. Sampling 1–10% в проде + 100% errors (`OTEL_TRACES_SAMPLER=parentbased_traceidratio`); `trace_id`/`span_id` в логах через `@opentelemetry/instrumentation-pino`.

5. **Health** (`R-OBS-HC-*`): `@nestjs/terminus` — раздельные `/health/live` (только процесс / event-loop) и `/health/ready` (`TypeOrmHealthIndicator`/pg + критичные зависимости); custom `HealthIndicator` на критичные внешние системы с TTL-кешем; `/info`: git sha, build time, имя сервиса.

6. **Config/Context** (`R-OBS-CFG/CTX-*`): отдельный management-порт `:9090` (второй Nest-app) только для `/metrics` и `/health/*`; `genReqId: (req) => req.headers['x-request-id'] ?? randomUUID()` — request-scoped logger через AsyncLocalStorage; `userId` в контекст после JWT-валидации в guard/interceptor (`logger.assign({ userId })`); **AsyncLocalStorage нативно проходит через `await`/Promise** — рвётся только на `worker_threads` и BullMQ (передавать `requestId`/`traceparent` явно в payload).

7. **SLO** (`R-OBS-SLO-*`): SLO + error budget + multi-window burn-rate alerts + runbook. Самопроверка (§8) + предложи `ucp-node-observability-review`.

## Антипаттерны, которые НЕ генерировать

- PII в логах/спанах (`R-OBS-LOG-X1`/`R-OBS-TRC-X2`); `console.log`/`console.error` (`R-OBS-LOG-X2`); `logger.error(err.message)` без `{ err }` (`R-OBS-LOG-X4`); `JSON.stringify` в template-literal аргументе (`R-OBS-LOG-X3`).
- High-cardinality labels (`R-OBS-MTR-X1`); нестандартные labels (`R-OBS-MTR-X2`); `/metrics` без сетевой защиты (`R-OBS-MTR-X4`).
- `tracing.ts` импортирован после `NestFactory.create` (`R-OBS-TRC-X1` — модули не пропатчены); sampling 100% в проде (`R-OBS-TRC-X1`); manual span без `finally`/callback-формы — утечка span (`R-OBS-TRC-X3`); разрыв trace при offload в worker/BullMQ без передачи контекста (`R-OBS-TRC-X4`).
- Liveness зависит от DB/Redis (`R-OBS-HC-X2`) — restart-loop; бизнес-состояние в health (`R-OBS-HC-X1`); health-probe бизнес-операцией (`R-OBS-HC-X3`).
- Один порт business + management (`R-OBS-CFG-X2`); общий мутируемый контекст вместо per-request ALS-store (`R-OBS-CTX-X1`) — `userId` соседнего запроса в логах = compliance-инцидент; обогащение контекста вне middleware/guard/interceptor (`R-OBS-CTX-X2`); потеря контекста при offload без явной передачи (`R-OBS-CTX-X3`).
- Alert на каждый ERROR (`R-OBS-SLO-X1`); SLO без error budget (`R-OBS-SLO-X2`); алерты без runbook (`R-OBS-SLO-X3`).

После работы скилла — обязательно `ucp-node-observability-review`.

$ARGUMENTS
