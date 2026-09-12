# Observability — реализация на Node (nestjs-pino / prom-client / OpenTelemetry JS)

Реализация язык-нейтрального контракта `../spec.md` (`R-OBS-*`) на Node-стеке (NestJS + TypeScript).
Коды общие с Java/Python; инструментарий: **pino** через `nestjs-pino` (логи), **prom-client** (метрики),
**OpenTelemetry JS** (`@opentelemetry/auto-instrumentations-node`, трейсы), **@nestjs/terminus** (health),
**AsyncLocalStorage** вместо MDC. Часть пересекается с `nest-bootstrap` (`NESTBOOT-*`).

## 1. Logging (`R-OBS-LOG-*`)

`observability/structured-logs-in-production` — **pino JSON в проде** (stdout как есть), локально — `pino-pretty` transport по `NODE_ENV`.
`observability/logger-declared-uniformly` — логгер через DI: `@InjectPinoLogger(OrderService.name)` / `PinoLogger`, не `new Logger()` и не
`console`. `observability/parameterized-log-messages` — структурные поля merge-объектом первым аргументом, не конкатенация:

```ts
// PREFER
this.logger.info({ orderId: order.id, customerId: order.customerId }, 'order created');
// AVOID
this.logger.info(`Order created: ${JSON.stringify(order)}`);   // сериализация всегда + неструктурно
```

`observability/log-levels-and-noise` — уровни по семантике (error — actionable + stack, warn — деградация/retry/CB, info — бизнес-события,
debug — не в проде). `observability/request-context-in-every-record` — `trace_id`/`span_id` (авто через OTel), `requestId`, `userId` — в каждой записи
через request-scoped logger `nestjs-pino` (AsyncLocalStorage, см. §6). `observability/log-levels-and-noise` — логи на границах (in/out
адаптеров, publish событий, start/end batch).

`observability/no-pii-in-logs` — **PII в логах** (email/phone/ФИО/токены) — критично; маскировать или не логировать (`auth-patterns/no-pii-in-logs-and-events`);
pino `redact: ['req.headers.authorization', '*.password', '*.email']`. `observability/no-direct-stdout-logging` — `console.log`/`console.error`
(мимо pipeline, без контекста). `observability/parameterized-log-messages` — тяжёлая сериализация в аргументе лога (`JSON.stringify` в
template-literal выполняется всегда) — передавай объект, pino сериализует сам. `observability/parameterized-log-messages` — потеря stack:
`logger.error(err.message)`; нужен `logger.error({ err }, 'failed')` — pino-сериализатор выводит stack. `observability/no-pii-in-logs` —
полный request body для money/PII (только идентификаторы). `observability/log-levels-and-noise` — INFO в каждом handler'е на HTTP-запрос —
access-log делает `pino-http` (`autoLogging`), отдельно.

## 2. Metrics (`R-OBS-MTR-*`)

`observability/metrics-are-exported` — `prom-client` (обвязка `@willsoto/nestjs-prometheus`); endpoint `/metrics` для scraping.
`observability/standard-metric-dimensions` — стандартные labels через `register.setDefaultLabels({ service, env, version })`, не в каждой метрике.
`observability/red-and-use-metrics` — RED для HTTP: interceptor/middleware с `Histogram` `http_server_requests_seconds{method,route,status_class}`;
label `route` — **шаблон роута** (`/orders/:id`), не сырой URL. `observability/red-and-use-metrics` — USE: `collectDefaultMetrics()` —
`nodejs_eventloop_lag_seconds`, heap, GC; плюс saturation пулов (pg `pool.totalCount/waitingCount` как `Gauge`).
`observability/red-and-use-metrics` — бизнес-метрики `Counter`/`Histogram`/`Gauge`:

```ts
export const orderCreatedTotal = new Counter({ name: 'order_created_total', help: 'Orders created', labelNames: ['type'] as const });
export const paymentDuration = new Histogram({ name: 'payment_processing_seconds', help: 'Payment latency', buckets: [0.1, 0.5, 1, 5] });
```

`observability/metric-naming` — имена snake_case с единицей (`payment_duration_seconds`). `observability/low-cardinality-labels` — низкая cardinality labels
(`status_class`/`route`/`payment_method`), не `user_id`/`order_id`.

`observability/low-cardinality-labels` — high-cardinality labels (`user_id`, сырой `req.url` с ID) — взрыв time series/OOM. `observability/standard-metric-dimensions` —
нестандартизованные labels (`app` vs `service_name`) — только `service`/`env`/`version` через default labels.
`observability/metrics-are-exported` — метрики мимо экспортируемого registry (теряются). `observability/management-endpoints-restricted` — `/metrics` без сетевой защиты
в публичной сети.

## 3. Tracing (`R-OBS-TRC-*`)

`observability/tracing-auto-instrumented` — OTel автоинструментация: `NodeSDK` + `getNodeAutoInstrumentations()` (http/express/nestjs-core/pg/
kafkajs/ioredis) в `tracing.ts`, **импортируется до** `NestFactory.create` (или `node --require ./tracing.js`) —
иначе модули не пропатчены. `observability/tracing-auto-instrumented` — `traceparent` propagation (W3C, `rest-api/trace-context-header`) — авто
(`W3CTraceContextPropagator` дефолт). `observability/manual-spans-are-closed` — manual span через `startActiveSpan` (callback-форма закрывает
контекст сама, `end()` — в `finally`):

```ts
return this.tracer.startActiveSpan('confirmOrder', async (span) => {
  try { span.setAttribute('order.id', cmd.orderId); return await this.handle(cmd); }
  finally { span.end(); }
});
```

`observability/manual-spans-are-closed` — span-атрибуты — бизнес-контекст (внутренние ID, статусы), не PII. `observability/sampling-strategy` — sampling 1–10% в
проде, 100% на ошибки: `OTEL_TRACES_SAMPLER=parentbased_traceidratio`, `OTEL_TRACES_SAMPLER_ARG=0.1` (tail-based —
на collector'е). `observability/logs-linked-to-traces` — `trace_id`/`span_id` в логах — `@opentelemetry/instrumentation-pino` (или pino
`mixin` из `trace.getActiveSpan()`), не руками.

`observability/sampling-strategy` — sampling 100% в проде на нагруженном сервисе. `observability/manual-spans-are-closed` — PII в span-атрибутах. `observability/manual-spans-are-closed` —
manual span без `finally`/callback-формы (утечка span). `observability/context-propagated-to-async` — разрыв trace при offload в worker/очередь
без явной передачи контекста (см. `observability/context-propagated-to-async`).

## 4. Health checks (`R-OBS-HC-*`)

`observability/liveness-and-readiness-split` — `@nestjs/terminus`, раздельные `/health/live` (только процесс — пустой check или event-loop) и
`/health/ready` (БД ping `TypeOrmHealthIndicator`/pg, критичные зависимости). `observability/health-indicator-per-system` — custom `HealthIndicator`
на критичные внешние системы с TTL-кешем результата (`resilience/cached-health-probe-per-system`). `observability/health-indicator-per-system` — `/info`: версия (git sha из env),
build time, имя сервиса.

`observability/health-check-is-technical` — бизнес-состояние в health (`if (orderCount > N) → DOWN`). `observability/liveness-and-readiness-split` — liveness зависит от внешних
(DB/Redis) → restart-loop; внешние — только в readiness. `observability/health-check-is-technical` — health-probe бизнес-операцией (`resilience/cached-health-probe-per-system`).

## 5. Конфигурация (`R-OBS-CFG-*`)

`observability/separate-management-port` — отдельный management-порт: второй `http.Server`/Nest-приложение на :9090 только с `/metrics` и
`/health/*` — business-трафик не мешается со scraping, порт закрывается network policy. `observability/separate-management-port` — explicit
список endpoints (health, info, metrics), не всё подряд. `observability/metrics-are-exported` — дефолты метрик: histogram buckets латентности
HTTP, `collectDefaultMetrics`. `observability/structured-logs-in-production` — конфиг логов по `NODE_ENV`: JSON в проде, `pino-pretty` локально.

`observability/management-endpoints-restricted` — debug-поверхности (Swagger `/docs`, `/metrics`, env-dump) без auth/сетевой защиты в проде.
`observability/separate-management-port` — один порт для business + management. `observability/management-endpoints-restricted` — экспонировать всё подряд в проде.

## 6. Context propagation (`R-OBS-CTX-*`)

`observability/context-set-at-edge-and-cleared` — **request-id**: `nestjs-pino` `genReqId: (req) => req.headers['x-request-id'] ?? randomUUID()` —
каждый запрос получает request-scoped logger через AsyncLocalStorage. `observability/logs-linked-to-traces` — `trace_id`/`span_id` —
автоматически через OTel-pino интеграцию, не руками. `observability/context-propagated-to-async` — **AsyncLocalStorage нативно проходит через
`await`/Promise/таймеры** (аналог contextvars; TaskDecorator не нужен); рвётся на `worker_threads` и внешних
очередях (BullMQ) — передавать `requestId`/`traceparent` явно в payload джобы и восстанавливать в processor'е.
`observability/context-set-at-edge-and-cleared` — `userId` в контекст после JWT-валидации (в guard/interceptor): `logger.assign({ userId })` /
`cls.set('userId', ...)` при `nestjs-cls`.

`observability/context-set-at-edge-and-cleared` — общий мутируемый контекст вместо per-request ALS-store (`cls.run` / nestjs-pino) — `userId` соседнего
запроса в логах = compliance-инцидент. `observability/context-set-at-edge-and-cleared` — обогащение контекста в произвольных местах (handler/service) —
только middleware/guard/interceptor. `observability/context-propagated-to-async` — потеря контекста при offload в worker/очередь без явной передачи.

## 7. SLO и алерты (`R-OBS-SLO-*`)

`observability/slo-with-error-budget` — у critical-эндпоинта есть SLO (latency/availability). `observability/burn-rate-alerting` — multi-window multi-burn-rate
alerts. `observability/burn-rate-alerting` — alert на исчерпание error budget (<10%). `observability/burn-rate-alerting` — alerts отдельны от SLO-определения
(инфраструктурные — event loop lag, heap, pool saturation; доменные — `order_failed_total`).

`observability/burn-rate-alerting` — alert на каждый ERROR (alert fatigue) — агрегировать. `observability/slo-with-error-budget` — SLO без error budget (100%
target). `observability/alerts-have-runbooks` — алерты без runbook.

## 8. Чеклист подключения к новому сервису (Node/NestJS)

1. nestjs-pino: JSON в проде / pretty локально, DI-логгер, merge-объект вместо конкатенации, `{ err }` для ошибок, `redact` для PII.
2. prom-client + default labels `service`/`env`/`version`, RED-histogram по шаблону роута, `collectDefaultMetrics`, snake_case+единица, низкая cardinality.
3. `tracing.ts` с NodeSDK + auto-instrumentations **до** bootstrap; manual span через `startActiveSpan`; sampling 1–10%; нет PII в атрибутах.
4. terminus: раздельные `/health/live` и `/health/ready`; внешние системы только в readiness, с TTL-кешем.
5. Отдельный management-порт для `/metrics` + `/health`; Swagger и debug закрыты в проде.
6. `genReqId` из `X-Request-Id`, `userId` в guard/interceptor; явная передача контекста в worker/очереди.
7. SLO + error budget + multi-window alerts + runbook.
