---
name: ucp-py-error-handling-review
lang: python
description: Ревью обработки ошибок в Python/FastAPI-сервисе по UCP — иерархия от AppError, edge exception-handlers, mapping в problem+json (RFC 9457), нет except в core/handler, port-исключения в httpx out-adapter, retry через tenacity.
when_to_use: Изменения в errors.py, error_handlers.py, httpx-клиентах или любом коде с except Exception.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью обработки ошибок (Python / FastAPI)

Ты ревьюишь FastAPI-сервис на соответствие **общему контракту** `backend/error-handling/spec.md`
(`R-ERR-*`, коды едины с Java) и его **Python-реализации** `backend/error-handling/references/python/implementation.md`.
Главные точки: типизированная иерархия от `AppError`, ровно три места catch, problem+json-mapping, отсутствие силент-фейлов.

## Зависимости

- **`.claude/docs/backend/error-handling/spec.md`** — общий контракт (`R-ERR-HIER-*`/`WHERE-*`/`MAP-*`/`LOG-*`/`RETRY-*`/`RESULT-*`/`OBS-*`).
- **`.claude/docs/backend/error-handling/references/python/implementation.md`** — Python-реализация (FastAPI/httpx/tenacity/structlog/prometheus_client).
- Парные: `backend/rest-api/spec.md` (`R-API-ERR-*`), `backend/validation/spec.md`, `backend/resilience/spec.md`, `backend/auth-patterns/spec.md` (`auth-patterns/error-response-hides-cause`/`auth-patterns/money-commands-need-idempotency-key`), `backend/observability/spec.md`.

## Инструкции

1. **Прочти** общий `error-handling/spec.md` и `references/python/implementation.md` (как это выглядит в FastAPI). Цитируй конкретные коды (`error-handling/catch-does-not-swallow`), не префикс.

2. **Определи объект ревью.** Файлы от пользователя либо скоп по умолчанию:
   - `**/errors.py`, `core/**/errors.py` — иерархия (`R-ERR-HIER-*`).
   - `**/error_handlers.py`, `app/**` с `add_exception_handler` — edge (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`).
   - `adapters/out/**/*.py` (httpx-клиенты) — port-specific, ловля `httpx.*` (`R-ERR-WHERE-2b`).
   - `git diff` на изменённые `.py`.
   - **`Grep`**: `except\s+(Exception|BaseException)\s*(as\s+\w+)?\s*:` — потенциальные `error-handling/catch-does-not-swallow`/`X2`/`X3`.

3. **Прогон по подгруппам.**

   ### `R-ERR-HIER-*`
   - 4 базовых типа наследуют один `AppError`, не голый `Exception`? — `R-ERR-HIER-1/2`.
   - Доменные именуются по бизнес-смыслу (`InsufficientFundsError`), не `BusinessError`? — `error-handling/domain-exception-named-by-meaning`.
   - `IntegrationError`-наследники с префиксом системы (`PaymentGatewayError`)? — `error-handling/integration-exception-names-system`.
   - Контекст в конструкторе (`@dataclass`-поля / `__init__`)? Не пустые? — `error-handling/exception-carries-context`.
   - `raise Exception(...)` / `raise RuntimeError(...)` — `error-handling/no-bare-base-exceptions`.
   - `assert` / `raise AssertionError` / `ValueError` как бизнес-правило в core — `error-handling/no-bare-base-exceptions`.

   ### `R-ERR-WHERE-*`
   - В `core/` (Handler/Service/Aggregate) **нет** `try/except`. Любой `except Exception` — критика `error-handling/catch-does-not-swallow`.
   - В `adapters/out/`: каждый `except httpx.HTTPStatusError/TimeoutException/TransportError` → port-specific (`raise PaymentGatewayError(...) from e`)? Иначе нарушение `R-ERR-WHERE-2b`.
   - `register_error_handlers(app)` / `add_exception_handler` существует с per-type + catch-all `Exception`? — `R-ERR-WHERE-2a`.
   - `except ...: return None` / `return []` — критика `error-handling/catch-does-not-swallow`.
   - `except Exception as e: logger.error(...)` без re-raise — критика `error-handling/catch-does-not-swallow`.
   - `except Exception as e: raise RuntimeError(e)` — критика `error-handling/catch-does-not-swallow`.

   ### `R-ERR-MAP-*`
   - Handler `DomainError` → 409/422? — `error-handling/domain-and-validation-mapping`.
   - `RequestValidationError` (pydantic) → 400 + per-field `errors`? — `error-handling/domain-and-validation-mapping`.
   - `IntegrationError` → 502/503/504 по подтипу? — `error-handling/integration-and-technical-mapping`.
   - catch-all `Exception` → 500? — `error-handling/integration-and-technical-mapping`.
   - Все error-response с `media_type="application/problem+json"`? — `R-ERR-MAP-*`.
   - В response нет stacktrace / `str(exc)` низкоуровневой ошибки? — `error-handling/integration-and-technical-mapping`/`X3`.
   - `status_code=200` в error-handler / `{"success": false}` — критика `error-handling/no-success-code-for-failure`.

   ### `R-ERR-LOG-*`
   - `DomainError` → `logger.warning` (не error)? — `error-handling/log-level-matches-kind`.
   - catch-all → `logger.exception(...)` или `logger.error(..., exc_info=exc)` со stacktrace? — `error-handling/log-level-matches-kind`.
   - `logger.error(...); raise` — `error-handling/log-once-with-exception`.
   - `logger.error(str(e))` без `exc_info` — `error-handling/log-once-with-exception`.

   ### `R-ERR-RETRY-*`
   - `tenacity @retry` ловит `DomainError`/`InputValidationError` — нарушение `error-handling/retry-semantics-by-kind`.
   - `retry_if_exception_type` включает 4xx-производное — `error-handling/retry-semantics-by-kind`.
   - `@retry` на write без `Idempotency-Key` — критика `error-handling/retry-semantics-by-kind` + `resilience/retry-only-when-safe`/`auth-patterns/money-commands-need-idempotency-key`.

   ### `R-ERR-RESULT-*`
   - Глобальный `returns.Result`/`Either` вместо исключений в цепочке Handler→Domain→Adapter — `error-handling/result-type-is-local-choice`.

   ### `R-ERR-OBS-*`
   - `app_errors_total` (prometheus_client `Counter` с `type`/`exception`) экспонирована? — `error-handling/errors-counted-by-kind`.
   - `span.record_exception` + `set_status(ERROR)` на ошибке? — `error-handling/trace-span-marked-error`.
   - Алёрты только на `unexpected`/`technical`, не на любую error-метрику — `error-handling/alert-on-patterns-not-exceptions`.

4. **Cross-check:** `@retry` на write без ключа → `auth-patterns/money-commands-need-idempotency-key`/`resilience/retry-only-when-safe`; PII в `detail` → `auth-patterns/error-response-hides-cause`; problem+json формат → `R-API-ERR-*`; pydantic-валидация → `validation/input-validated-at-edge`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Доменные ориентиры серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — `error-handling/catch-does-not-swallow` (silent `except Exception`), `error-handling/catch-does-not-swallow` (`return None` в except), `error-handling/no-success-code-for-failure` (200 при ошибке), `error-handling/integration-and-technical-mapping` (SQL-текст в response), `error-handling/retry-semantics-by-kind` (retry write без ключа), отсутствие catch-all.
   - **Предупреждение** — `R-ERR-HIER-X1/X2`, `error-handling/catch-does-not-swallow`, `R-ERR-LOG-X1/X2`, DomainError на ERROR-уровне.
   - **Замечание** — нет `app_errors_total`, конструктор без контекста, нет spec-карточки.

## Что не входит

- Формат problem+json (поля) — `ucp-api-review` (`R-API-ERR-*`).
- Pydantic-constraints — `ucp-py-validation-review`.
- Retry-policy конфиг — `ucp-py-resilience-review`.
- PII в логах — `ucp-py-observability-review` / `ucp-auth-review`.

$ARGUMENTS
