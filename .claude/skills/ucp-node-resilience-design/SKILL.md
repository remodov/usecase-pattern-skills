---
name: ucp-node-resilience-design
lang: node
description: Спроектировать защиту NestJS-сервиса от отказов внешних систем (коды R-RES-*) — per-system undici Agent + cockatiel wrap(retry, circuitBreaker, bulkhead, timeout), CountBreaker, ExponentialBackoff, terminus health-check с TTL.
when_to_use: Подключение внешней системы или добавление resilience. Триггеры — «защити вызов X», «circuit breaker для Y», «таймауты/ретраи на Node».
allowed-tools: Read Glob Grep Write Edit Bash(node*) Bash(npm*) Bash(npx*) Bash(jest*)
---

# Resilience — проектирование (Node / NestJS + cockatiel + undici + terminus)

Ты проектируешь защиту от отказов по **контракту** `backend/resilience/resilience-rules.md` (`R-RES-*`) и
**Node-реализации** `backend/resilience/node/resilience-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Node-style-guide. Коды в обосновании, не в коде. Связанные: `backend/hexagonal/node/...` (out-adapter/порт), `backend/resilience/node/...` (скелет клиента), `backend/observability/node/...` (метрики/спаны).

2. **Определи границу** (`R-RES-WHERE-*`): outbound HTTP → полный набор (timeout + CB + bulkhead + опц. retry); internal s2s → timeout + CB; scheduler/outbox-relay → task-queue (`R-RES-RE-5`); inbound rate-limit → API Gateway / `@nestjs/throttler` только без gateway. Не оборачивай локальные операции (`R-RES-WHERE-X1`).

3. **Произведи код** (на public-методе out-adapter `@Injectable()`, не на сгенерированном клиенте):
   - **Per-system** undici `new Agent({ connections, connectTimeout, headersTimeout, bodyTimeout })` **или** `axios.create(...)` с `maxSockets`; singleton-провайдер c DI-токеном `SBER_CLIENT` (`R-RES-ISO-1`, `R-RES-ISO-3`).
   - **Cockatiel-policy** — `wrap(retry(...), circuitBreaker(...), bulkhead(N), timeout(total, TimeoutStrategy.Aggressive))` — singleton в DI, создаётся один раз, не per-call (`R-RES-CB-X3`).
   - **Circuit breaker** — `circuitBreaker(handleAll, { halfOpenAfter: 30_000, breaker: new CountBreaker({ threshold: 0.5, size: 50 }) })`; открыт → `BrokenCircuitError` → маппится в port-исключение (`...SystemUnavailable`) (`R-RES-CB-*`).
   - **Bulkhead** — `bulkhead(maxConcurrent, queueLimit)` per-system, `maxConcurrent ≈ connections × 0.8`, малый `queueLimit` для немедленного `BulkheadRejectedError` (`R-RES-BH-*`).
   - **Retry** — `retry(handleType(SberTransientError), { maxAttempts: 3, backoff: new ExponentialBackoff() })` только при идемпотентности (read-метод или `Idempotency-Key`), не на 4xx (`R-RES-RE-*`). Сторонние авто-retry (`axios-retry`, `got` defaults, RxJS `retry()`) — выключить (`R-RES-RE-X4`).
   - **Mapper** generated DTO → domain; порт возвращает domain-типы, не DTO (`R-RES-OAS-4`).
   - **Health-check** — `@Injectable()` class `<System>HealthIndicator`, TTL-кеш `{ up, at }` ~30s, лёгкий probe (`GET /health`/`OPTIONS`), не бизнес-вызов; регистрируется в readiness `/health/ready` через `@nestjs/terminus` (`R-RES-HC-*`).
   - **Конфиг** — class-validator / zod `<System>ClientConfig` (env-секция `client.<system>.*`); dефолты + per-system override (`R-RES-CFG-*`).

4. **Polling/async** (`R-RES-ASYNC-*`): через task-queue (`*_task`-таблица + `@Interval`-poller), не `setTimeout`/`sleep`-цикл в handler; sleep допустим только при total wait <2s. На каждый async-вызов — отдельный `timeout()` / `AbortSignal.timeout()`.

5. **Observability** (`R-RES-OBS-*`): метрики `prom-client` — `onBreak`/`onReset`/`onHalfOpen` CB → gauges/counters; OTel-span на adapter-методе с атрибутами `circuit_breaker.state`, `external.system`; WARN-лог на каждый state-transition CB (system, prev_state, new_state), не на каждый вызов.

6. **Самопроверка** (чеклист §13 Node-style-guide) + предложи `ucp-node-resilience-review`. Скелет клиента целиком — `ucp-node-integration-design`.

## Антипаттерны, которые НЕ генерировать

- Shared `Agent`/`axios.create` на несколько систем (`R-RES-ISO-X1`); клиент без явных timeout/pool (`R-RES-TO-X1`, `R-RES-ISO-X2`); `axios timeout: 0`.
- CB/retry на репозиториях/in-memory (`R-RES-WHERE-X1`, `R-RES-CB-X1`); самописный CB на `try/catch` + счётчик (`R-RES-CB-X2`); policy пересоздаётся per-call (`R-RES-CB-X3`).
- Обёртки на сгенерированном клиенте (`R-RES-OAS-X1`); CB в generic `executeCall<T>` с именем-строкой (`R-RES-OAS-X2`); возврат generated DTO из порта (`R-RES-OAS-X3`).
- Retry write без `Idempotency-Key` (`R-RES-RE-X1`); retry на 4xx (`R-RES-RE-X2`); без `ExponentialBackoff` (`R-RES-RE-X3`); стихийные авто-retry фреймворка/клиента без интеграции с CB (`R-RES-RE-X4`).
- `bulkhead` через `worker_threads`/piscina (теряется `AsyncLocalStorage`) (`R-RES-BH-X1`).
- `await sleep()`-цикл опроса в HTTP-handler (`R-RES-ASYNC-X1`); sleep > 5s (`R-RES-ASYNC-X2`).
- Fallback `Money(0)`/`null` для money-операции (`R-RES-FB-X1`); fallback тихий «успех» (`R-RES-FB-X2`); fallback → второй провайдер без своего CB (`R-RES-FB-X3`).

После работы скилла — обязательно `ucp-node-resilience-review`.

$ARGUMENTS
