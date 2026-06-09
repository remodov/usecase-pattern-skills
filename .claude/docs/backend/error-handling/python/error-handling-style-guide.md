# Error Handling — Python Style Guide (FastAPI / SQLAlchemy / Pydantic)

Реализация язык-нейтрального контракта `../error-handling-rules.md` (`R-ERR-*`) на Python-стеке.
Коды правил — общие с Java; здесь — как они выглядят в FastAPI-сервисе. Структура слоёв UCP:
`core/` (домен, без фреймворка), `adapters/out/*` (httpx-клиенты), edge (FastAPI app + exception-handlers).

Базовый принцип (`R-ERR-1`): **исключение — часть контракта**. `except Exception: return None` — главный
антипаттерн всего гайда.

---

## 1. Иерархия исключений — `R-ERR-HIER-*`

`R-ERR-HIER-1` / `R-ERR-HIER-2` — 4 базовых типа, все наследуют один корневой `AppError`, не «голый» `Exception`:

```python
# core/errors.py
class AppError(Exception):
    """Корень всех прикладных ошибок."""


class DomainError(AppError):
    """Нарушено бизнес-правило → 409/422, no-retry."""


class InputValidationError(AppError):
    """Невалидный вход → 400, no-retry. Не путать с pydantic.ValidationError."""


class IntegrationError(AppError):
    """Внешняя система ответила неожиданно → 502/503/504, retry-safe."""


class TechnicalError(AppError):
    """Наша внутренняя проблема → 500, retry-возможно."""
```

`DomainError` живёт в `core/`, `IntegrationError`-наследники — в каждом `adapters/out/<system>/`,
`InputValidationError` — на edge. В Python нет checked-exceptions, поэтому `R-ERR-HIER-2` про «не терять тип»
выполняется тем, что edge-handler матчит **конкретные** классы, а не `Exception`.

`R-ERR-HIER-3` — имя по бизнес-смыслу, не по техформату:

```python
# PREFER
class OrderAlreadyShippedError(DomainError): ...
class InsufficientFundsError(DomainError): ...
# AVOID
class BusinessError(DomainError): ...        # без контекста
```

`R-ERR-HIER-4` — `IntegrationError`-наследники с префиксом системы:

```python
# adapters/out/payment/errors.py
class PaymentGatewayError(IntegrationError): ...
class PaymentGatewayUnavailableError(PaymentGatewayError): ...   # CB открыт
```

`R-ERR-HIER-5` — конструктор фиксирует контекст обязательно. Идиоматично — `@dataclass`-исключение:

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class InsufficientFundsError(DomainError):
    customer_id: str
    requested: Decimal
    available: Decimal

    def __str__(self) -> str:
        return (f"Insufficient funds: customer={self.customer_id}, "
                f"requested={self.requested}, available={self.available}")
```

`R-ERR-HIER-X1` ❌ `raise Exception("что-то сломалось")` / `raise RuntimeError(...)` — тип теряется, edge-handler не отличит от технической. Кидать конкретный наследник.

`R-ERR-HIER-X2` ❌ `assert` / `raise AssertionError` / `ValueError` как бизнес-правило в доменном коде. Бизнес-правило → `DomainError`; нарушение инварианта агрегата → ловит unit-тест, не endpoint.

---

## 2. Где throw, где catch — `R-ERR-WHERE-*`

`R-ERR-WHERE-1` — `raise` где нужно: domain handler → `DomainError`, валидатор → `InputValidationError`, out-adapter → `IntegrationError`. Не накручивать `returns.Result` везде (см. §6).

`R-ERR-WHERE-2` — три места catch:

**a) Edge — FastAPI exception-handlers** (один модуль `app/error_handlers.py`, per-type):

```python
# app/error_handlers.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain)
    app.add_exception_handler(InputValidationError, _handle_validation)
    app.add_exception_handler(IntegrationError, _handle_integration)
    app.add_exception_handler(Exception, _handle_unexpected)   # catch-all
```

**b) Integration boundary — httpx-адаптер** ловит низкоуровневое, кидает port-specific:

```python
# adapters/out/payment/client.py
import httpx

class PaymentClientAdapter(PaymentPort):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def register(self, cmd: RegisterCommand) -> RegisterResult:
        try:
            resp = await self._client.post("/register", json=_to_api(cmd))
            resp.raise_for_status()
            return _to_domain(resp.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:                    # 4xx → domain, R-ERR-RETRY-2
                raise InvalidPaymentRequestError(cmd.order_id, e.response.text) from e
            raise PaymentGatewayError("payment 5xx on register") from e
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise PaymentGatewayError("payment timeout/transport") from e
```

**c) Резильянс-обёртка** — декоратор (tenacity / circuit breaker), формальный catch (см. §5).

`R-ERR-WHERE-3` — в UseCase Handler / Domain Service / Aggregate **ноль try/except**.

`R-ERR-WHERE-X1` ❌ `try: ... except Exception as e: logger.error("failed", exc_info=e)` в handler/service — глушит, теряет тип, возвращает «успех». Главный силент-фейл.

`R-ERR-WHERE-X2` ❌ `except Exception as e: raise RuntimeError(e)` — теряется тип, edge отдаёт 500 на всё; оборачивать в типизированный наследник (`raise PaymentGatewayError(...) from e`).

`R-ERR-WHERE-X3` ❌ `except Exception: return None` / `return []` — скрывает проблему ещё глубже, чем X1.

---

## 3. Mapping в ProblemDetails — `R-ERR-MAP-*`

RFC 9457 в FastAPI — вручную через `JSONResponse` с `media_type="application/problem+json"` (FastAPI не даёт встроенного ProblemDetail). Хелпер:

```python
# app/problem.py
from fastapi.responses import JSONResponse

def problem(status: int, title: str, detail: str, *, type_: str = "about:blank",
            trace_id: str | None = None, **ext) -> JSONResponse:
    body = {"type": type_, "title": title, "status": status, "detail": detail}
    if trace_id:
        body["traceId"] = trace_id
    body.update(ext)
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")
```

`R-ERR-MAP-1` — `DomainError` → 409 (нарушение состояния) / 422 (нарушение инвариантов):

```python
async def _handle_domain(request: Request, exc: InsufficientFundsError) -> JSONResponse:
    logger.warning("domain rule violated: %s", exc)                      # R-ERR-LOG-1
    app_errors_total.labels(type="domain", exception=type(exc).__name__).inc()
    return problem(
        status=422,
        title="Operation cannot be completed",
        detail="insufficient funds",
        type_="https://api.example.com/errors/insufficient-funds",
        trace_id=get_trace_id(),
        customerId=exc.customer_id, requested=str(exc.requested), available=str(exc.available),
    )
```

`R-ERR-MAP-2` — `InputValidationError` → 400 c `errors`-массивом. Ошибки **pydantic** (`RequestValidationError`) приводить к этой же форме отдельным handler-ом:

```python
from fastapi.exceptions import RequestValidationError

async def _handle_pydantic(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return problem(400, "Validation failed", "request body is invalid",
                   trace_id=get_trace_id(), errors=errors)
```

`R-ERR-MAP-3` — `IntegrationError` → 502 (внешка 5xx с телом) / 503 (CB открыт / bulkhead reject) / 504 (timeout). Сырое тело внешки в `detail` **не вкладывать** (PII) — фраза + `traceId`.

`R-ERR-MAP-4` — `TechnicalError` → 500, минимум в response, детали в логи (`AUTH-18`).

`R-ERR-MAP-5` — catch-all (`Exception`) → 500, ERROR-лог + полный stacktrace + контекст; сигнал бага:

```python
async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unexpected error", exc_info=exc)                       # R-ERR-LOG-3
    app_errors_total.labels(type="unexpected", exception=type(exc).__name__).inc()
    return problem(500, "Internal Server Error", "internal error", trace_id=get_trace_id())
```

`R-ERR-MAP-X1` ❌ HTTP 200 при ошибке с `{"success": false}` в body.
`R-ERR-MAP-X2` ❌ stacktrace в `detail` — утечка путей/версий; только в логи.
`R-ERR-MAP-X3` ❌ `str(exc)` низкоуровневой ошибки как `detail` без санитизации (`relation "orders" does not exist`) — раскрытие схемы БД.

---

## 4. Логирование исключений — `R-ERR-LOG-*`

Логгер — `structlog` (JSON в проде), MDC через `contextvars` (`R-OBS-*`).

`R-ERR-LOG-1` — `DomainError` → `WARNING` в edge-handler (ожидаемо, не баг).
`R-ERR-LOG-2` — `IntegrationError` → `WARNING` если CB закрыт, `ERROR` если CB открылся.
`R-ERR-LOG-3` — `TechnicalError` и catch-all → `ERROR` + stacktrace (`exc_info=exc` или `logger.exception(...)`) + контекст.
`R-ERR-LOG-4` — логируем один раз — на edge-handler.

`R-ERR-LOG-X1` ❌ `logger.error(...); raise` — двойное логирование. Либо логируй и обработай, либо проброс.
`R-ERR-LOG-X2` ❌ `logger.error(str(e))` без `exc_info` — теряется stacktrace. Используй `logger.exception("context: %s", ctx)` (внутри except) или `logger.error("...", exc_info=e)`.

---

## 5. Retry / no-retry семантика — `R-ERR-RETRY-*`

Retry — `tenacity`; circuit breaker — `aiobreaker` / `purgatory`. На out-adapter-методах, не в домене.

`R-ERR-RETRY-1` — по типу: `DomainError`/`InputValidationError` — никогда; `IntegrationError` — retry-safe при идемпотентности (`AUTH-19`); `TechnicalError` — обычно retry после latency.

```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

@retry(retry=retry_if_exception_type(PaymentGatewayError),   # только 5xx/timeout, R-ERR-RETRY-3
       stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, max=2),
       reraise=True)
async def register_with_retry(self, cmd: RegisterCommand) -> RegisterResult:
    return await self._adapter.register(cmd)   # InvalidPaymentRequestError (4xx) НЕ ретраится
```

`R-ERR-RETRY-2` — HTTP 4xx от внешней системы — не retry; → port-specific (`InvalidPaymentRequestError`), edge отдаёт 422.
`R-ERR-RETRY-3` — 5xx и timeout — retry-safe только при идемпотентности; без `Idempotency-Key` на write — `R-RES-RE-X1`.

`R-ERR-RETRY-X1` ❌ `@retry` на edge-handler-функции — он вне retry-цикла.

---

## 6. Result-types vs exceptions — `R-ERR-RESULT-*`

`R-ERR-RESULT-1` — `returns.Result` / `Either` допустим точечно в чисто-функциональных модулях (парсер, calc engine).
`R-ERR-RESULT-2` — в цепочке UseCase Handler → Domain → Adapter — исключения, не Result.
`R-ERR-RESULT-X1` ❌ глобальная замена исключений на Result — без match-выражения вырождается в `if not res.ok: raise res.error`.

---

## 7. Observability — `R-ERR-OBS-*`

`R-ERR-OBS-1` — метрика `app_errors_total` через `prometheus_client`:

```python
from prometheus_client import Counter
app_errors_total = Counter("app_errors_total", "Application errors", ["type", "exception"])
```

`R-ERR-OBS-2` — span на исключение помечается `ERROR` (OpenTelemetry):

```python
span.set_status(Status(StatusCode.ERROR))
span.record_exception(exc)
```

`R-ERR-OBS-3` — алёрты на необычные паттерны (рост `unexpected` → баг; `integration` → деградация внешки; `domain` для одного кода → изменилось бизнес-условие; `validation` рост → клиент сломал контракт).

`R-ERR-OBS-X1` ❌ алёрт «любое исключение в логах» — `DomainError` нормально частая; алёртить только на `unexpected`/`technical`.

---

## Чеклист подключения к новому сервису (Python/FastAPI)

- [ ] 4 базовых исключения в `core/errors.py` от общего `AppError`
- [ ] Доменные наследники с контекстом (`@dataclass`-исключения), имена по бизнес-смыслу
- [ ] `register_error_handlers(app)` с per-type + catch-all `Exception`
- [ ] Catch-all → 500 + `logger.exception` + `traceId` в response
- [ ] `RequestValidationError` (pydantic) приведён к нашей форме 400
- [ ] httpx out-adapter ловит `HTTPStatusError`/`TimeoutException` → port-specific
- [ ] Никаких try/except в UseCase Handler / Domain Service / Aggregate
- [ ] `tenacity @retry` только на идемпотентных Integration-вызовах, `retry_if_exception_type` на 5xx-типе
- [ ] `app_errors_total{type,exception}` экспонирована; span.record_exception на ошибке
- [ ] structlog: domain=WARNING, technical/unexpected=ERROR; PII не в логах (`AUTH-16`)
- [ ] `application/problem+json` media-type на всех error-response
- [ ] Spec в `docs/spec/errors/` — каждое доменное исключение имеет карточку
```
