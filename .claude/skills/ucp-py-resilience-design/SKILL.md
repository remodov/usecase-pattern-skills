---
name: ucp-py-resilience-design
lang: python
description: Спроектировать защиту FastAPI-сервиса от отказов внешних систем (требования resilience/*) — per-system httpx.AsyncClient + Timeout, circuit breaker, asyncio.Semaphore (bulkhead), tenacity retry при идемпотентности, fallback, health-check с TTL.
when_to_use: Подключение внешней системы или добавление resilience. Триггеры — «защити вызов X», «circuit breaker для Y», «таймауты/ретраи на питоне».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*) Bash(ruff*)
---

# Resilience — проектирование (Python / httpx + tenacity + CB + asyncio)

Ты проектируешь защиту от отказов по **контракту** `backend/resilience/spec.md` (`R-RES-*`) и
**Python-реализации** `backend/resilience/references/python/implementation.md`.

## Инструкции

1. **Прочитай** требования `python-style/*`. Коды в обосновании, не в коде. Связанные: `backend/hexagonal/python/...` (out-adapter/порт), `integration` (скелет клиента), `observability` (метрики/спаны).

2. **Определи границу** (`R-RES-WHERE-*`): outbound HTTP → полный набор (timeout+CB+semaphore+опц.retry); internal s2s → timeout+CB; scheduler/polling → task-queue; inbound rate-limit → gateway. Не оборачивай локальные операции (`resilience/no-protection-around-local-operations`).

3. **Произведи код** (на public-методе out-adapter, не на сгенерированном клиенте):
   - **Per-system** `httpx.AsyncClient` с `httpx.Limits` + `httpx.Timeout` (connect<read<total) + `asyncio.timeout()` (`resilience/client-per-external-system`, `resilience/timeout-hierarchy`).
   - **Circuit breaker** (`purgatory` async / `aiobreaker`) per-system, count-based, open→half-open; `CircuitBreakerError` → port-исключение (`R-RES-CB-*`).
   - **Bulkhead** — `asyncio.Semaphore(max_concurrent)` per-system, sizing < pool (`R-RES-BH-*`).
   - **Retry** — `tenacity` только при идемпотентности (read / `Idempotency-Key`), exponential backoff, не на 4xx, ≤3 попыток (`R-RES-RE-*`).
   - **Mapper** DTO внешней системы → domain; порт возвращает domain (`resilience/mapper-between-client-and-port`).
   - **Health-check** per-system с TTL-кешем (`cachetools.TTLCache`), лёгкий probe (`R-RES-HC-*`).
   - **Конфиг** — `pydantic-settings` `<System>ClientSettings` (`resilience/declarative-configuration`).

4. **Polling/async** (`R-RES-ASYNC-*`): через task-queue (`*_task`-таблица + scheduler), не `asyncio.sleep`-цикл; для async-вызовов — `asyncio.timeout()`.

5. **Observability** (`R-RES-OBS-*`): метрики CB/retry/semaphore (`prometheus-client`), OTel-span с `circuit_breaker.state`/`external.system`, WARN на state-transition.

6. **Самопроверка** (§13) + предложи `ucp-py-resilience-review`. Скелет клиента целиком — `ucp-py-integration-design`.

## Антипаттерны, которые НЕ генерировать

- Shared `AsyncClient`/CB на несколько систем (`resilience/client-per-external-system`/`resilience/instance-names-match-system`); `AsyncClient()` без timeout/limits (`resilience/timeout-hierarchy`).
- CB/retry на репозитории/in-memory (`resilience/no-protection-around-local-operations`); самописный CB на счётчике (`resilience/no-custom-breaker`); обёртки на сгенерированном клиенте (`resilience/breaker-on-adapter-method`).
- Retry write без `Idempotency-Key` (`resilience/retry-only-when-safe`); retry на 4xx (`resilience/retry-only-when-safe`); без backoff (`resilience/retry-with-backoff-and-limit`).
- `asyncio.sleep`-цикл опроса в handler (`resilience/no-long-synchronous-waits`); fallback `Money(0)`/тихий успех (`R-RES-FB-X1/X2`); возврат DTO внешней системы из порта (`R-RES-OAS-X3`).

После работы скилла — обязательно `ucp-py-resilience-review`.

$ARGUMENTS
