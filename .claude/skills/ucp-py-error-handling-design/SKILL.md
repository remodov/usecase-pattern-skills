---
name: ucp-py-error-handling-design
lang: python
description: Спроектировать обработку ошибок в FastAPI-сервисе на Python (требования error-handling/*) — иерархия от AppError, edge exception-handlers с problem+json (RFC 9457), port-исключения в httpx out-adapter, retry через tenacity, structlog-наблюдаемость.
when_to_use: При старте сервиса или миграции «except Exception → log → return None»-кода. Триггеры — «настрой обработку ошибок в FastAPI», «exception handlers».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Проектирование обработки ошибок (Python / FastAPI)

Ты создаёшь / расширяешь обработку ошибок в FastAPI-сервисе согласно **общему контракту**
`backend/error-handling/spec.md` (`R-ERR-*`) и его **Python-реализации**
`backend/error-handling/references/python/implementation.md`. Цель — единая стратегия: типизированная иерархия,
ровно три места catch (edge / httpx out-adapter / резильянс-обёртка), консистентный problem+json-mapping, наблюдаемость.

Не делает: валидацию входа (`ucp-py-validation-design`), резилианс-обвязку (`ucp-py-resilience-design`),
маскирование PII в логах (`ucp-py-observability-design`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/error-handling/spec.md` — общий контракт, коды `R-ERR-*` (цитируй их в design-обосновании ответа, **не** в комментариях кода).
   - `.claude/docs/backend/error-handling/references/python/implementation.md` — Python-реализация (FastAPI/httpx/tenacity/structlog), открывай точечно по разделу.
   - `.claude/docs/backend/rest-api/spec.md` — `R-API-ERR-*` для формата problem+json.
   - `.claude/docs/backend/auth-patterns/spec.md` — `auth-patterns/money-commands-need-idempotency-key` (идемпотентность), `auth-patterns/error-response-hides-cause` (PII в response).

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на Python:
   - `core/` — базовые ошибки (`AppError` + 4 типа) + доменные наследники; без фреймворка.
   - `app/` — FastAPI-приложение, `error_handlers.py`, `problem.py`.
   - `adapters/out/<system>/` — httpx-клиент + port-specific ошибки.

3. **Аудит текущего состояния** (что есть / что предстоит): базовые ошибки от `AppError` (`R-ERR-HIER-1/2`), доменные с контекстом (`R-ERR-HIER-3/5`), `register_error_handlers` с per-type + catch-all (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`), httpx-адаптеры мапят `httpx.*` в port-specific (`R-ERR-WHERE-2b`), нет `try/except` в core (`error-handling/catch-does-not-swallow`), метрика `app_errors_total` (`error-handling/errors-counted-by-kind`).

4. **Произведи код** (полные `.py`-файлы; Python 3.11+, тайп-хинты обязательны; без комментариев в коде — соответствие выражается именами/типами/структурой; коды правил в комментариях НЕ цитируй).

   ### 4.1 `core/errors.py` — корень + 4 типа
   `AppError(Exception)` и `DomainError` / `InputValidationError` / `IntegrationError` / `TechnicalError` от него.

   ### 4.2 Доменные наследники с контекстом
   `@dataclass`-исключения с полями (`InsufficientFundsError(customer_id, requested, available)`), имена по бизнес-смыслу.

   ### 4.3 `app/problem.py` + `app/error_handlers.py`
   Хелпер `problem(...)` → `JSONResponse(..., media_type="application/problem+json")`. `register_error_handlers(app)` с per-type (`DomainError`→422/409, `InputValidationError`/`RequestValidationError`→400, `IntegrationError`→502/503/504) + catch-all `Exception`→500 (`logger.exception` + traceId).

   ### 4.4 Port-specific ошибки в httpx-адаптерах
   `<System>Error(IntegrationError)`; в адаптере `except httpx.HTTPStatusError` (4xx → domain-уровень `Invalid…Error`, 5xx → `<System>Error`), `except httpx.TimeoutException/TransportError → <System>Error`. Всегда `raise ... from e`.

   ### 4.5 Убрать `try/except` из Handler/Service/Aggregate
   Доменные `raise`, integration-вызовы бросают `IntegrationError`. Перехват — только на edge / в адаптере.

   ### 4.6 Retry (если есть исходящие вызовы)
   `tenacity @retry(retry=retry_if_exception_type(<System>Error), ...)` только на идемпотентных вызовах; 4xx-производные (`Invalid…Error`) не ретраятся (`R-ERR-RETRY-2/3`).

   ### 4.7 Observability
   `app_errors_total = Counter(..., ["type","exception"])`; в catch-all и domain-handler — `.labels(...).inc()`; `span.record_exception` + `set_status(ERROR)`.

5. **Самопроверка** — пройдись по чеклисту из `python/implementation.md` §«Чеклист подключения».

6. **Финальный шаг:** предложи «запусти `ucp-py-error-handling-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `except Exception: return None` / `log; pass` (`error-handling/catch-does-not-swallow`/`X3`).
- `raise Exception(...)` / `raise RuntimeError(e)` (`error-handling/no-bare-base-exceptions`/`error-handling/catch-does-not-swallow`).
- `status_code=200` при ошибке (`error-handling/no-success-code-for-failure`).
- `str(exc)` низкоуровневой ошибки в `detail` (`error-handling/integration-and-technical-mapping`).
- `@retry` на write без `Idempotency-Key` (`error-handling/retry-semantics-by-kind`).

После работы скилла — обязательно `ucp-py-error-handling-review` для верификации.

$ARGUMENTS
