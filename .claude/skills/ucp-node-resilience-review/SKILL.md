---
name: ucp-node-resilience-review
lang: node
description: Ревью защиты NestJS-сервиса (Node/TypeScript) от отказов внешних систем по UCP (требования resilience/*) — per-system undici/axios + cockatiel wrap(retry+CB+bulkhead+timeout), retry только при идемпотентности, terminus health per-system с TTL.
when_to_use: Ревью adapters/out, *ClientConfig, cockatiel-политик, terminus-индикаторов, task-queue polling в NestJS.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Resilience (Node / NestJS + cockatiel + undici/axios + terminus)

Ты ревьюишь защиту от отказов на соответствие **контракту** `backend/resilience/spec.md` (`R-RES-*`) и
**Node-реализации** `backend/resilience/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/resilience/spec.md`** + **`backend/resilience/references/node/implementation.md`**.
- Парные: `backend/hexagonal/node/...` (out-adapter/порт), `backend/observability/node/...` (метрики/спаны), `backend/auth-patterns/node/...` (`auth-patterns/money-commands-need-idempotency-key` idempotency для retry).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`resilience/instance-names-match-system`, `resilience/retry-only-when-safe`), не префикс.

2. **Скоп.** `src/adapters/out/**` (`*.adapter.ts`, `*-client*.ts`), `*-client.config.ts`/`*ClientConfig`, terminus-индикаторы, `@Interval`-poller'ы task-queue, `git diff` на `.ts`.

3. **Прогон.**
   - **Где (`R-RES-WHERE-*`):** outbound HTTP — полный набор (timeout + CB + bulkhead + опц. retry); CB/bulkhead вокруг репозитория/in-memory → `resilience/no-protection-around-local-operations`.
   - **Isolation (`R-RES-ISO-*`):** per-system undici `new Agent(...)` или `axios.create({...})` c собственным `http(s)Agent + maxSockets` + cockatiel-policy как singleton в DI; единое имя (`SBER_CLIENT`, `SBER_POLICY`). Shared клиент на несколько систем → `resilience/client-per-external-system`. Клиент без явных `connections/timeout` → `resilience/client-per-external-system`/`resilience/timeout-hierarchy` (axios `timeout: 0` = ∞).
   - **Timeouts (`R-RES-TO-*`):** иерархия undici `connectTimeout < headersTimeout ≤ bodyTimeout` + cockatiel `timeout(total)` вокруг вызова (для axios: `timeout` = read-уровень, total — policy). total < read → `resilience/timeout-hierarchy`. read > 60s в синхронном handler → `resilience/no-long-synchronous-waits`. Конфиг через типизированный `*ClientConfig` (zod/class-validator) → `resilience/timeout-hierarchy`.
   - **CB (`R-RES-CB-*`):** на public-методе out-adapter, не на сгенерированном клиенте/handler/репозитории → `resilience/no-protection-around-local-operations`; `CountBreaker({ threshold: 0.5, size: 50 })`; `halfOpenAfter: 30_000`; `BrokenCircuitError` → port-исключение (`...SystemUnavailable`). Самописный CB на `try/catch + счётчик` → `resilience/no-custom-breaker`. Общий CB-инстанс/`handleAll`-policy на разные системы → `resilience/instance-names-match-system`. policy пересоздаётся на вызов (не singleton в DI) → нарушает `resilience/instance-names-match-system`.
   - **Retry (`R-RES-RE-*`):** cockatiel `retry()` + `ExponentialBackoff`, только при идемпотентности (`findX` / команда с `Idempotency-Key`), `handleType(...)` только на транзиентные (timeout/5xx/`ECONNREFUSED`/`UND_ERR_*`), `maxAttempts: 3` (макс 5). Retry write без `Idempotency-Key` → `resilience/retry-only-when-safe`. Retry на 4xx → `resilience/retry-only-when-safe`. Без exponential backoff → `resilience/retry-with-backoff-and-limit`. Сторонние авто-retry (axios-retry, `got`-defaults, RxJS `retry()` в `HttpService`) без интеграции с CB → `resilience/retry-with-backoff-and-limit`.
   - **Bulkhead (`R-RES-BH-*`):** cockatiel `bulkhead(maxConcurrent, queueLimit)` per-system, отдельно от connection-pool; `maxConcurrent ≈ connections × 0.8`; `queueLimit` маленький (0–N). Вынос outbound I/O в `worker_threads`/piscina «как bulkhead» → `resilience/bulkhead-is-semaphore-based` (теряется `AsyncLocalStorage`).
   - **Fallback (`R-RES-FB-*`):** не для money-операций → `resilience/fallback-does-not-fake-success`; не тихий «успех» → `resilience/fallback-does-not-fake-success`; fallback с вызовом второго провайдера без своего CB → `resilience/fallback-does-not-fake-success`.
   - **OpenAPI/mapper (`R-RES-OAS-*`):** policy-обёртки на public-методе адаптера, не на сгенерированном клиенте (`openapi-typescript`/`openapi-fetch`) → `resilience/breaker-on-adapter-method`; CB в generic `executeCall<T>` со строкой-параметром системы → `resilience/breaker-on-adapter-method`; mapper generated DTO → domain обязателен, порт возвращает domain-типы → нарушение `R-RES-OAS-X3`.
   - **Health (`R-RES-HC-*`):** per-system `@nestjs/terminus` custom indicator в readiness (`/health/ready`); TTL-кеш ~30s (`{ up, at }` + `Date.now()`); лёгкий probe (`GET /health`/`OPTIONS`), не бизнес-вызов. Probe без кеша → `resilience/cached-health-probe-per-system`. Probe бизнес-операцией → `resilience/cached-health-probe-per-system`.
   - **Async/polling (`R-RES-ASYNC-*`):** polling внешней системы — через `*_task`-таблицу + `@Interval`-poller; `await sleep(...)`-цикл опроса в handler → `resilience/no-long-synchronous-waits`; `sleep > 5s` → `resilience/no-long-synchronous-waits`; на каждый async-вызов — отдельный `timeout()` / `AbortSignal.timeout()` → `resilience/async-calls-need-time-limit`.
   - **Observability (`R-RES-OBS-*`):** prom-client gauges/counters на `onBreak`/`onReset`/`onHalfOpen`, `onFailure`/`onSuccess`, bulkhead `executionSlots`; OTel-span с атрибутами `circuit_breaker.state`, `external.system`; WARN-лог на каждый state-transition CB (system, prev_state, new_state). Отсутствие метрик → `resilience/resilience-state-is-observable`.

4. **Cross-check:** структура out-adapter/порта — `ucp-node-hexagonal-review`; метрики/трейсинг — `ucp-node-observability-review`; idempotency для retry — `ucp-node-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — retry write без `Idempotency-Key` (`resilience/retry-only-when-safe`), shared клиент/CB на несколько систем (`resilience/client-per-external-system`/`resilience/instance-names-match-system`), клиент без timeout (`resilience/timeout-hierarchy`, axios `timeout: 0`), `await sleep(...)`-цикл polling в handler (`resilience/no-long-synchronous-waits`), fallback money `null`/`0`/тихий успех (`R-RES-FB-X1/X2`).
   - **Предупреждение** — CB/policy на сгенерированном клиенте (`resilience/breaker-on-adapter-method`), CB в generic-helper со строкой (`resilience/breaker-on-adapter-method`), самописный CB (`resilience/no-custom-breaker`), retry на 4xx/без backoff (`R-RES-RE-X2/X3`), сторонние авто-retry без CB (`resilience/retry-with-backoff-and-limit`), worker-пул как bulkhead (`resilience/bulkhead-is-semaphore-based`), health без TTL-кеша (`resilience/cached-health-probe-per-system`).
   - **Замечание** — возврат generated DTO из порта (`R-RES-OAS-X3`), probe бизнес-операцией (`resilience/cached-health-probe-per-system`), метрики resilience отсутствуют (`resilience/resilience-state-is-observable`).

## Что не входит

- Структура out-adapter/портов — `ucp-node-hexagonal-review`. Скелет outbound-клиента — `ucp-node-integration-review`.
- Метрики/трейсинг — `ucp-node-observability-review`.

$ARGUMENTS
