# Observability — реализация на Python (structlog / prometheus-client / OpenTelemetry)

Реализация язык-нейтрального контракта `../spec.md` (`R-OBS-*`) на Python. Коды общие с Java;
инструментарий: **structlog** (логи), **prometheus-client** (метрики), **OpenTelemetry Python SDK** (трейсы),
**contextvars** вместо MDC. Часть пересекается с `python-bootstrap` (`python-bootstrap/observability-configured-in-factory`).

## 1. Logging (`R-OBS-LOG-*`)

`observability/structured-logs-in-production` — **structlog** с JSON-renderer в проде, человекочитаемый — локально. `observability/logger-declared-uniformly` — логгер через
`structlog.get_logger(__name__)`, не `print`. `observability/parameterized-log-messages` — структурные поля как kwargs
(`log.info("order_created", order_id=order.id)`), не f-string-конкатенация. `observability/log-levels-and-noise` — уровни (DEBUG/INFO/WARN/
ERROR) по семантике. `observability/request-context-in-every-record` — `trace_id`/`span_id` (через OTel-интеграцию), `request_id`, `user_id` — в каждой
записи через bound contextvars (`structlog.contextvars.bind_contextvars`). `observability/log-levels-and-noise` — логи на границах (вход/
выход адаптеров, ошибки).

`observability/no-pii-in-logs` — **PII в логах** (email/phone/ФИО/токены) — критично, маскировать/не логировать (`auth-patterns/no-pii-in-logs-and-events`).
`observability/no-direct-stdout-logging` — `print()`/`traceback.print_exc()` (мимо pipeline, теряют контекст). `observability/parameterized-log-messages` — тяжёлая
сериализация в аргументе лога без ленивости (вычисляй лениво / передавай объект, не строку). `observability/parameterized-log-messages` —
`log.error(...)` без `exc_info=True`/`log.exception(...)` для исключения (теряется stack). `observability/no-pii-in-logs` — полный
request body для money/PII (только идентификаторы). `observability/log-levels-and-noise` — INFO на каждый HTTP-запрос (access-log отдельно).

```python
import logging
import sys
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

# R-OBS-LOG-1: structlog + JSON-renderer, ECS-совместимые поля. Формат идентичен эталонному сервису.
def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,         # R-OBS-LOG-5: trace_id/method/path из contextvars
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,                # → поле "logger"
            structlog.stdlib.add_log_level,                  # → поле "level"
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),     # → поле "timestamp" (ISO-8601)
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),             # прод: парсится Loki/ELK/Datadog
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)    # access-log глушим (R-OBS-LOG-X6)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

log = structlog.get_logger(__name__)                         # R-OBS-LOG-2: не print

# R-OBS-LOG-3: событие = первый позиционный аргумент (snake_case), поля как kwargs (только id, не PII):
log.info("order_created", order_id=str(order.id), customer_id=str(order.customer_id))

# R-OBS-LOG-X4: исключение через .exception (stack в pipeline), не log.error(str(e)):
try:
    await charge(order)
except PaymentPortError:
    log.exception("order_charge_failed", order_id=str(order.id))    # exc_info=True неявно

# Request-логирование + trace_id (события request_started / request_completed / request_failed):
class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(              # R-OBS-LOG-5
            trace_id=trace_id, method=request.method, path=request.url.path)
        start = time.perf_counter()
        log.info("request_started")
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_failed")
            raise
        log.info("request_completed", status_code=response.status_code,
                 duration_ms=round((time.perf_counter() - start) * 1000, 2))
        response.headers["X-Trace-Id"] = trace_id
        return response

# R-OBS-LOG-X1/X5 анти-пример (НЕ так): PII и полный body в логах
# log.info("order_created", email=user.email, body=request_payload)   # email/PII + payload запрещены
```

## 2. Metrics (`R-OBS-MTR-*`)

`observability/metrics-are-exported` — `prometheus-client` (или `prometheus-fastapi-instrumentator`); endpoint `/metrics` для scraping.
`observability/standard-metric-dimensions` — стандартные labels `service`/`env`/`version`. `observability/red-and-use-metrics` — RED для HTTP (rate/errors/duration —
instrumentator авто). `observability/red-and-use-metrics` — USE для ресурсов. `observability/red-and-use-metrics` — бизнес-метрики через `Counter`/`Histogram`/
`Gauge`. `observability/metric-naming` — имена snake_case с единицей (`payment_duration_seconds`). `observability/low-cardinality-labels` — **низкая
cardinality** labels (`status_class`/`endpoint`/`payment_method`), не `user_id`/`order_id`.

`observability/low-cardinality-labels` — high-cardinality labels (`user_id`/`request_id` как value) — взрыв time series/OOM. `observability/standard-metric-dimensions` —
нестандартизованные labels (`app` vs `service_name`). `observability/metrics-are-exported` — метрики без экспортируемого registry (теряются).
`observability/management-endpoints-restricted` — `/metrics` без сетевой защиты в публичной сети.

Setup как в эталонном сервисе: авто-RED HTTP через `prometheus-fastapi-instrumentator` + USE-gauges через `psutil`
(паритет с Java: instrumentator ≈ Spring Actuator `http_server_requests`, system-gauges ≈ `jvm_memory`/`hikaricp`):

```python
import asyncio
import contextlib

import psutil
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# R-OBS-MTR-1/3: registry + /metrics + авто-RED для HTTP (rate/errors/duration) — без ручного кода на каждый маршрут.
def setup_metrics(app: FastAPI) -> None:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# R-OBS-MTR-2: prometheus-client НЕ имеет глобальных tags (в отличие от Micrometer `management.metrics.tags`),
# поэтому service/env/version выносим в info-метрику (или в target-labels Prometheus-scrape), не дублируя в каждой:
APP_INFO = Gauge("app_info", "Build/runtime info", labelnames=("service", "env", "version"))
APP_INFO.labels(service="order-service", env=settings.env, version=settings.build_version).set(1)

# R-OBS-MTR-4: USE для ресурсов (аналог jvm_memory/hikaricp в Java) — gauges + фоновый сбор psutil:
CPU_USAGE = Gauge("system_cpu_usage_percent", "CPU usage percentage")
MEMORY_USAGE = Gauge("system_memory_usage_bytes", "Memory usage in bytes")
OPEN_FDS = Gauge("system_open_file_descriptors", "Open file descriptors")

async def collect_system_metrics(interval: float = 15.0) -> None:
    proc = psutil.Process()
    while True:
        CPU_USAGE.set(proc.cpu_percent(interval=None))
        MEMORY_USAGE.set(proc.memory_info().rss)
        with contextlib.suppress(AttributeError):          # num_fds() недоступен на Windows
            OPEN_FDS.set(proc.num_fds())
        await asyncio.sleep(interval)
# Запуск/останов — в lifespan: task = asyncio.create_task(collect_system_metrics()); ... task.cancel() (R-SHUT-SCHED-1)
```

```python
from prometheus_client import Counter, Histogram

# R-OBS-MTR-5/6: custom-метрики; имена snake_case с единицей. Объявляются один раз на модуль (не в хендлере).
# R-OBS-MTR-7: labels — только низкая cardinality (payment_method/status_class), НЕ order_id/user_id (R-OBS-MTR-X1).
ORDER_CREATED_TOTAL = Counter(
    "order_created_total",                                  # _total для Counter (соглашение Prometheus)
    "Total orders created",
    labelnames=("payment_method",),                        # CARD/SBP/CRYPTO — десятки значений, не миллионы
)
PAYMENT_DURATION_SECONDS = Histogram(
    "payment_duration_seconds",                            # R-OBS-MTR-6: единица (_seconds) в имени
    "Payment processing duration",
    labelnames=("status_class",),                          # success/client_error/server_error
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Стандартные labels service/env/version (R-OBS-MTR-2) задаются глобально на registry, не дублируются в метрике.
async def confirm(order: Order) -> None:
    with PAYMENT_DURATION_SECONDS.labels(status_class="success").time():   # context-manager: авто-замер
        await self._payment_port.charge(order)
    ORDER_CREATED_TOTAL.labels(payment_method=order.payment_method.value).inc()
```

## 3. Tracing (`R-OBS-TRC-*`)

`observability/tracing-auto-instrumented` — OTel автоинструментация (`opentelemetry-instrumentation-fastapi`/`-sqlalchemy`/`-httpx`/`-aiokafka`).
`observability/tracing-auto-instrumented` — `traceparent` propagation (W3C, `rest-api/trace-context-header`) — авто через инструментацию. `observability/manual-spans-are-closed` — manual span
через **context manager** `with tracer.start_as_current_span("confirm_order"):` (авто-закрытие). `observability/manual-spans-are-closed` —
span-атрибуты — бизнес-контекст, не PII. `observability/sampling-strategy` — sampling 1–10% в проде, 100% на ошибки (tail-based если
collector умеет). `observability/logs-linked-to-traces` — `trace_id` в логах (OTel ↔ structlog processor).

`observability/sampling-strategy` — sampling 100% в проде на нагруженном сервисе (переполнение хранилища). `observability/manual-spans-are-closed` — PII в
span-атрибутах. `observability/manual-spans-are-closed` — manual span без context-manager/`try-finally` (утечка span). `observability/context-propagated-to-async` —
разрыв контекста при `run_in_executor` без `contextvars.copy_context()` (см. `observability/context-propagated-to-async`).

```python
import contextvars
import asyncio
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

# R-OBS-TRC-3: manual span ТОЛЬКО через context-manager — авто-end даже при исключении (R-OBS-TRC-X3).
async def handle(cmd: ConfirmOrderCommand) -> None:
    with tracer.start_as_current_span("confirm_order") as span:
        span.set_attribute("order.id", str(cmd.order_id))   # R-OBS-TRC-4: бизнес-контекст, внутренний id
        span.set_attribute("payment.method", cmd.payment_method.value)
        # span.set_attribute("customer.email", ...)         # R-OBS-TRC-X2: PII в span запрещено
        await self._dispatcher.dispatch(cmd)
    # span закрыт context-manager'ом — ручной span.end() не нужен

# R-OBS-TRC-X4/R-OBS-CTX-3: contextvars нативно проходят через await, но offload в thread их теряет.
# Для run_in_executor — переносим контекст явно через copy_context(), иначе trace_id/span разорвутся.
def _cpu_bound(report: bytes) -> bytes:
    return render_pdf(report)                               # синхронная CPU-задача

async def build_report(report: bytes) -> bytes:
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()                        # снимок trace/log-контекста
    return await loop.run_in_executor(None, lambda: ctx.run(_cpu_bound, report))
```

OTel ↔ structlog (`observability/logs-linked-to-traces`/`observability/logs-linked-to-traces`) — `trace_id`/`span_id` подставляются автоматически, не руками:

```python
from opentelemetry import trace

def add_otel_context(_, __, event_dict: dict) -> dict:      # structlog-processor (после merge_contextvars)
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:                                        # R-OBS-TRC-6: связка лог-запись → distributed trace
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

## 4. Health checks (`R-OBS-HC-*`)

`observability/liveness-and-readiness-split` — раздельные `/health/live` и `/health/ready` (cross-ref `python-bootstrap/liveness-and-readiness-split`). `observability/health-indicator-per-system` — custom-check на
критичные внешние системы с TTL-кешем (`resilience/cached-health-probe-per-system`). `observability/health-indicator-per-system` — `/info` (версия, build).

`observability/health-check-is-technical` — бизнес-состояние в health (`if order_count > N: DOWN`). `observability/liveness-and-readiness-split` — liveness зависит от внешних
(DB/Redis) → restart-loop; только readiness. `observability/health-check-is-technical` — health-probe бизнес-операцией (`resilience/cached-health-probe-per-system`).

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])

# R-OBS-HC-1: liveness — процесс жив; НЕ зависит от внешних систем (R-OBS-HC-X2), иначе restart-loop.
@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "UP"}

# R-OBS-HC-2: readiness — готов принимать трафик; проверяет критичные зависимости с TTL-кешем (R-RES-HC-2).
# 503 при неготовности → k8s убирает pod из endpoints. Проверка — light SELECT 1, не бизнес-операция (R-OBS-HC-X3).
@router.get("/ready")
async def ready(probe: ReadinessProbe = Depends(get_readiness_probe)) -> JSONResponse:
    if not probe.is_ready():                                # readiness снят на shutdown — см. graceful-shutdown
        return JSONResponse({"status": "DOWN"}, status_code=503)
    db_ok = await probe.check_db()                          # SELECT 1 с TTL-кешем, не if order_count > N (R-OBS-HC-X1)
    status_code = 200 if db_ok else 503
    return JSONResponse({"status": "UP" if db_ok else "DOWN"}, status_code=status_code)
```

## 5. Конфигурация (`R-OBS-CFG-*`)

`observability/separate-management-port` — отдельный management-порт/приложение для `/metrics` и `/health` (отделить от business-трафика;
в FastAPI — sub-app или отдельный ASGI на своём порту). `observability/separate-management-port` — explicit список endpoints, не всё подряд.
`observability/metrics-are-exported` — дефолты метрик (гистограммы латентности). `observability/structured-logs-in-production` — конфиг логов: JSON в проде, текст локально
(по `APP_ENV`).

`observability/management-endpoints-restricted` — debug-эндпоинты (env/heapdump-аналоги, `/docs` с секретами) без auth в проде. `observability/separate-management-port` —
один порт для business + management. `observability/management-endpoints-restricted` — экспонировать всё подряд в проде.

```python
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from pydantic_settings import BaseSettings, SettingsConfigDict

class ObservabilitySettings(BaseSettings):                  # pydantic-settings, не os.getenv
    env: str = "dev"                                        # R-OBS-CFG-4: JSON в проде, текст локально — по env
    management_port: int = 8081                             # R-OBS-CFG-1: отдельный порт от business (8080)
    model_config = SettingsConfigDict(env_prefix="APP_")

# R-OBS-CFG-1/X2: /metrics и /health — на отдельном management-ASGI (свой порт), не на business-app.
def build_management_app(probe: ReadinessProbe) -> FastAPI:
    mgmt = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)   # R-OBS-CFG-X1: docs закрыты в management
    mgmt.mount("/metrics", make_asgi_app())                 # prometheus ASGI; не на публичном порту (R-OBS-MTR-X4)
    mgmt.include_router(health_router)                       # /health/live + /health/ready
    return mgmt
# Business-app (server.port=8080) НЕ монтирует /metrics — иначе один порт на всё (R-OBS-CFG-X2).
```

## 6. Context propagation (`R-OBS-CTX-*`)

`observability/context-set-at-edge-and-cleared` — **request-id middleware**: на каждый входящий запрос — `bind_contextvars(request_id=...)`.
`observability/logs-linked-to-traces` — `trace_id`/`span_id` — автоматически через OTel-structlog processor, не руками. `observability/context-propagated-to-async` —
**contextvars нативно проходят через `await`** в asyncio (в отличие от Java thread-pool — `TaskDecorator` не нужен);
для `run_in_executor`/thread — `contextvars.copy_context()`. `observability/context-set-at-edge-and-cleared` — `user_id` в contextvars после
JWT-валидации (в auth-зависимости/middleware).

`observability/context-set-at-edge-and-cleared` — bound contextvars без очистки между запросами (`clear_contextvars` в middleware `finally` / per-request
binding) — утечка `user_id` соседнему запросу = compliance-инцидент. `observability/context-set-at-edge-and-cleared` — `bind_contextvars` в произвольных
местах (handler/service) — только в middleware. `observability/context-propagated-to-async` — потеря контекста при offload в thread без
`copy_context()`.

```python
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware

# R-OBS-CTX-1: bind_contextvars на входящий запрос ТОЛЬКО в middleware (R-OBS-CTX-X2), не в handler/service.
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)   # попадёт в каждую log-запись
        try:
            return await call_next(request)
        finally:
            # R-OBS-CTX-X1: обязательная очистка — иначе user_id протечёт соседнему запросу = compliance-инцидент.
            structlog.contextvars.clear_contextvars()
        # trace_id/span_id (R-OBS-CTX-2) НЕ биндим руками — добавляет OTel-processor (см. add_otel_context выше).

# R-OBS-CTX-4: user_id биндится после JWT-валидации в auth-зависимости/middleware, не в бизнес-коде.
async def bind_user(claims: TokenClaims = Depends(verify_jwt)) -> None:
    structlog.contextvars.bind_contextvars(user_id=claims.sub)          # внутренний id, не email/ФИО (R-OBS-LOG-X1)
```

## 7. SLO и алерты (`R-OBS-SLO-*`)

`observability/slo-with-error-budget` — у critical-эндпоинта есть SLO (latency/availability). `observability/burn-rate-alerting` — multi-window multi-burn-rate
alerts. `observability/burn-rate-alerting` — alert на исчерпание error budget (<10%). `observability/burn-rate-alerting` — alerts отдельны от SLO-определения.

`observability/burn-rate-alerting` — alert на каждый ERROR (alert fatigue) — агрегировать. `observability/slo-with-error-budget` — SLO без error budget (100%
target). `observability/alerts-have-runbooks` — алерты без runbook.

## 8. Чеклист подключения к новому сервису (Python)

1. structlog JSON в проде, нет `print`, kwargs-поля, нет PII, `exc_info` для ошибок.
2. prometheus-client, стандартные labels, низкая cardinality, snake_case+единица.
3. OTel автоинструментация + manual span через context-manager, sampling, нет PII в атрибутах.
4. Раздельные live/ready health; нет бизнес-состояния и внешних в liveness.
5. Отдельный management-порт, explicit endpoints, debug закрыт в проде.
6. request_id/user_id через contextvars в middleware с очисткой; copy_context для thread-offload.
7. SLO + error budget + multi-window alerts + runbook.
