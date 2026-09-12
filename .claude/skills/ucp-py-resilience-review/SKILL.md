---
name: ucp-py-resilience-review
lang: python
description: Ревью защиты FastAPI-сервиса (Python) от отказов внешних систем по UCP — per-system httpx.AsyncClient/semaphore, timeout+CB+bulkhead+retry на public-методе out-adapter, retry только при идемпотентности, health-check per-system с TTL.
when_to_use: Ревью adapters/out, *ClientSettings, httpx-клиентов, tenacity/circuit-breaker кода.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Resilience (Python / httpx + tenacity + CB + asyncio)

Ты ревьюишь защиту от отказов на соответствие **контракту** `backend/resilience/spec.md` (`R-RES-*`) и
**Python-реализации** `backend/resilience/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/resilience/spec.md`** + **`backend/resilience/references/python/implementation.md`**.
- Парные: `backend/hexagonal/python/...` (out-adapter/порт), `observability` (метрики/спаны), `auth-patterns` (`auth-patterns/money-commands-need-idempotency-key` idempotency для retry).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`resilience/instance-names-match-system`, `resilience/retry-only-when-safe`), не префикс.

2. **Скоп.** `adapters/out/**` (`*_adapter.py`, `*_client*.py`), `*_settings.py`/`config`, health-индикаторы, task-queue scheduler, `git diff` на `.py`.

3. **Прогон.**
   - **Где (`R-RES-WHERE-*`):** outbound HTTP — полный набор; CB/retry вокруг репозитория/in-memory → `resilience/no-protection-around-local-operations`.
   - **Isolation (`R-RES-ISO-*`):** per-system `AsyncClient` + `Limits` + CB + semaphore, единое имя. Shared client/CB на несколько систем → `resilience/client-per-external-system`/`resilience/instance-names-match-system`. `AsyncClient()` без limits/timeout → `resilience/client-per-external-system`/`resilience/timeout-hierarchy`.
   - **Timeouts (`R-RES-TO-*`):** `httpx.Timeout` + `asyncio.timeout`, иерархия connect<read<total. total<read → `resilience/timeout-hierarchy`. read>60s в sync-handler → `resilience/no-long-synchronous-waits`.
   - **CB (`R-RES-CB-*`):** на public-методе адаптера (не на сгенерированном клиенте/handler/репозитории → `resilience/no-protection-around-local-operations`); `CircuitBreakerError`→port-исключение. Самописный CB на счётчике → `resilience/no-custom-breaker`.
   - **Retry (`R-RES-RE-*`):** `tenacity`, только при идемпотентности, exponential backoff. Retry write без `Idempotency-Key` → `resilience/retry-only-when-safe`. Retry на 4xx → `resilience/retry-only-when-safe`. Без backoff → `resilience/retry-with-backoff-and-limit`.
   - **Bulkhead (`R-RES-BH-*`):** `asyncio.Semaphore` per-system, sizing<pool. Executor-пул как bulkhead для async → `resilience/bulkhead-is-semaphore-based`.
   - **Fallback (`R-RES-FB-*`):** не для money (`resilience/fallback-does-not-fake-success`), не тихий «успех» (`resilience/fallback-does-not-fake-success`), не второй провайдер без CB (`resilience/fallback-does-not-fake-success`).
   - **OpenAPI/mapper (`R-RES-OAS-*`):** обёртки не на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); mapper DTO→domain, порт возвращает domain (`R-RES-OAS-X3`).
   - **Health (`R-RES-HC-*`):** per-system, TTL-кеш (sync-probe без кеша → `resilience/cached-health-probe-per-system`), лёгкий probe (бизнес-вызов → `resilience/cached-health-probe-per-system`).
   - **Async/polling (`R-RES-ASYNC-*`):** polling через task-queue; `asyncio.sleep`-цикл опроса в handler → `resilience/no-long-synchronous-waits`; `sleep>5s` → `resilience/no-long-synchronous-waits`.
   - **Observability (`R-RES-OBS-*`):** метрики/спаны CB включены (отключены без причины → `resilience/resilience-state-is-observable`).

4. **Cross-check:** структура out-adapter — `ucp-py-hexagonal-review`; метрики/трейсинг — `ucp-py-observability-review`; idempotency для retry — `ucp-py-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — retry write без идемпотентности (`resilience/retry-only-when-safe`), shared client/CB (`resilience/client-per-external-system`/`resilience/instance-names-match-system`), нет timeout (`resilience/timeout-hierarchy`), `asyncio.sleep`-цикл polling в handler (`resilience/no-long-synchronous-waits`), fallback money `0`/тихий успех (`R-RES-FB-X1/X2`).
   - **Предупреждение** — CB на сгенерированном клиенте (`resilience/breaker-on-adapter-method`), самописный CB (`resilience/no-custom-breaker`), retry на 4xx/без backoff (`R-RES-RE-X2/X3`), executor-bulkhead (`resilience/bulkhead-is-semaphore-based`), health без кеша (`resilience/cached-health-probe-per-system`).
   - **Замечание** — возврат DTO внешней системы из порта (`R-RES-OAS-X3`), метрики resilience выключены (`resilience/resilience-state-is-observable`).

## Что не входит

- Структура out-adapter/портов — `ucp-py-hexagonal-review`. Скелет outbound-клиента — `ucp-py-integration-review`.
- Метрики/трейсинг — `ucp-py-observability-review`.

$ARGUMENTS
