---
name: ucp-node-observability-review
lang: node
description: Ревью наблюдаемости NestJS-сервиса (Node/TypeScript, коды R-OBS-*) — nestjs-pino JSON + AsyncLocalStorage, prom-client (RED/USE, низкая cardinality), OpenTelemetry JS, health live/ready terminus, management-порт, request-id, SLO.
when_to_use: Изменения в logging-конфиге, метриках, OTel-setup, interceptor/middleware, health-эндпоинтах, management-конфиге.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Observability (Node / NestJS + nestjs-pino + prom-client + OTel JS)

Ты ревьюишь наблюдаемость на соответствие **контракту** `backend/observability/observability-rules.md` (`R-OBS-*`) и
**Node-реализации** `backend/observability/node/observability-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/observability/observability-rules.md`** + **`backend/observability/node/observability-style-guide.md`**.
- Парные: `backend/node/nest-bootstrap/...` (`NESTBOOT-*`), `resilience` (health внешних с TTL-кешем), `auth-patterns` (`AUTH-16` PII), `kafka` (контекст в BullMQ/KafkaJS).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-OBS-LOG-X1`, `R-OBS-MTR-X1`), не только префикс.

2. **Скоп.** Logging-конфиг (nestjs-pino / pino), метрики (prom-client + @willsoto/nestjs-prometheus), OTel-setup (`tracing.ts` / NodeSDK), interceptor/middleware (request-id / AsyncLocalStorage), health-эндпоинты (@nestjs/terminus), management-конфиг (второй порт); `git diff`.

3. **Прогон.**
   - **Logging (`R-OBS-LOG-*`):** pino JSON в проде, DI-логгер через `@InjectPinoLogger`, merge-объект вместо конкатенации, AsyncLocalStorage / nestjs-pino для `requestId`/`userId` в каждой записи. PII в логах → `R-OBS-LOG-X1` (критично); `pino redact` для authorization/password/email. `console.log`/`console.error` → `R-OBS-LOG-X2`. `JSON.stringify` в template-literal → `R-OBS-LOG-X3`. `logger.error(err.message)` без `{ err }` → `R-OBS-LOG-X4` (теряет stack). Полный request body для money/PII → `R-OBS-LOG-X5`. INFO в каждом handler на HTTP-запрос → `R-OBS-LOG-X6` (дублирует pino-http access-log).
   - **Metrics (`R-OBS-MTR-*`):** prom-client, `register.setDefaultLabels({ service, env, version })`, snake_case+единица. `route`-label — шаблон роута (`/orders/:id`), не сырой URL. High-cardinality label (`user_id`/сырой `req.url`) → `R-OBS-MTR-X1`. Нестандартные labels (`app` vs `service`) → `R-OBS-MTR-X2`. Метрики мимо реестра → `R-OBS-MTR-X3`. `/metrics` без сетевой защиты → `R-OBS-MTR-X4`.
   - **Tracing (`R-OBS-TRC-*`):** `tracing.ts` с `NodeSDK` + `getNodeAutoInstrumentations()` **импортируется до** `NestFactory.create` (иначе модули не пропатчены). `traceparent` propagation (W3C) — авто. Manual span через `startActiveSpan`-callback-форму с `end()` в `finally` (без → `R-OBS-TRC-X3`). Sampling 1–10%+errors в проде (100% → `R-OBS-TRC-X1`). PII в span-атрибутах → `R-OBS-TRC-X2`. Разрыв trace при offload в `worker_threads`/BullMQ без явной передачи `traceparent` → `R-OBS-TRC-X4`.
   - **Health (`R-OBS-HC-*`):** `@nestjs/terminus`, раздельные `/health/live` (процесс / event-loop) и `/health/ready` (DB `TypeOrmHealthIndicator`, критичные зависимости). Бизнес-состояние в health → `R-OBS-HC-X1`. Liveness зависит от DB/Redis → `R-OBS-HC-X2` (restart-loop). Health-probe бизнес-операцией → `R-OBS-HC-X3`.
   - **Config (`R-OBS-CFG-*`):** отдельный management-порт на :9090 только с `/metrics` и `/health/*` (один порт business+management → `R-OBS-CFG-X2`). Debug-поверхности (Swagger `/docs`, env-dump) без auth в проде → `R-OBS-CFG-X1`. Экспонировать всё подряд → `R-OBS-CFG-X3`.
   - **Context (`R-OBS-CTX-*`):** `nestjs-pino` `genReqId` из `X-Request-Id`, `userId` в guard/interceptor через `logger.assign({ userId })`. Общий мутируемый контекст вместо per-request ALS-store → `R-OBS-CTX-X1` (критично, `userId` соседнего запроса = compliance-инцидент). Обогащение контекста в service/handler вместо middleware/guard/interceptor → `R-OBS-CTX-X2`. Потеря контекста при offload в worker/BullMQ без явной передачи `requestId`/`traceparent` → `R-OBS-CTX-X3`.
   - **SLO (`R-OBS-SLO-*`):** SLO + error budget + multi-window multi-burn-rate alerts + runbook. Alert на каждый ERROR → `R-OBS-SLO-X1`. SLO без error budget (100% target) → `R-OBS-SLO-X2`. Алерты без runbook → `R-OBS-SLO-X3`.

4. **Cross-check:** PII-гигиена — `ucp-node-auth-review` (`AUTH-16`); health внешних систем (TTL-кеш) — `ucp-node-resilience-review`; wiring interceptor/management в bootstrap — `ucp-node-bootstrap-review`; контекст в BullMQ/KafkaJS — `ucp-node-kafka-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — PII в логах/спанах (`R-OBS-LOG-X1`/`R-OBS-TRC-X2`), общий мутируемый ALS-контекст без per-request изоляции (`R-OBS-CTX-X1`), high-cardinality labels (`R-OBS-MTR-X1`), liveness зависит от внешних (`R-OBS-HC-X2`), debug-эндпоинты без auth в проде (`R-OBS-CFG-X1`).
   - **Предупреждение** — `console.log`/потеря stack (`R-OBS-LOG-X2`/`R-OBS-LOG-X4`), sampling 100% в проде (`R-OBS-TRC-X1`), manual span без callback-формы/`finally` (`R-OBS-TRC-X3`), один порт business+management (`R-OBS-CFG-X2`), alert на каждый ERROR (`R-OBS-SLO-X1`).
   - **Замечание** — `JSON.stringify` в template-literal (`R-OBS-LOG-X3`), INFO в каждом handler (`R-OBS-LOG-X6`), нестандартные labels (`R-OBS-MTR-X2`), нет runbook (`R-OBS-SLO-X3`).

## Что не входит

- PII-классификация/политика маскирования — `ucp-node-auth-review`. Health внешних систем (TTL/probe) — `ucp-node-resilience-review`.
- Wiring interceptor/management-порта в bootstrap — `ucp-node-bootstrap-review`. Контекст в очередях — `ucp-node-kafka-review`.

$ARGUMENTS
