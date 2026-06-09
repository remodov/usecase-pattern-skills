---
name: ucp-py-resilience-review
lang: python
description: Ревью защиты FastAPI-сервиса (Python) от отказов внешних систем по UCP (коды R-RES-*) — per-system httpx.AsyncClient/semaphore, timeout+CB+bulkhead+retry на public-методе out-adapter, retry только при идемпотентности, health-check per-system с TTL.
when_to_use: Ревью adapters/out, *ClientSettings, httpx-клиентов, tenacity/circuit-breaker кода.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Resilience (Python / httpx + tenacity + CB + asyncio)

Ты ревьюишь защиту от отказов на соответствие **контракту** `backend/resilience/resilience-rules.md` (`R-RES-*`) и
**Python-реализации** `backend/resilience/python/resilience-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/resilience/resilience-rules.md`** + **`backend/resilience/python/resilience-style-guide.md`**.
- Парные: `backend/hexagonal/python/...` (out-adapter/порт), `observability` (метрики/спаны), `auth-patterns` (`AUTH-19` idempotency для retry).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-RES-CB-X3`, `R-RES-RE-X1`), не префикс.

2. **Скоп.** `adapters/out/**` (`*_adapter.py`, `*_client*.py`), `*_settings.py`/`config`, health-индикаторы, task-queue scheduler, `git diff` на `.py`.

3. **Прогон.**
   - **Где (`R-RES-WHERE-*`):** outbound HTTP — полный набор; CB/retry вокруг репозитория/in-memory → `R-RES-WHERE-X1`.
   - **Isolation (`R-RES-ISO-*`):** per-system `AsyncClient` + `Limits` + CB + semaphore, единое имя. Shared client/CB на несколько систем → `R-RES-ISO-X1`/`R-RES-CB-X3`. `AsyncClient()` без limits/timeout → `R-RES-ISO-X2`/`R-RES-TO-X1`.
   - **Timeouts (`R-RES-TO-*`):** `httpx.Timeout` + `asyncio.timeout`, иерархия connect<read<total. total<read → `R-RES-TO-X2`. read>60s в sync-handler → `R-RES-TO-X3`.
   - **CB (`R-RES-CB-*`):** на public-методе адаптера (не на сгенерированном клиенте/handler/репозитории → `R-RES-CB-X1`); `CircuitBreakerError`→port-исключение. Самописный CB на счётчике → `R-RES-CB-X2`.
   - **Retry (`R-RES-RE-*`):** `tenacity`, только при идемпотентности, exponential backoff. Retry write без `Idempotency-Key` → `R-RES-RE-X1`. Retry на 4xx → `R-RES-RE-X2`. Без backoff → `R-RES-RE-X3`.
   - **Bulkhead (`R-RES-BH-*`):** `asyncio.Semaphore` per-system, sizing<pool. Executor-пул как bulkhead для async → `R-RES-BH-X1`.
   - **Fallback (`R-RES-FB-*`):** не для money (`R-RES-FB-X1`), не тихий «успех» (`R-RES-FB-X2`), не второй провайдер без CB (`R-RES-FB-X3`).
   - **OpenAPI/mapper (`R-RES-OAS-*`):** обёртки не на сгенерированном клиенте (`R-RES-OAS-X1`); mapper DTO→domain, порт возвращает domain (`R-RES-OAS-X3`).
   - **Health (`R-RES-HC-*`):** per-system, TTL-кеш (sync-probe без кеша → `R-RES-HC-X1`), лёгкий probe (бизнес-вызов → `R-RES-HC-X2`).
   - **Async/polling (`R-RES-ASYNC-*`):** polling через task-queue; `asyncio.sleep`-цикл опроса в handler → `R-RES-ASYNC-X1`; `sleep>5s` → `R-RES-ASYNC-X2`.
   - **Observability (`R-RES-OBS-*`):** метрики/спаны CB включены (отключены без причины → `R-RES-OBS-X1`).

4. **Cross-check:** структура out-adapter — `ucp-py-hexagonal-review`; метрики/трейсинг — `ucp-py-observability-review`; idempotency для retry — `ucp-py-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — retry write без идемпотентности (`R-RES-RE-X1`), shared client/CB (`R-RES-ISO-X1`/`R-RES-CB-X3`), нет timeout (`R-RES-TO-X1`), `asyncio.sleep`-цикл polling в handler (`R-RES-ASYNC-X1`), fallback money `0`/тихий успех (`R-RES-FB-X1/X2`).
   - **Предупреждение** — CB на сгенерированном клиенте (`R-RES-OAS-X1`), самописный CB (`R-RES-CB-X2`), retry на 4xx/без backoff (`R-RES-RE-X2/X3`), executor-bulkhead (`R-RES-BH-X1`), health без кеша (`R-RES-HC-X1`).
   - **Замечание** — возврат DTO внешней системы из порта (`R-RES-OAS-X3`), метрики resilience выключены (`R-RES-OBS-X1`).

## Что не входит

- Структура out-adapter/портов — `ucp-py-hexagonal-review`. Скелет outbound-клиента — `ucp-py-integration-review`.
- Метрики/трейсинг — `ucp-py-observability-review`.

$ARGUMENTS
