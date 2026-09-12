# Resilience — реализация на Node (cockatiel + undici/axios + terminus)

Реализация язык-нейтрального контракта `../spec.md` (`R-RES-*`) на Node/NestJS. Коды общие с Java;
меняется реализация: вместо Resilience4j-аннотаций — **policy-композиция cockatiel** вокруг public-методов
out-adapter (opossum — зрелая альтернатива для одного только circuit breaker; cockatiel предпочтителен — даёт
весь набор как композируемые policy):

| Защита | Java (Resilience4j) | Node |
|---|---|---|
| timeout | OkHttp call/read/connect | undici `connectTimeout/headersTimeout/bodyTimeout` (axios `timeout`) + cockatiel `timeout()` |
| circuit breaker | `@CircuitBreaker` | cockatiel `circuitBreaker()` (`CountBreaker`); альтернатива — opossum |
| retry | `@Retry` | cockatiel `retry()` + `ExponentialBackoff` |
| bulkhead | `@Bulkhead(SEMAPHORE)` | cockatiel `bulkhead(limit)` — счётчик в event loop, semaphore-семантика |
| time limiter | `@TimeLimiter` | cockatiel `timeout()` / `AbortSignal.timeout()` |
| health | `HealthIndicator` | `@nestjs/terminus` custom indicator с TTL-кешем |

## 1. Где какая защита (`R-RES-WHERE-*`)

`resilience/outbound-calls-fully-protected` — outbound HTTP к внешним системам: полный набор (timeout + CB + bulkhead + опц. retry).
`resilience/outbound-calls-fully-protected` — internal s2s: timeout + CB. `resilience/durable-retry-via-task-queue` — schedulers/outbox-relay: durable retry через
**task-queue** (PG-таблица), не in-memory (`resilience/durable-retry-via-task-queue`). `resilience/inbound-rate-limiting-at-edge` — inbound rate limit — на API Gateway;
`@nestjs/throttler` — только если gateway недоступен. `resilience/no-protection-around-local-operations` — CB/retry вокруг локальных операций
(репозиторий, in-memory) — нет транзиентов, любой сбой реален.

## 2. Per-system isolation (`R-RES-ISO-*`)

`resilience/client-per-external-system` — на каждую внешнюю систему — **отдельный HTTP-клиент**: undici
`new Agent({ connections, connectTimeout, headersTimeout, bodyTimeout })` либо `axios.create({...})` с собственным
`http(s)Agent({ maxSockets })`; плюс собственные CB/bulkhead/retry-policy. `resilience/pool-sizes-are-balanced` — pool sizing per-system:
`connections ≈ maxConcurrent × 1.2`; суммарно ≤ половина пула БД. `resilience/instance-names-match-system` — единое имя системы (`sber`,
`receipt`) для провайдера клиента, policy-набора и health-индикатора (DI-токен `SBER_CLIENT` и т.п.).

```ts
// PREFER: per-system провайдер
{ provide: SBER_CLIENT, useFactory: (cfg: SberClientConfig) =>
    new Agent({ connections: 10, connectTimeout: 1_000, headersTimeout: 2_000, bodyTimeout: 5_000 }) }
// AVOID: глобальный fetch / один axios-дефолт на все системы — зависание одной съедает коннекты других
```

`resilience/client-per-external-system` — один shared клиент/Agent на несколько систем. `resilience/client-per-external-system` — клиент без явных pool/timeout
(глобальные дефолты undici/axios, shared-семантика; у axios дефолтный `timeout: 0` = ∞).

## 3. Timeouts (`R-RES-TO-*`)

`resilience/timeout-hierarchy` — иерархия `connect < read < total`: undici `connectTimeout < headersTimeout ≤ bodyTimeout` + общий
cockatiel `timeout(total)` вокруг вызова (для axios: `timeout` = read-уровень, total — policy). `resilience/timeout-hierarchy` —
per-system через типизированный конфиг (`SberClientConfig`, zod/class-validator, `nest-bootstrap/config-validated-at-startup`); отклонения от
типовых — комментарием с обоснованием. `resilience/respect-remaining-time-budget` — уважать оставшийся TimeBudget при наличии `traceparent`:
client-side timeout = `min(callTimeout, remainingBudget - 100ms)`.

`resilience/timeout-hierarchy` — клиент без timeout (axios `timeout: 0`, fetch без `AbortSignal`) — зависание = таска навсегда.
`resilience/timeout-hierarchy` — total-timeout меньше read — внутреннее противоречие. `resilience/no-long-synchronous-waits` — read > 60s в синхронном
HTTP-handler — в task-queue.

## 4. Circuit Breaker (`R-RES-CB-*`)

`resilience/breaker-on-adapter-method` — CB оборачивает **public-метод out-adapter**, не сгенерированный клиент, не handler, не репозиторий.
`resilience/breaker-window-and-thresholds` — count-based окно: `new CountBreaker({ threshold: 0.5, size: 50 })`, минимум вызовов ~10.
`resilience/breaker-window-and-thresholds` — failure rate 50% (для платежей 30% — «лучше быстро открыть»). `resilience/breaker-window-and-thresholds` — `halfOpenAfter: 30_000`,
в half-open ~3 пробных вызова: успех → closed, иначе назад в open. `resilience/breaker-window-and-thresholds` — slow-call — отдельной
timeout-policy с порогом ≈ read/2, ошибки которой считает CB.

```ts
@Injectable()
export class SberAdapter implements PaymentPort {
  private readonly policy = wrap(
    retry(handleType(SberTransientError), { maxAttempts: 3, backoff: new ExponentialBackoff() }),
    circuitBreaker(handleAll, { halfOpenAfter: 30_000, breaker: new CountBreaker({ threshold: 0.5, size: 50 }) }),
    bulkhead(8),
    timeout(5_000, TimeoutStrategy.Aggressive),
  );

  async findPayment(ref: PaymentRef): Promise<Payment> {       // read → retry допустим (R-RES-RE-1)
    try {
      const resp = await this.policy.execute(() => this.client.request({ path: `/payments/${ref.id}`, method: 'GET' }));
      return toDomain(await resp.body.json());                  // mapper DTO → domain (R-RES-OAS-4)
    } catch (e) {
      if (e instanceof BrokenCircuitError) throw PaymentPortError.systemUnavailable('sber', e);
      throw PaymentPortError.from(e);
    }
  }
}
```

`resilience/open-breaker-maps-to-domain-error` — при open CB cockatiel кидает `BrokenCircuitError` (opossum — `EOPENBREAKER`); адаптер мапит в
port-исключение (`...SystemUnavailable`), exception filter — в `503`/`409` по UC. `resilience/no-protection-around-local-operations` — CB на
репозитории/in-memory. `resilience/no-custom-breaker` — самописный CB на `try/catch` + счётчик (bug-source; cockatiel/opossum
отлажены, дают события для метрик). `resilience/instance-names-match-system` — общий CB-инстанс/`handleAll`-policy на разные системы
(policy создаётся per-system и живёт как singleton в DI, не пересоздаётся на вызов).

## 5. Retry (`R-RES-RE-*`)

`resilience/retry-only-when-safe` — `retry()` **только** при идемпотентности: read-метод **или** команда с `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`).
`resilience/retry-with-backoff-and-limit`/`resilience/retry-with-backoff-and-limit` — `new ExponentialBackoff()` (jitter встроен), `maxAttempts: 3` (макс 5, включая первую),
`handleType(...)` только на транзиентные (timeout/5xx/`ECONNREFUSED`/`UND_ERR_*`). `resilience/durable-retry-via-task-queue`/`resilience/durable-retry-via-task-queue` —
долгий retry (>30s, переживание рестарта) — task-queue: таблица `*_task`
(`status`/`retry_count`/`next_attempt_at`/`last_error`), `@Interval`-poller по
`status='IN_PROGRESS' AND next_attempt_at <= now()`, после N неудач — `FAILED` + alert.

```ts
// AVOID: axios-retry/interceptor с ретраем «на любой ошибке» поверх POST без Idempotency-Key
axiosRetry(client, { retries: 3 });            // двойной платёж на 5xx + не согласован с CB
// PREFER: cockatiel-композиция (retry снаружи CB), handleType только транзиентных, метод идемпотентен
```

`resilience/retry-only-when-safe` — retry write-метода без `Idempotency-Key` (5xx = «может, дошло» → двойная операция). `resilience/retry-only-when-safe` —
retry на 4xx (контрактная ошибка). `resilience/retry-with-backoff-and-limit` — retry без exponential backoff (`ConstantBackoff(0)` бьёт пачкой
по лежачей системе). `resilience/retry-with-backoff-and-limit` — стихийные retry-механизмы фреймворка/клиента (axios-retry, `got` retry-дефолты,
RxJS `retry()` в Nest `HttpService`) без интеграции с CB/bulkhead — единая cockatiel-композиция.

## 6. Bulkhead (`R-RES-BH-*`)

`resilience/bulkhead-is-semaphore-based`/`resilience/bulkhead-is-semaphore-based` — cockatiel `bulkhead(maxConcurrent, queueLimit)` per-system, **отдельно** от
connection-pool: pool ограничивает TCP-соединения, bulkhead — одновременные вызовы. Работает в текущем async-контексте —
`AsyncLocalStorage` (trace/MDC) не теряется; это и есть semaphore-семантика (отдельных тредов в Node нет).
`resilience/bulkhead-is-semaphore-based` — `maxConcurrent ≈ connections × 0.8` (срабатывает раньше исчерпания пула); `queueLimit` маленький
(0–N) — немедленный `BulkheadRejectedError` лучше бесконечной очереди promise'ов.

`resilience/bulkhead-is-semaphore-based` — выносить outbound I/O в `worker_threads`/piscina-пул «как bulkhead» — теряется `AsyncLocalStorage`,
лишние треды для I/O-bound нагрузки; счётчика-bulkhead достаточно.

## 7. Fallback (`R-RES-FB-*`)

`resilience/fallback-does-not-fake-success` — fallback допустим для деградации (кеш/частичный ответ/дефолт), не для money-операций. `resilience/fallback-does-not-fake-success` —
явная обработка (`catch` на `BrokenCircuitError`/`TaskCancelledError`/`BulkheadRejectedError` либо
`fallback(policy, value)` cockatiel) с осознанным результатом того же типа.

`resilience/fallback-does-not-fake-success` — fallback `Money(0)`/`null` для money-операции (бизнес-баг). `resilience/fallback-does-not-fake-success` — fallback, тихо
возвращающий «успех». `resilience/fallback-does-not-fake-success` — fallback с вызовом второго провайдера без своего CB (cascading failure).

## 8. Конфигурация (`R-RES-CFG-*`)

`resilience/declarative-configuration`/`resilience/declarative-configuration` — параметры CB/retry/timeout/bulkhead — через типизированный конфиг
(`client.<system>`-секции env, zod/class-validator), policy собирается фабрикой из конфига, не литералами по коду;
дефолты + per-system override. `resilience/instance-names-match-system` — имена инстансов/DI-токенов = имя системы. `resilience/declarative-configuration` — скрытая
программная конфигурация (магические числа в `wrap(...)`) без причины.

## 9. Связка с OpenAPI generator (`R-RES-OAS-*`)

`resilience/breaker-on-adapter-method` — policy-обёртки — на public-методе out-adapter, не на сгенерированном клиенте, не в generic
`executeCall<T>`-helper. `resilience/client-generated-from-contract` — для нового кода клиент/типы генерируются из OpenAPI-спеки внешней системы:
`openapi-typescript` (+ `openapi-fetch`) или openapi-generator `typescript-axios`. `resilience/client-generated-from-contract` — спека хранится в
`src/adapters/out/<system>/openapi/<system>.openapi.yaml`; codegen — в build-артефакты (`generated/`, в
`.gitignore`), регенерация — на build-шаге. `resilience/mapper-between-client-and-port` — между сгенерированным клиентом и портом из `core/` —
**mapper** (generated DTO → domain); адаптер не пробрасывает DTO наверх.

`resilience/breaker-on-adapter-method` — обёртки на сгенерированном клиенте (регенерация затрёт). `resilience/breaker-on-adapter-method` — CB в `executeCall<T>` с
именем системы строкой-параметром — теряется compile-time связь policy↔система, опечатка всплывает на runtime.
`R-RES-OAS-X3` — возврат generated DTO из port-метода.

## 10. Health checks (`R-RES-HC-*`)

`resilience/cached-health-probe-per-system` — на каждую систему — custom indicator `@nestjs/terminus`, отражается в readiness
(`/health/ready`). `resilience/cached-health-probe-per-system` — **кеш TTL ~30s** внутри индикатора (`{ result, at }` + сравнение с `Date.now()`),
не probe на каждый запрос. `resilience/cached-health-probe-per-system` — лёгкий probe (`GET /health`/`OPTIONS`), не бизнес-вызов. `resilience/external-systems-affect-readiness` —
readiness учитывает внешние системы, liveness — нет.

```ts
@Injectable()
export class SberHealthIndicator {
  private cached?: { up: boolean; at: number };
  async isHealthy(): Promise<HealthIndicatorResult> {
    if (!this.cached || Date.now() - this.cached.at > 30_000)
      this.cached = { up: await this.probe(), at: Date.now() };       // GET /health, не бизнес-вызов
    return { sber: { status: this.cached.up ? 'up' : 'down' } };
  }
}
```

`resilience/cached-health-probe-per-system` — sync-probe без кеша на каждый `/health` (k8s-probes каждые 5s = DDoS внешней системы).
`resilience/cached-health-probe-per-system` — probe бизнес-операцией (`registerTestOrder`).

## 11. Async и polling (`R-RES-ASYNC-*`)

`resilience/async-calls-need-time-limit` — polling внешней системы — через **task-queue** (`*_task` + `@Interval`-poller), не
`setTimeout`/`sleep`-цикл в handler. `resilience/no-long-synchronous-waits` — `sleep` в адаптере допустим только при total wait <2s
(короткий фиксированный backoff). `resilience/async-calls-need-time-limit` — на каждый async-вызов — отдельный time-limit
(cockatiel `timeout()` / `AbortSignal.timeout()`), retry/bulkhead/CB его не заменяют.

`resilience/no-long-synchronous-waits` — `await sleep(...)`-цикл опроса в HTTP-handler (держит запрос, копит pending-промисы, под
нагрузкой кладёт event loop по памяти/сокетам). `resilience/no-long-synchronous-waits` — любой sleep > 5s — запах «должно быть task-queue».

## 12. Observability (`R-RES-OBS-*`)

`resilience/resilience-state-is-observable` — метрики через `prom-client`: cockatiel `onBreak`/`onReset`/`onHalfOpen`, `onFailure`/`onSuccess`,
bulkhead `executionSlots` → gauges/counters (opossum отдаёт `status`-снапшоты из коробки). `resilience/resilience-state-is-observable` —
OTel-span на adapter-методе с атрибутами `circuit_breaker.state`, `external.system`. `resilience/resilience-state-is-observable` — структурный
лог (WARN) на каждый state-transition CB (system, prev_state, new_state), не на каждый успешный вызов.

`resilience/resilience-state-is-observable` — отсутствие resilience-метрик (SRE не увидит залипший half-open).

## 13. Чеклист подключения к новому сервису (Node/NestJS)

1. На каждую внешнюю систему — отдельный undici `Agent`/axios-инстанс + cockatiel-policy (singleton в DI) +
   per-system конфиг с единым именем.
2. Timeout: connect < headers/read < total (`timeout()`-policy); никаких клиентов с `timeout: 0`.
3. Композиция `wrap(retry, circuitBreaker, bulkhead, timeout)` на public-методе адаптера; CB — `CountBreaker`,
   open → port-исключение → 503/409.
4. Retry только при идемпотентности, `ExponentialBackoff`, не на 4xx; сторонние авто-retry (axios-retry, got)
   выключены; долгий retry — task-queue.
5. Bulkhead — cockatiel-счётчик, не worker-пул; sizing < pool; queueLimit маленький.
6. Fallback — не для money, не «тихий успех»; mapper DTO → domain, порт возвращает domain-типы.
7. Terminus-индикатор per-system с TTL-кешем; polling — task-queue, не sleep-цикл; метрики + WARN на CB-переходы.
