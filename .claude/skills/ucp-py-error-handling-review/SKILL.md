---
name: ucp-py-error-handling-review
lang: python
description: Ревью обработки ошибок в Python/FastAPI-сервисе по UCP (коды R-ERR-*) — иерархия от AppError, edge exception-handlers, mapping в problem+json (RFC 9457), нет except в core/handler, port-исключения в httpx out-adapter, retry через tenacity.
when_to_use: Изменения в errors.py, error_handlers.py, httpx-клиентах или любом коде с except Exception.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью обработки ошибок (Python / FastAPI)

Ты ревьюишь FastAPI-сервис на соответствие **общему контракту** `backend/error-handling/error-handling-rules.md`
(`R-ERR-*`, коды едины с Java) и его **Python-реализации** `backend/error-handling/python/error-handling-style-guide.md`.
Главные точки: типизированная иерархия от `AppError`, ровно три места catch, problem+json-mapping, отсутствие силент-фейлов.

## Зависимости

- **`.claude/docs/backend/error-handling/error-handling-rules.md`** — общий контракт (`R-ERR-HIER-*`/`WHERE-*`/`MAP-*`/`LOG-*`/`RETRY-*`/`RESULT-*`/`OBS-*`).
- **`.claude/docs/backend/error-handling/python/error-handling-style-guide.md`** — Python-реализация (FastAPI/httpx/tenacity/structlog/prometheus_client).
- Парные: `backend/rest-api/rest-api-rules.md` (`R-API-ERR-*`), `backend/validation/validation-rules.md`, `backend/resilience/resilience-rules.md`, `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-18`/`AUTH-19`), `backend/observability/observability-rules.md`.

## Инструкции

1. **Прочти** общий `error-handling-rules.md` (коды) и Python-style-guide (как это выглядит в FastAPI). Цитируй конкретные коды (`R-ERR-WHERE-X1`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/errors.py`, `core/**/errors.py` — иерархия (`R-ERR-HIER-*`).
   - `**/error_handlers.py`, `app/**` с `add_exception_handler` — edge (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapters/out/**/*.py` (httpx-клиенты) — port-specific, ловля `httpx.*` (`R-ERR-WHERE-2b`).
   - `git diff` на изменённые `.py`.
   - **`Grep`**: `except\s+(Exception|BaseException)\s*(as\s+\w+)?\s*:` — потенциальные `R-ERR-WHERE-X1`/`X2`/`X3`.

3. **Прогон по подгруппам.**

   ### `R-ERR-HIER-*`
   - 4 базовых типа наследуют один `AppError`, не голый `Exception`? — `R-ERR-HIER-1/2`.
   - Доменные именуются по бизнес-смыслу (`InsufficientFundsError`), не `BusinessError`? — `R-ERR-HIER-3`.
   - `IntegrationError`-наследники с префиксом системы (`PaymentGatewayError`)? — `R-ERR-HIER-4`.
   - Контекст в конструкторе (`@dataclass`-поля / `__init__`)? Не пустые? — `R-ERR-HIER-5`.
   - `raise Exception(...)` / `raise RuntimeError(...)` — `R-ERR-HIER-X1`.
   - `assert` / `raise AssertionError` / `ValueError` как бизнес-правило в core — `R-ERR-HIER-X2`.

   ### `R-ERR-WHERE-*`
   - В `core/` (Handler/Service/Aggregate) **нет** `try/except`. Любой `except Exception` — критика `R-ERR-WHERE-X1`.
   - В `adapters/out/`: каждый `except httpx.HTTPStatusError/TimeoutException/TransportError` → port-specific (`raise PaymentGatewayError(...) from e`)? Иначе нарушение `R-ERR-WHERE-2b`.
   - `register_error_handlers(app)` / `add_exception_handler` существует с per-type + catch-all `Exception`? — `R-ERR-WHERE-2a`.
   - `except ...: return None` / `return []` — критика `R-ERR-WHERE-X3`.
   - `except Exception as e: logger.error(...)` без re-raise — критика `R-ERR-WHERE-X1`.
   - `except Exception as e: raise RuntimeError(e)` — критика `R-ERR-WHERE-X2`.

   ### `R-ERR-MAP-*`
   - Handler `DomainError` → 409/422? — `R-ERR-MAP-1`.
   - `RequestValidationError` (pydantic) → 400 + per-field `errors`? — `R-ERR-MAP-2`.
   - `IntegrationError` → 502/503/504 по подтипу? — `R-ERR-MAP-3`.
   - catch-all `Exception` → 500? — `R-ERR-MAP-5`.
   - Все error-response с `media_type="application/problem+json"`? — `R-ERR-MAP-*`.
   - В response нет stacktrace / `str(exc)` низкоуровневой ошибки? — `R-ERR-MAP-X2`/`X3`.
   - `status_code=200` в error-handler / `{"success": false}` — критика `R-ERR-MAP-X1`.

   ### `R-ERR-LOG-*`
   - `DomainError` → `logger.warning` (не error)? — `R-ERR-LOG-1`.
   - catch-all → `logger.exception(...)` или `logger.error(..., exc_info=exc)` со stacktrace? — `R-ERR-LOG-3`.
   - `logger.error(...); raise` — `R-ERR-LOG-X1`.
   - `logger.error(str(e))` без `exc_info` — `R-ERR-LOG-X2`.

   ### `R-ERR-RETRY-*`
   - `tenacity @retry` ловит `DomainError`/`InputValidationError` — нарушение `R-ERR-RETRY-1`.
   - `retry_if_exception_type` включает 4xx-производное — `R-ERR-RETRY-2`.
   - `@retry` на write без `Idempotency-Key` — критика `R-ERR-RETRY-3` + `R-RES-RE-X1`/`AUTH-19`.

   ### `R-ERR-RESULT-*`
   - Глобальный `returns.Result`/`Either` вместо исключений в цепочке Handler→Domain→Adapter — `R-ERR-RESULT-X1`.

   ### `R-ERR-OBS-*`
   - `app_errors_total` (prometheus_client `Counter` с `type`/`exception`) экспонирована? — `R-ERR-OBS-1`.
   - `span.record_exception` + `set_status(ERROR)` на ошибке? — `R-ERR-OBS-2`.
   - Алёрты только на `unexpected`/`technical`, не на любую error-метрику — `R-ERR-OBS-X1`.

4. **Cross-check:** `@retry` на write без ключа → `AUTH-19`/`R-RES-RE-X1`; PII в `detail` → `AUTH-18`; problem+json формат → `R-API-ERR-*`; pydantic-валидация → `R-VLD-WHERE-1`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`RFF-12`):
   - **Критично** — `R-ERR-WHERE-X1` (silent `except Exception`), `R-ERR-WHERE-X3` (`return None` в except), `R-ERR-MAP-X1` (200 при ошибке), `R-ERR-MAP-X3` (SQL-текст в response), `R-ERR-RETRY-3` (retry write без ключа), отсутствие catch-all.
   - **Предупреждение** — `R-ERR-HIER-X1/X2`, `R-ERR-WHERE-X2`, `R-ERR-LOG-X1/X2`, DomainError на ERROR-уровне.
   - **Замечание** — нет `app_errors_total`, конструктор без контекста, нет spec-карточки.

## Что не входит

- Формат problem+json (поля) — `ucp-api-review` (`R-API-ERR-*`).
- Pydantic-constraints — `ucp-py-validation-review`.
- Retry-policy конфиг — `ucp-py-resilience-review`.
- PII в логах — `ucp-py-observability-review` / `ucp-auth-review`.

$ARGUMENTS
