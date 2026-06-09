# Observability — Python Style Guide (structlog / prometheus-client / OpenTelemetry)

Реализация язык-нейтрального контракта `../observability-rules.md` (`R-OBS-*`) на Python. Коды общие с Java;
инструментарий: **structlog** (логи), **prometheus-client** (метрики), **OpenTelemetry Python SDK** (трейсы),
**contextvars** вместо MDC. Часть пересекается с `python-bootstrap` (`PYBOOT-14`).

## 1. Logging (`R-OBS-LOG-*`)

`R-OBS-LOG-1` — **structlog** с JSON-renderer в проде, человекочитаемый — локально. `R-OBS-LOG-2` — логгер через
`structlog.get_logger(__name__)`, не `print`. `R-OBS-LOG-3` — структурные поля как kwargs
(`log.info("order_created", order_id=order.id)`), не f-string-конкатенация. `R-OBS-LOG-4` — уровни (DEBUG/INFO/WARN/
ERROR) по семантике. `R-OBS-LOG-5` — `trace_id`/`span_id` (через OTel-интеграцию), `request_id`, `user_id` — в каждой
записи через bound contextvars (`structlog.contextvars.bind_contextvars`). `R-OBS-LOG-6` — логи на границах (вход/
выход адаптеров, ошибки).

`R-OBS-LOG-X1` — **PII в логах** (email/phone/ФИО/токены) — критично, маскировать/не логировать (`AUTH-16`).
`R-OBS-LOG-X2` — `print()`/`traceback.print_exc()` (мимо pipeline, теряют контекст). `R-OBS-LOG-X3` — тяжёлая
сериализация в аргументе лога без ленивости (вычисляй лениво / передавай объект, не строку). `R-OBS-LOG-X4` —
`log.error(...)` без `exc_info=True`/`log.exception(...)` для исключения (теряется stack). `R-OBS-LOG-X5` — полный
request body для money/PII (только идентификаторы). `R-OBS-LOG-X6` — INFO на каждый HTTP-запрос (access-log отдельно).

## 2. Metrics (`R-OBS-MTR-*`)

`R-OBS-MTR-1` — `prometheus-client` (или `prometheus-fastapi-instrumentator`); endpoint `/metrics` для scraping.
`R-OBS-MTR-2` — стандартные labels `service`/`env`/`version`. `R-OBS-MTR-3` — RED для HTTP (rate/errors/duration —
instrumentator авто). `R-OBS-MTR-4` — USE для ресурсов. `R-OBS-MTR-5` — бизнес-метрики через `Counter`/`Histogram`/
`Gauge`. `R-OBS-MTR-6` — имена snake_case с единицей (`payment_duration_seconds`). `R-OBS-MTR-7` — **низкая
cardinality** labels (`status_class`/`endpoint`/`payment_method`), не `user_id`/`order_id`.

`R-OBS-MTR-X1` — high-cardinality labels (`user_id`/`request_id` как value) — взрыв time series/OOM. `R-OBS-MTR-X2` —
нестандартизованные labels (`app` vs `service_name`). `R-OBS-MTR-X3` — метрики без экспортируемого registry (теряются).
`R-OBS-MTR-X4` — `/metrics` без сетевой защиты в публичной сети.

## 3. Tracing (`R-OBS-TRC-*`)

`R-OBS-TRC-1` — OTel автоинструментация (`opentelemetry-instrumentation-fastapi`/`-sqlalchemy`/`-httpx`/`-aiokafka`).
`R-OBS-TRC-2` — `traceparent` propagation (W3C, `R-HDR-4`) — авто через инструментацию. `R-OBS-TRC-3` — manual span
через **context manager** `with tracer.start_as_current_span("confirm_order"):` (авто-закрытие). `R-OBS-TRC-4` —
span-атрибуты — бизнес-контекст, не PII. `R-OBS-TRC-5` — sampling 1–10% в проде, 100% на ошибки (tail-based если
collector умеет). `R-OBS-TRC-6` — `trace_id` в логах (OTel ↔ structlog processor).

`R-OBS-TRC-X1` — sampling 100% в проде на нагруженном сервисе (переполнение хранилища). `R-OBS-TRC-X2` — PII в
span-атрибутах. `R-OBS-TRC-X3` — manual span без context-manager/`try-finally` (утечка span). `R-OBS-TRC-X4` —
разрыв контекста при `run_in_executor` без `contextvars.copy_context()` (см. `R-OBS-CTX-3`).

## 4. Health checks (`R-OBS-HC-*`)

`R-OBS-HC-1` — раздельные `/health/live` и `/health/ready` (cross-ref `PYBOOT-13`). `R-OBS-HC-2` — custom-check на
критичные внешние системы с TTL-кешем (`R-RES-HC-2`). `R-OBS-HC-3` — `/info` (версия, build).

`R-OBS-HC-X1` — бизнес-состояние в health (`if order_count > N: DOWN`). `R-OBS-HC-X2` — liveness зависит от внешних
(DB/Redis) → restart-loop; только readiness. `R-OBS-HC-X3` — health-probe бизнес-операцией (`R-RES-HC-X2`).

## 5. Конфигурация (`R-OBS-CFG-*`)

`R-OBS-CFG-1` — отдельный management-порт/приложение для `/metrics` и `/health` (отделить от business-трафика;
в FastAPI — sub-app или отдельный ASGI на своём порту). `R-OBS-CFG-2` — explicit список endpoints, не всё подряд.
`R-OBS-CFG-3` — дефолты метрик (гистограммы латентности). `R-OBS-CFG-4` — конфиг логов: JSON в проде, текст локально
(по `APP_ENV`).

`R-OBS-CFG-X1` — debug-эндпоинты (env/heapdump-аналоги, `/docs` с секретами) без auth в проде. `R-OBS-CFG-X2` —
один порт для business + management. `R-OBS-CFG-X3` — экспонировать всё подряд в проде.

## 6. Context propagation (`R-OBS-CTX-*`)

`R-OBS-CTX-1` — **request-id middleware**: на каждый входящий запрос — `bind_contextvars(request_id=...)`.
`R-OBS-CTX-2` — `trace_id`/`span_id` — автоматически через OTel-structlog processor, не руками. `R-OBS-CTX-3` —
**contextvars нативно проходят через `await`** в asyncio (в отличие от Java thread-pool — `TaskDecorator` не нужен);
для `run_in_executor`/thread — `contextvars.copy_context()`. `R-OBS-CTX-4` — `user_id` в contextvars после
JWT-валидации (в auth-зависимости/middleware).

`R-OBS-CTX-X1` — bound contextvars без очистки между запросами (`clear_contextvars` в middleware `finally` / per-request
binding) — утечка `user_id` соседнему запросу = compliance-инцидент. `R-OBS-CTX-X2` — `bind_contextvars` в произвольных
местах (handler/service) — только в middleware. `R-OBS-CTX-X3` — потеря контекста при offload в thread без
`copy_context()`.

## 7. SLO и алерты (`R-OBS-SLO-*`)

`R-OBS-SLO-1` — у critical-эндпоинта есть SLO (latency/availability). `R-OBS-SLO-2` — multi-window multi-burn-rate
alerts. `R-OBS-SLO-3` — alert на исчерпание error budget (<10%). `R-OBS-SLO-4` — alerts отдельны от SLO-определения.

`R-OBS-SLO-X1` — alert на каждый ERROR (alert fatigue) — агрегировать. `R-OBS-SLO-X2` — SLO без error budget (100%
target). `R-OBS-SLO-X3` — алерты без runbook.

## 8. Чеклист подключения к новому сервису (Python)

1. structlog JSON в проде, нет `print`, kwargs-поля, нет PII, `exc_info` для ошибок.
2. prometheus-client, стандартные labels, низкая cardinality, snake_case+единица.
3. OTel автоинструментация + manual span через context-manager, sampling, нет PII в атрибутах.
4. Раздельные live/ready health; нет бизнес-состояния и внешних в liveness.
5. Отдельный management-порт, explicit endpoints, debug закрыт в проде.
6. request_id/user_id через contextvars в middleware с очисткой; copy_context для thread-offload.
7. SLO + error budget + multi-window alerts + runbook.
