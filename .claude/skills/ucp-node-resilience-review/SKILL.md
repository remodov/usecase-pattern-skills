---
name: ucp-node-resilience-review
lang: node
description: Ревью защиты NestJS-сервиса (Node/TypeScript) от отказов внешних систем по UCP (коды R-RES-*) — per-system undici/axios + cockatiel wrap(retry+CB+bulkhead+timeout), retry только при идемпотентности, terminus health per-system с TTL.
when_to_use: Ревью adapters/out, *ClientConfig, cockatiel-политик, terminus-индикаторов, task-queue polling в NestJS.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Resilience (Node / NestJS + cockatiel + undici/axios + terminus)

Ты ревьюишь защиту от отказов на соответствие **контракту** `backend/resilience/resilience-rules.md` (`R-RES-*`) и
**Node-реализации** `backend/resilience/node/resilience-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/resilience/resilience-rules.md`** + **`backend/resilience/node/resilience-style-guide.md`**.
- Парные: `backend/hexagonal/node/...` (out-adapter/порт), `backend/observability/node/...` (метрики/спаны), `backend/auth-patterns/node/...` (`AUTH-19` idempotency для retry).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-RES-CB-X3`, `R-RES-RE-X1`), не префикс.

2. **Скоп.** `src/adapters/out/**` (`*.adapter.ts`, `*-client*.ts`), `*-client.config.ts`/`*ClientConfig`, terminus-индикаторы, `@Interval`-poller'ы task-queue, `git diff` на `.ts`.

3. **Прогон.**
   - **Где (`R-RES-WHERE-*`):** outbound HTTP — полный набор (timeout + CB + bulkhead + опц. retry); CB/bulkhead вокруг репозитория/in-memory → `R-RES-WHERE-X1`.
   - **Isolation (`R-RES-ISO-*`):** per-system undici `new Agent(...)` или `axios.create({...})` c собственным `http(s)Agent + maxSockets` + cockatiel-policy как singleton в DI; единое имя (`SBER_CLIENT`, `SBER_POLICY`). Shared клиент на несколько систем → `R-RES-ISO-X1`. Клиент без явных `connections/timeout` → `R-RES-ISO-X2`/`R-RES-TO-X1` (axios `timeout: 0` = ∞).
   - **Timeouts (`R-RES-TO-*`):** иерархия undici `connectTimeout < headersTimeout ≤ bodyTimeout` + cockatiel `timeout(total)` вокруг вызова (для axios: `timeout` = read-уровень, total — policy). total < read → `R-RES-TO-X2`. read > 60s в синхронном handler → `R-RES-TO-X3`. Конфиг через типизированный `*ClientConfig` (zod/class-validator) → `R-RES-TO-2`.
   - **CB (`R-RES-CB-*`):** на public-методе out-adapter, не на сгенерированном клиенте/handler/репозитории → `R-RES-CB-X1`; `CountBreaker({ threshold: 0.5, size: 50 })`; `halfOpenAfter: 30_000`; `BrokenCircuitError` → port-исключение (`...SystemUnavailable`). Самописный CB на `try/catch + счётчик` → `R-RES-CB-X2`. Общий CB-инстанс/`handleAll`-policy на разные системы → `R-RES-CB-X3`. policy пересоздаётся на вызов (не singleton в DI) → нарушает `R-RES-CB-X3`.
   - **Retry (`R-RES-RE-*`):** cockatiel `retry()` + `ExponentialBackoff`, только при идемпотентности (`findX` / команда с `Idempotency-Key`), `handleType(...)` только на транзиентные (timeout/5xx/`ECONNREFUSED`/`UND_ERR_*`), `maxAttempts: 3` (макс 5). Retry write без `Idempotency-Key` → `R-RES-RE-X1`. Retry на 4xx → `R-RES-RE-X2`. Без exponential backoff → `R-RES-RE-X3`. Сторонние авто-retry (axios-retry, `got`-defaults, RxJS `retry()` в `HttpService`) без интеграции с CB → `R-RES-RE-X4`.
   - **Bulkhead (`R-RES-BH-*`):** cockatiel `bulkhead(maxConcurrent, queueLimit)` per-system, отдельно от connection-pool; `maxConcurrent ≈ connections × 0.8`; `queueLimit` маленький (0–N). Вынос outbound I/O в `worker_threads`/piscina «как bulkhead» → `R-RES-BH-X1` (теряется `AsyncLocalStorage`).
   - **Fallback (`R-RES-FB-*`):** не для money-операций → `R-RES-FB-X1`; не тихий «успех» → `R-RES-FB-X2`; fallback с вызовом второго провайдера без своего CB → `R-RES-FB-X3`.
   - **OpenAPI/mapper (`R-RES-OAS-*`):** policy-обёртки на public-методе адаптера, не на сгенерированном клиенте (`openapi-typescript`/`openapi-fetch`) → `R-RES-OAS-X1`; CB в generic `executeCall<T>` со строкой-параметром системы → `R-RES-OAS-X2`; mapper generated DTO → domain обязателен, порт возвращает domain-типы → нарушение `R-RES-OAS-X3`.
   - **Health (`R-RES-HC-*`):** per-system `@nestjs/terminus` custom indicator в readiness (`/health/ready`); TTL-кеш ~30s (`{ up, at }` + `Date.now()`); лёгкий probe (`GET /health`/`OPTIONS`), не бизнес-вызов. Probe без кеша → `R-RES-HC-X1`. Probe бизнес-операцией → `R-RES-HC-X2`.
   - **Async/polling (`R-RES-ASYNC-*`):** polling внешней системы — через `*_task`-таблицу + `@Interval`-poller; `await sleep(...)`-цикл опроса в handler → `R-RES-ASYNC-X1`; `sleep > 5s` → `R-RES-ASYNC-X2`; на каждый async-вызов — отдельный `timeout()` / `AbortSignal.timeout()` → `R-RES-ASYNC-3`.
   - **Observability (`R-RES-OBS-*`):** prom-client gauges/counters на `onBreak`/`onReset`/`onHalfOpen`, `onFailure`/`onSuccess`, bulkhead `executionSlots`; OTel-span с атрибутами `circuit_breaker.state`, `external.system`; WARN-лог на каждый state-transition CB (system, prev_state, new_state). Отсутствие метрик → `R-RES-OBS-X1`.

4. **Cross-check:** структура out-adapter/порта — `ucp-node-hexagonal-review`; метрики/трейсинг — `ucp-node-observability-review`; idempotency для retry — `ucp-node-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — retry write без `Idempotency-Key` (`R-RES-RE-X1`), shared клиент/CB на несколько систем (`R-RES-ISO-X1`/`R-RES-CB-X3`), клиент без timeout (`R-RES-TO-X1`, axios `timeout: 0`), `await sleep(...)`-цикл polling в handler (`R-RES-ASYNC-X1`), fallback money `null`/`0`/тихий успех (`R-RES-FB-X1/X2`).
   - **Предупреждение** — CB/policy на сгенерированном клиенте (`R-RES-OAS-X1`), CB в generic-helper со строкой (`R-RES-OAS-X2`), самописный CB (`R-RES-CB-X2`), retry на 4xx/без backoff (`R-RES-RE-X2/X3`), сторонние авто-retry без CB (`R-RES-RE-X4`), worker-пул как bulkhead (`R-RES-BH-X1`), health без TTL-кеша (`R-RES-HC-X1`).
   - **Замечание** — возврат generated DTO из порта (`R-RES-OAS-X3`), probe бизнес-операцией (`R-RES-HC-X2`), метрики resilience отсутствуют (`R-RES-OBS-X1`).

## Что не входит

- Структура out-adapter/портов — `ucp-node-hexagonal-review`. Скелет outbound-клиента — `ucp-node-integration-review`.
- Метрики/трейсинг — `ucp-node-observability-review`.

$ARGUMENTS
