---
name: ucp-node-observability-review
lang: node
description: Ревью наблюдаемости NestJS-сервиса (Node/TypeScript, коды R-OBS-*) — nestjs-pino JSON + AsyncLocalStorage, prom-client (RED/USE, низкая cardinality), OpenTelemetry JS, health live/ready terminus, management-порт, request-id, SLO.
when_to_use: Изменения в logging-конфиге, метриках, OTel-setup, interceptor/middleware, health-эндпоинтах, management-конфиге.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Observability (Node / NestJS + nestjs-pino + prom-client + OTel JS)

Ты ревьюишь наблюдаемость на соответствие **контракту** `backend/observability/spec.md` (`R-OBS-*`) и
**Node-реализации** `backend/observability/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/observability/spec.md`** + **`backend/observability/references/node/implementation.md`**.
- Парные: `backend/node/nest-bootstrap/...` (`NESTBOOT-*`), `resilience` (health внешних с TTL-кешем), `auth-patterns` (`auth-patterns/no-pii-in-logs-and-events` PII), `kafka` (контекст в BullMQ/KafkaJS).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`observability/no-pii-in-logs`, `observability/low-cardinality-labels`), не только префикс.

2. **Скоп.** Logging-конфиг (nestjs-pino / pino), метрики (prom-client + @willsoto/nestjs-prometheus), OTel-setup (`tracing.ts` / NodeSDK), interceptor/middleware (request-id / AsyncLocalStorage), health-эндпоинты (@nestjs/terminus), management-конфиг (второй порт); `git diff`.

3. **Прогон.**
   - **Logging (`R-OBS-LOG-*`):** pino JSON в проде, DI-логгер через `@InjectPinoLogger`, merge-объект вместо конкатенации, AsyncLocalStorage / nestjs-pino для `requestId`/`userId` в каждой записи. PII в логах → `observability/no-pii-in-logs` (критично); `pino redact` для authorization/password/email. `console.log`/`console.error` → `observability/no-direct-stdout-logging`. `JSON.stringify` в template-literal → `observability/parameterized-log-messages`. `logger.error(err.message)` без `{ err }` → `observability/parameterized-log-messages` (теряет stack). Полный request body для money/PII → `observability/no-pii-in-logs`. INFO в каждом handler на HTTP-запрос → `observability/log-levels-and-noise` (дублирует pino-http access-log).
   - **Metrics (`R-OBS-MTR-*`):** prom-client, `register.setDefaultLabels({ service, env, version })`, snake_case+единица. `route`-label — шаблон роута (`/orders/:id`), не сырой URL. High-cardinality label (`user_id`/сырой `req.url`) → `observability/low-cardinality-labels`. Нестандартные labels (`app` vs `service`) → `observability/standard-metric-dimensions`. Метрики мимо реестра → `observability/metrics-are-exported`. `/metrics` без сетевой защиты → `observability/management-endpoints-restricted`.
   - **Tracing (`R-OBS-TRC-*`):** `tracing.ts` с `NodeSDK` + `getNodeAutoInstrumentations()` **импортируется до** `NestFactory.create` (иначе модули не пропатчены). `traceparent` propagation (W3C) — авто. Manual span через `startActiveSpan`-callback-форму с `end()` в `finally` (без → `observability/manual-spans-are-closed`). Sampling 1–10%+errors в проде (100% → `observability/sampling-strategy`). PII в span-атрибутах → `observability/manual-spans-are-closed`. Разрыв trace при offload в `worker_threads`/BullMQ без явной передачи `traceparent` → `observability/context-propagated-to-async`.
   - **Health (`R-OBS-HC-*`):** `@nestjs/terminus`, раздельные `/health/live` (процесс / event-loop) и `/health/ready` (DB `TypeOrmHealthIndicator`, критичные зависимости). Бизнес-состояние в health → `observability/health-check-is-technical`. Liveness зависит от DB/Redis → `observability/liveness-and-readiness-split` (restart-loop). Health-probe бизнес-операцией → `observability/health-check-is-technical`.
   - **Config (`R-OBS-CFG-*`):** отдельный management-порт на :9090 только с `/metrics` и `/health/*` (один порт business+management → `observability/separate-management-port`). Debug-поверхности (Swagger `/docs`, env-dump) без auth в проде → `observability/management-endpoints-restricted`. Экспонировать всё подряд → `observability/management-endpoints-restricted`.
   - **Context (`R-OBS-CTX-*`):** `nestjs-pino` `genReqId` из `X-Request-Id`, `userId` в guard/interceptor через `logger.assign({ userId })`. Общий мутируемый контекст вместо per-request ALS-store → `observability/context-set-at-edge-and-cleared` (критично, `userId` соседнего запроса = compliance-инцидент). Обогащение контекста в service/handler вместо middleware/guard/interceptor → `observability/context-set-at-edge-and-cleared`. Потеря контекста при offload в worker/BullMQ без явной передачи `requestId`/`traceparent` → `observability/context-propagated-to-async`.
   - **SLO (`R-OBS-SLO-*`):** SLO + error budget + multi-window multi-burn-rate alerts + runbook. Alert на каждый ERROR → `observability/burn-rate-alerting`. SLO без error budget (100% target) → `observability/slo-with-error-budget`. Алерты без runbook → `observability/alerts-have-runbooks`.

4. **Cross-check:** PII-гигиена — `ucp-node-auth-review` (`auth-patterns/no-pii-in-logs-and-events`); health внешних систем (TTL-кеш) — `ucp-node-resilience-review`; wiring interceptor/management в bootstrap — `ucp-node-bootstrap-review`; контекст в BullMQ/KafkaJS — `ucp-node-kafka-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — PII в логах/спанах (`observability/no-pii-in-logs`/`observability/manual-spans-are-closed`), общий мутируемый ALS-контекст без per-request изоляции (`observability/context-set-at-edge-and-cleared`), high-cardinality labels (`observability/low-cardinality-labels`), liveness зависит от внешних (`observability/liveness-and-readiness-split`), debug-эндпоинты без auth в проде (`observability/management-endpoints-restricted`).
   - **Предупреждение** — `console.log`/потеря stack (`observability/no-direct-stdout-logging`/`observability/parameterized-log-messages`), sampling 100% в проде (`observability/sampling-strategy`), manual span без callback-формы/`finally` (`observability/manual-spans-are-closed`), один порт business+management (`observability/separate-management-port`), alert на каждый ERROR (`observability/burn-rate-alerting`).
   - **Замечание** — `JSON.stringify` в template-literal (`observability/parameterized-log-messages`), INFO в каждом handler (`observability/log-levels-and-noise`), нестандартные labels (`observability/standard-metric-dimensions`), нет runbook (`observability/alerts-have-runbooks`).

## Что не входит

- PII-классификация/политика маскирования — `ucp-node-auth-review`. Health внешних систем (TTL/probe) — `ucp-node-resilience-review`.
- Wiring interceptor/management-порта в bootstrap — `ucp-node-bootstrap-review`. Контекст в очередях — `ucp-node-kafka-review`.

$ARGUMENTS
