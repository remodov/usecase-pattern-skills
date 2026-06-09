---
name: ucp-py-error-handling-design
lang: python
description: Спроектировать обработку ошибок в FastAPI-сервисе на Python (коды R-ERR-*) — иерархия от AppError, edge exception-handlers с problem+json (RFC 9457), port-исключения в httpx out-adapter, retry через tenacity, structlog-наблюдаемость.
when_to_use: При старте сервиса или миграции «except Exception → log → return None»-кода. Триггеры — «настрой обработку ошибок в FastAPI», «exception handlers».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Проектирование обработки ошибок (Python / FastAPI)

Ты создаёшь / расширяешь обработку ошибок в FastAPI-сервисе согласно **общему контракту**
`backend/error-handling/error-handling-rules.md` (`R-ERR-*`) и его **Python-реализации**
`backend/error-handling/python/error-handling-style-guide.md`. Цель — единая стратегия: типизированная иерархия,
ровно три места catch (edge / httpx out-adapter / резильянс-обёртка), консистентный problem+json-mapping, наблюдаемость.

Не делает: валидацию входа (`ucp-py-validation-design`), резилианс-обвязку (`ucp-py-resilience-design`),
маскирование PII в логах (`ucp-py-observability-design`).

## Инструкции

1. **Прочитай**:
   - `.claude/docs/backend/error-handling/error-handling-rules.md` — общий контракт, коды `R-ERR-*` (цитируй их в design-обосновании ответа, **не** в комментариях кода).
   - `.claude/docs/backend/error-handling/python/error-handling-style-guide.md` — Python-реализация (FastAPI/httpx/tenacity/structlog), открывай точечно по разделу.
   - `.claude/docs/backend/rest-api/rest-api-rules.md` — `R-API-ERR-*` для формата problem+json.
   - `.claude/docs/backend/auth-patterns/auth-patterns-rules.md` — `AUTH-19` (идемпотентность), `AUTH-18` (PII в response).

2. **Идентифицируй сервис.** `git diff` или путь от пользователя. Структура UCP на Python:
   - `core/` — базовые ошибки (`AppError` + 4 типа) + доменные наследники; без фреймворка.
   - `app/` — FastAPI-приложение, `error_handlers.py`, `problem.py`.
   - `adapters/out/<system>/` — httpx-клиент + port-specific ошибки.

3. **Аудит текущего состояния** (что есть / что предстоит): базовые ошибки от `AppError` (`R-ERR-HIER-1/2`), доменные с контекстом (`R-ERR-HIER-3/5`), `register_error_handlers` с per-type + catch-all (`R-ERR-WHERE-2a`, `R-ERR-MAP-*`), httpx-адаптеры мапят `httpx.*` в port-specific (`R-ERR-WHERE-2b`), нет `try/except` в core (`R-ERR-WHERE-X1`), метрика `app_errors_total` (`R-ERR-OBS-1`).

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

5. **Самопроверка** — пройдись по чеклисту из `python/error-handling-style-guide.md` §«Чеклист подключения».

6. **Финальный шаг:** предложи «запусти `ucp-py-error-handling-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `except Exception: return None` / `log; pass` (`R-ERR-WHERE-X1`/`X3`).
- `raise Exception(...)` / `raise RuntimeError(e)` (`R-ERR-HIER-X1`/`R-ERR-WHERE-X2`).
- `status_code=200` при ошибке (`R-ERR-MAP-X1`).
- `str(exc)` низкоуровневой ошибки в `detail` (`R-ERR-MAP-X3`).
- `@retry` на write без `Idempotency-Key` (`R-ERR-RETRY-3`).

После работы скилла — обязательно `ucp-py-error-handling-review` для верификации.

$ARGUMENTS
