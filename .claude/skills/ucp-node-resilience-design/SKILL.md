---
name: ucp-node-resilience-design
lang: node
description: Спроектировать защиту NestJS-сервиса от отказов внешних систем (требования resilience/*) — per-system undici Agent + cockatiel wrap(retry, circuitBreaker, bulkhead, timeout), CountBreaker, ExponentialBackoff, terminus health-check с TTL.
when_to_use: Подключение внешней системы или добавление resilience. Триггеры — «защити вызов X», «circuit breaker для Y», «таймауты/ретраи на Node».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Resilience — проектирование (Node / NestJS + cockatiel + undici + terminus)

Ты проектируешь защиту от отказов по **контракту** `backend/resilience/spec.md` (`R-RES-*`) и
**Node-реализации** `backend/resilience/references/node/implementation.md`.

## Инструкции

1. **Прочитай** требования `node-style/*`. Коды в обосновании, не в коде. Связанные: `backend/hexagonal/node/...` (out-adapter/порт), `backend/resilience/node/...` (скелет клиента), `backend/observability/node/...` (метрики/спаны).

2. **Определи границу** (`R-RES-WHERE-*`): outbound HTTP → полный набор (timeout + CB + bulkhead + опц. retry); internal s2s → timeout + CB; scheduler/outbox-relay → task-queue (`resilience/durable-retry-via-task-queue`); inbound rate-limit → API Gateway / `@nestjs/throttler` только без gateway. Не оборачивай локальные операции (`resilience/no-protection-around-local-operations`).

3. **Произведи код** (на public-методе out-adapter `@Injectable()`, не на сгенерированном клиенте):
   - **Per-system** undici `new Agent({ connections, connectTimeout, headersTimeout, bodyTimeout })` **или** `axios.create(...)` с `maxSockets`; singleton-провайдер c DI-токеном `SBER_CLIENT` (`resilience/client-per-external-system`, `resilience/instance-names-match-system`).
   - **Cockatiel-policy** — `wrap(retry(...), circuitBreaker(...), bulkhead(N), timeout(total, TimeoutStrategy.Aggressive))` — singleton в DI, создаётся один раз, не per-call (`resilience/instance-names-match-system`).
   - **Circuit breaker** — `circuitBreaker(handleAll, { halfOpenAfter: 30_000, breaker: new CountBreaker({ threshold: 0.5, size: 50 }) })`; открыт → `BrokenCircuitError` → маппится в port-исключение (`...SystemUnavailable`) (`R-RES-CB-*`).
   - **Bulkhead** — `bulkhead(maxConcurrent, queueLimit)` per-system, `maxConcurrent ≈ connections × 0.8`, малый `queueLimit` для немедленного `BulkheadRejectedError` (`R-RES-BH-*`).
   - **Retry** — `retry(handleType(SberTransientError), { maxAttempts: 3, backoff: new ExponentialBackoff() })` только при идемпотентности (read-метод или `Idempotency-Key`), не на 4xx (`R-RES-RE-*`). Сторонние авто-retry (`axios-retry`, `got` defaults, RxJS `retry()`) — выключить (`resilience/retry-with-backoff-and-limit`).
   - **Mapper** generated DTO → domain; порт возвращает domain-типы, не DTO (`resilience/mapper-between-client-and-port`).
   - **Health-check** — `@Injectable()` class `<System>HealthIndicator`, TTL-кеш `{ up, at }` ~30s, лёгкий probe (`GET /health`/`OPTIONS`), не бизнес-вызов; регистрируется в readiness `/health/ready` через `@nestjs/terminus` (`R-RES-HC-*`).
   - **Конфиг** — class-validator / zod `<System>ClientConfig` (env-секция `client.<system>.*`); dефолты + per-system override (`R-RES-CFG-*`).

4. **Polling/async** (`R-RES-ASYNC-*`): через task-queue (`*_task`-таблица + `@Interval`-poller), не `setTimeout`/`sleep`-цикл в handler; sleep допустим только при total wait <2s. На каждый async-вызов — отдельный `timeout()` / `AbortSignal.timeout()`.

5. **Observability** (`R-RES-OBS-*`): метрики `prom-client` — `onBreak`/`onReset`/`onHalfOpen` CB → gauges/counters; OTel-span на adapter-методе с атрибутами `circuit_breaker.state`, `external.system`; WARN-лог на каждый state-transition CB (system, prev_state, new_state), не на каждый вызов.

6. **Самопроверка** (чеклист §13 требования `node-style/*`) + предложи `ucp-node-resilience-review`. Скелет клиента целиком — `ucp-node-integration-design`.

## Антипаттерны, которые НЕ генерировать

- Shared `Agent`/`axios.create` на несколько систем (`resilience/client-per-external-system`); клиент без явных timeout/pool (`resilience/timeout-hierarchy`, `resilience/client-per-external-system`); `axios timeout: 0`.
- CB/retry на репозиториях/in-memory (`resilience/no-protection-around-local-operations`, `resilience/no-protection-around-local-operations`); самописный CB на `try/catch` + счётчик (`resilience/no-custom-breaker`); policy пересоздаётся per-call (`resilience/instance-names-match-system`).
- Обёртки на сгенерированном клиенте (`resilience/breaker-on-adapter-method`); CB в generic `executeCall<T>` с именем-строкой (`resilience/breaker-on-adapter-method`); возврат generated DTO из порта (`R-RES-OAS-X3`).
- Retry write без `Idempotency-Key` (`resilience/retry-only-when-safe`); retry на 4xx (`resilience/retry-only-when-safe`); без `ExponentialBackoff` (`resilience/retry-with-backoff-and-limit`); стихийные авто-retry фреймворка/клиента без интеграции с CB (`resilience/retry-with-backoff-and-limit`).
- `bulkhead` через `worker_threads`/piscina (теряется `AsyncLocalStorage`) (`resilience/bulkhead-is-semaphore-based`).
- `await sleep()`-цикл опроса в HTTP-handler (`resilience/no-long-synchronous-waits`); sleep > 5s (`resilience/no-long-synchronous-waits`).
- Fallback `Money(0)`/`null` для money-операции (`resilience/fallback-does-not-fake-success`); fallback тихий «успех» (`resilience/fallback-does-not-fake-success`); fallback → второй провайдер без своего CB (`resilience/fallback-does-not-fake-success`).

После работы скилла — обязательно `ucp-node-resilience-review`.

$ARGUMENTS
