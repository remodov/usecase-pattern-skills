---
name: ucp-py-resilience-design
lang: python
description: Спроектировать защиту FastAPI-сервиса от отказов внешних систем (коды R-RES-*) — per-system httpx.AsyncClient + Timeout, circuit breaker, asyncio.Semaphore (bulkhead), tenacity retry при идемпотентности, fallback, health-check с TTL.
when_to_use: Подключение внешней системы или добавление resilience. Триггеры — «защити вызов X», «circuit breaker для Y», «таймауты/ретраи на питоне».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Resilience — проектирование (Python / httpx + tenacity + CB + asyncio)

Ты проектируешь защиту от отказов по **контракту** `backend/resilience/resilience-rules.md` (`R-RES-*`) и
**Python-реализации** `backend/resilience/python/resilience-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Python-style-guide. Коды в обосновании, не в коде. Связанные: `backend/hexagonal/python/...` (out-adapter/порт), `integration` (скелет клиента), `observability` (метрики/спаны).

2. **Определи границу** (`R-RES-WHERE-*`): outbound HTTP → полный набор (timeout+CB+semaphore+опц.retry); internal s2s → timeout+CB; scheduler/polling → task-queue; inbound rate-limit → gateway. Не оборачивай локальные операции (`R-RES-WHERE-X1`).

3. **Произведи код** (на public-методе out-adapter, не на сгенерированном клиенте):
   - **Per-system** `httpx.AsyncClient` с `httpx.Limits` + `httpx.Timeout` (connect<read<total) + `asyncio.timeout()` (`R-RES-ISO-1`, `R-RES-TO-1`).
   - **Circuit breaker** (`purgatory` async / `aiobreaker`) per-system, count-based, open→half-open; `CircuitBreakerError` → port-исключение (`R-RES-CB-*`).
   - **Bulkhead** — `asyncio.Semaphore(max_concurrent)` per-system, sizing < pool (`R-RES-BH-*`).
   - **Retry** — `tenacity` только при идемпотентности (read / `Idempotency-Key`), exponential backoff, не на 4xx, ≤3 попыток (`R-RES-RE-*`).
   - **Mapper** DTO внешней системы → domain; порт возвращает domain (`R-RES-OAS-4`).
   - **Health-check** per-system с TTL-кешем (`cachetools.TTLCache`), лёгкий probe (`R-RES-HC-*`).
   - **Конфиг** — `pydantic-settings` `<System>ClientSettings` (`R-RES-CFG-1`).

4. **Polling/async** (`R-RES-ASYNC-*`): через task-queue (`*_task`-таблица + scheduler), не `asyncio.sleep`-цикл; для async-вызовов — `asyncio.timeout()`.

5. **Observability** (`R-RES-OBS-*`): метрики CB/retry/semaphore (`prometheus-client`), OTel-span с `circuit_breaker.state`/`external.system`, WARN на state-transition.

6. **Самопроверка** (§13) + предложи `ucp-py-resilience-review`. Скелет клиента целиком — `ucp-py-integration-design`.

## Антипаттерны, которые НЕ генерировать

- Shared `AsyncClient`/CB на несколько систем (`R-RES-ISO-X1`/`R-RES-CB-X3`); `AsyncClient()` без timeout/limits (`R-RES-TO-X1`).
- CB/retry на репозитории/in-memory (`R-RES-WHERE-X1`); самописный CB на счётчике (`R-RES-CB-X2`); обёртки на сгенерированном клиенте (`R-RES-OAS-X1`).
- Retry write без `Idempotency-Key` (`R-RES-RE-X1`); retry на 4xx (`R-RES-RE-X2`); без backoff (`R-RES-RE-X3`).
- `asyncio.sleep`-цикл опроса в handler (`R-RES-ASYNC-X1`); fallback `Money(0)`/тихий успех (`R-RES-FB-X1/X2`); возврат DTO внешней системы из порта (`R-RES-OAS-X3`).

После работы скилла — обязательно `ucp-py-resilience-review`.

$ARGUMENTS
