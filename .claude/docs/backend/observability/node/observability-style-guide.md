# Observability — Node Style Guide (nestjs-pino / prom-client / OpenTelemetry JS)

Реализация язык-нейтрального контракта `../observability-rules.md` (`R-OBS-*`) на Node-стеке (NestJS + TypeScript).
Коды общие с Java/Python; инструментарий: **pino** через `nestjs-pino` (логи), **prom-client** (метрики),
**OpenTelemetry JS** (`@opentelemetry/auto-instrumentations-node`, трейсы), **@nestjs/terminus** (health),
**AsyncLocalStorage** вместо MDC. Часть пересекается с `nest-bootstrap` (`NESTBOOT-*`).

## 1. Logging (`R-OBS-LOG-*`)

`R-OBS-LOG-1` — **pino JSON в проде** (stdout как есть), локально — `pino-pretty` transport по `NODE_ENV`.
`R-OBS-LOG-2` — логгер через DI: `@InjectPinoLogger(OrderService.name)` / `PinoLogger`, не `new Logger()` и не
`console`. `R-OBS-LOG-3` — структурные поля merge-объектом первым аргументом, не конкатенация:

```ts
// PREFER
this.logger.info({ orderId: order.id, customerId: order.customerId }, 'order created');
// AVOID
this.logger.info(`Order created: ${JSON.stringify(order)}`);   // сериализация всегда + неструктурно
```

`R-OBS-LOG-4` — уровни по семантике (error — actionable + stack, warn — деградация/retry/CB, info — бизнес-события,
debug — не в проде). `R-OBS-LOG-5` — `trace_id`/`span_id` (авто через OTel), `requestId`, `userId` — в каждой записи
через request-scoped logger `nestjs-pino` (AsyncLocalStorage, см. §6). `R-OBS-LOG-6` — логи на границах (in/out
адаптеров, publish событий, start/end batch).

`R-OBS-LOG-X1` — **PII в логах** (email/phone/ФИО/токены) — критично; маскировать или не логировать (`AUTH-16`);
pino `redact: ['req.headers.authorization', '*.password', '*.email']`. `R-OBS-LOG-X2` — `console.log`/`console.error`
(мимо pipeline, без контекста). `R-OBS-LOG-X3` — тяжёлая сериализация в аргументе лога (`JSON.stringify` в
template-literal выполняется всегда) — передавай объект, pino сериализует сам. `R-OBS-LOG-X4` — потеря stack:
`logger.error(err.message)`; нужен `logger.error({ err }, 'failed')` — pino-сериализатор выводит stack. `R-OBS-LOG-X5` —
полный request body для money/PII (только идентификаторы). `R-OBS-LOG-X6` — INFO в каждом handler'е на HTTP-запрос —
access-log делает `pino-http` (`autoLogging`), отдельно.

## 2. Metrics (`R-OBS-MTR-*`)

`R-OBS-MTR-1` — `prom-client` (обвязка `@willsoto/nestjs-prometheus`); endpoint `/metrics` для scraping.
`R-OBS-MTR-2` — стандартные labels через `register.setDefaultLabels({ service, env, version })`, не в каждой метрике.
`R-OBS-MTR-3` — RED для HTTP: interceptor/middleware с `Histogram` `http_server_requests_seconds{method,route,status_class}`;
label `route` — **шаблон роута** (`/orders/:id`), не сырой URL. `R-OBS-MTR-4` — USE: `collectDefaultMetrics()` —
`nodejs_eventloop_lag_seconds`, heap, GC; плюс saturation пулов (pg `pool.totalCount/waitingCount` как `Gauge`).
`R-OBS-MTR-5` — бизнес-метрики `Counter`/`Histogram`/`Gauge`:

```ts
export const orderCreatedTotal = new Counter({ name: 'order_created_total', help: 'Orders created', labelNames: ['type'] as const });
export const paymentDuration = new Histogram({ name: 'payment_processing_seconds', help: 'Payment latency', buckets: [0.1, 0.5, 1, 5] });
```

`R-OBS-MTR-6` — имена snake_case с единицей (`payment_duration_seconds`). `R-OBS-MTR-7` — низкая cardinality labels
(`status_class`/`route`/`payment_method`), не `user_id`/`order_id`.

`R-OBS-MTR-X1` — high-cardinality labels (`user_id`, сырой `req.url` с ID) — взрыв time series/OOM. `R-OBS-MTR-X2` —
нестандартизованные labels (`app` vs `service_name`) — только `service`/`env`/`version` через default labels.
`R-OBS-MTR-X3` — метрики мимо экспортируемого registry (теряются). `R-OBS-MTR-X4` — `/metrics` без сетевой защиты
в публичной сети.

## 3. Tracing (`R-OBS-TRC-*`)

`R-OBS-TRC-1` — OTel автоинструментация: `NodeSDK` + `getNodeAutoInstrumentations()` (http/express/nestjs-core/pg/
kafkajs/ioredis) в `tracing.ts`, **импортируется до** `NestFactory.create` (или `node --require ./tracing.js`) —
иначе модули не пропатчены. `R-OBS-TRC-2` — `traceparent` propagation (W3C, `R-HDR-4`) — авто
(`W3CTraceContextPropagator` дефолт). `R-OBS-TRC-3` — manual span через `startActiveSpan` (callback-форма закрывает
контекст сама, `end()` — в `finally`):

```ts
return this.tracer.startActiveSpan('confirmOrder', async (span) => {
  try { span.setAttribute('order.id', cmd.orderId); return await this.handle(cmd); }
  finally { span.end(); }
});
```

`R-OBS-TRC-4` — span-атрибуты — бизнес-контекст (внутренние ID, статусы), не PII. `R-OBS-TRC-5` — sampling 1–10% в
проде, 100% на ошибки: `OTEL_TRACES_SAMPLER=parentbased_traceidratio`, `OTEL_TRACES_SAMPLER_ARG=0.1` (tail-based —
на collector'е). `R-OBS-TRC-6` — `trace_id`/`span_id` в логах — `@opentelemetry/instrumentation-pino` (или pino
`mixin` из `trace.getActiveSpan()`), не руками.

`R-OBS-TRC-X1` — sampling 100% в проде на нагруженном сервисе. `R-OBS-TRC-X2` — PII в span-атрибутах. `R-OBS-TRC-X3` —
manual span без `finally`/callback-формы (утечка span). `R-OBS-TRC-X4` — разрыв trace при offload в worker/очередь
без явной передачи контекста (см. `R-OBS-CTX-3`).

## 4. Health checks (`R-OBS-HC-*`)

`R-OBS-HC-1` — `@nestjs/terminus`, раздельные `/health/live` (только процесс — пустой check или event-loop) и
`/health/ready` (БД ping `TypeOrmHealthIndicator`/pg, критичные зависимости). `R-OBS-HC-2` — custom `HealthIndicator`
на критичные внешние системы с TTL-кешем результата (`R-RES-HC-2`). `R-OBS-HC-3` — `/info`: версия (git sha из env),
build time, имя сервиса.

`R-OBS-HC-X1` — бизнес-состояние в health (`if (orderCount > N) → DOWN`). `R-OBS-HC-X2` — liveness зависит от внешних
(DB/Redis) → restart-loop; внешние — только в readiness. `R-OBS-HC-X3` — health-probe бизнес-операцией (`R-RES-HC-X2`).

## 5. Конфигурация (`R-OBS-CFG-*`)

`R-OBS-CFG-1` — отдельный management-порт: второй `http.Server`/Nest-приложение на :9090 только с `/metrics` и
`/health/*` — business-трафик не мешается со scraping, порт закрывается network policy. `R-OBS-CFG-2` — explicit
список endpoints (health, info, metrics), не всё подряд. `R-OBS-CFG-3` — дефолты метрик: histogram buckets латентности
HTTP, `collectDefaultMetrics`. `R-OBS-CFG-4` — конфиг логов по `NODE_ENV`: JSON в проде, `pino-pretty` локально.

`R-OBS-CFG-X1` — debug-поверхности (Swagger `/docs`, `/metrics`, env-dump) без auth/сетевой защиты в проде.
`R-OBS-CFG-X2` — один порт для business + management. `R-OBS-CFG-X3` — экспонировать всё подряд в проде.

## 6. Context propagation (`R-OBS-CTX-*`)

`R-OBS-CTX-1` — **request-id**: `nestjs-pino` `genReqId: (req) => req.headers['x-request-id'] ?? randomUUID()` —
каждый запрос получает request-scoped logger через AsyncLocalStorage. `R-OBS-CTX-2` — `trace_id`/`span_id` —
автоматически через OTel-pino интеграцию, не руками. `R-OBS-CTX-3` — **AsyncLocalStorage нативно проходит через
`await`/Promise/таймеры** (аналог contextvars; TaskDecorator не нужен); рвётся на `worker_threads` и внешних
очередях (BullMQ) — передавать `requestId`/`traceparent` явно в payload джобы и восстанавливать в processor'е.
`R-OBS-CTX-4` — `userId` в контекст после JWT-валидации (в guard/interceptor): `logger.assign({ userId })` /
`cls.set('userId', ...)` при `nestjs-cls`.

`R-OBS-CTX-X1` — общий мутируемый контекст вместо per-request ALS-store (`cls.run` / nestjs-pino) — `userId` соседнего
запроса в логах = compliance-инцидент. `R-OBS-CTX-X2` — обогащение контекста в произвольных местах (handler/service) —
только middleware/guard/interceptor. `R-OBS-CTX-X3` — потеря контекста при offload в worker/очередь без явной передачи.

## 7. SLO и алерты (`R-OBS-SLO-*`)

`R-OBS-SLO-1` — у critical-эндпоинта есть SLO (latency/availability). `R-OBS-SLO-2` — multi-window multi-burn-rate
alerts. `R-OBS-SLO-3` — alert на исчерпание error budget (<10%). `R-OBS-SLO-4` — alerts отдельны от SLO-определения
(инфраструктурные — event loop lag, heap, pool saturation; доменные — `order_failed_total`).

`R-OBS-SLO-X1` — alert на каждый ERROR (alert fatigue) — агрегировать. `R-OBS-SLO-X2` — SLO без error budget (100%
target). `R-OBS-SLO-X3` — алерты без runbook.

## 8. Чеклист подключения к новому сервису (Node/NestJS)

1. nestjs-pino: JSON в проде / pretty локально, DI-логгер, merge-объект вместо конкатенации, `{ err }` для ошибок, `redact` для PII.
2. prom-client + default labels `service`/`env`/`version`, RED-histogram по шаблону роута, `collectDefaultMetrics`, snake_case+единица, низкая cardinality.
3. `tracing.ts` с NodeSDK + auto-instrumentations **до** bootstrap; manual span через `startActiveSpan`; sampling 1–10%; нет PII в атрибутах.
4. terminus: раздельные `/health/live` и `/health/ready`; внешние системы только в readiness, с TTL-кешем.
5. Отдельный management-порт для `/metrics` + `/health`; Swagger и debug закрыты в проде.
6. `genReqId` из `X-Request-Id`, `userId` в guard/interceptor; явная передача контекста в worker/очереди.
7. SLO + error budget + multi-window alerts + runbook.
