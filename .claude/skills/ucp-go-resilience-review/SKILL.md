---
name: ucp-go-resilience-review
lang: go
description: Ревью защиты Go-сервиса (net/http + chi) от отказов внешних систем по UCP (требования resilience/*) — per-system *http.Client + gobreaker + semaphore + retry-go, timeout-иерархия, health TTL-кеш, task-queue polling, метрики promauto.
when_to_use: Изменения в adapters/out/**/*.go, *config.go с OutboundConfig, health-индикаторах, scheduler polling или любом коде с gobreaker/retry.Do/semaphore.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Resilience (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/resilience/spec.md`
(`R-RES-*`, коды едины с Java/Python) и его **Go-реализации** `backend/resilience/references/go/implementation.md`.
Помни парадигму: в Go ошибки — **значения**, не исключения; port-specific ошибки через `errors.As`/`errors.Is`;
`gobreaker.ErrOpenState` надо явно фильтровать в `retry.RetryIf`; semaphore работает в горутине хендлера, не создаёт отдельного пула.

## Зависимости

- **`.claude/docs/backend/resilience/spec.md`** — общий контракт (`R-RES-WHERE-*`/`ISO-*`/`TO-*`/`CB-*`/`RE-*`/`BH-*`/`FB-*`/`CFG-*`/`OAS-*`/`HC-*`/`ASYNC-*`/`OBS-*`).
- **`.claude/docs/backend/resilience/references/go/implementation.md`** — Go-реализация (`*http.Client`+`*http.Transport`, `gobreaker.CircuitBreaker`, `semaphore.Weighted`, `retry.Do`+`retry.RetryIf`, `capTimeout`, `promauto`, OTel).
- Парные: `backend/hexagonal/go/...` (out-adapter/порт), `backend/observability/go/...` (метрики/спаны), `backend/auth-patterns/spec.md` (`auth-patterns/money-commands-need-idempotency-key` idempotency для retry), `backend/error-handling/go/...` (port-specific ошибки через `errors.As`).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй конкретные коды (`resilience/instance-names-match-system`, `resilience/retry-only-when-safe`), не только группу.

2. **Скоп.**
   - `adapters/out/**/*.go` — адаптеры, клиенты, health-индикаторы, mapper'ы.
   - `**/config.go` / `OutboundConfig` / `*ClientConfig` — конфиги таймаутов и пулов.
   - `scheduler/**/*.go` — polling-планировщики (task-queue vs sleep-цикл).
   - `git diff` на изменённые `.go`.
   - **`Grep`**: `http.DefaultClient` (shared transport), `&http.Client{}` без `Timeout` (дефолт ∞), `gobreaker.NewCircuitBreaker` (проверить `Name` и `ReadyToTrip`), `retry.Do` (проверить `RetryIf`), `time.Sleep` в хендлерах (polling-запах).

3. **Прогон по подгруппам.**

   ### `R-RES-WHERE-*`
   - Outbound HTTP к внешним системам — полный набор timeout + CB + bulkhead + (опц.) retry (`resilience/outbound-calls-fully-protected`).
   - Internal s2s — timeout + CB (`resilience/outbound-calls-fully-protected`).
   - Scheduler/outbox-relay — task-queue, не in-memory (`resilience/durable-retry-via-task-queue`).
   - `gobreaker`/`retry.Do` вокруг репозитория/SQL/in-memory → `resilience/no-protection-around-local-operations`.

   ### `R-RES-ISO-*`
   - Каждая система — отдельный `*http.Client` со своим `*http.Transport`, `gobreaker.CircuitBreaker`, `semaphore.Weighted`, конфигом (`resilience/client-per-external-system`).
   - `MaxIdleConnsPerHost ≈ maxConcurrent × 1.2`, суммарно ≤ пул БД / 2 (`resilience/pool-sizes-are-balanced`).
   - Единое имя системы (`sber`, `receipt`, `insurance`) в `gobreaker.Settings.Name`, метриках, логах (`resilience/instance-names-match-system`).
   - `http.DefaultClient` или один `*http.Client` на несколько систем → `resilience/client-per-external-system`.
   - `&http.Client{}` без явного `Transport` — shared `http.DefaultTransport` → `resilience/client-per-external-system`.

   ### `R-RES-TO-*`
   - Иерархия: `Transport.DialContext` (connect) < `Transport.ResponseHeaderTimeout` (read) < `http.Client.Timeout` (call) (`resilience/timeout-hierarchy`).
   - Per-system конфиг через `envconfig`-теги (`SberClientConfig{ConnectTimeout, ReadTimeout, CallTimeout}`) (`resilience/timeout-hierarchy`).
   - `capTimeout` уважает входящий дедлайн контекста: `min(callTimeout, remainingBudget - 100ms)` (`resilience/respect-remaining-time-budget`).
   - `&http.Client{}` без `Timeout` и без `Transport` с `DialContext` → `resilience/timeout-hierarchy`.
   - `CallTimeout < ReadTimeout` — `http.Client.Timeout` срабатывает раньше `ResponseHeaderTimeout` → `resilience/timeout-hierarchy`.
   - `ReadTimeout > 60s` в синхронном хендлере → task-queue → `resilience/no-long-synchronous-waits`.

   ### `R-RES-CB-*`
   - `gobreaker.CircuitBreaker` на **public-методе** структуры-адаптера, не на `*http.Client`, не на хендлере, не на репозитории (`resilience/breaker-on-adapter-method`).
   - Count-based окно 50, min requests 10, failure rate ≥50% (платёжные ≥30%), open 30s, half-open 3 пробных (`R-RES-CB-2..5`).
   - `gobreaker.ErrOpenState`/`ErrTooManyRequests` → port-specific `*SystemUnavailableError` (`resilience/open-breaker-maps-to-domain-error`).
   - `gobreaker` вокруг репозитория/SQL → `resilience/no-protection-around-local-operations`.
   - Самописный CB на `sync.Mutex` + счётчик → `resilience/no-custom-breaker`.
   - `Name: "default"` или одно имя для нескольких систем — делят state → `resilience/instance-names-match-system`.

   ### `R-RES-RE-*`
   - `retry.Do` только при идемпотентности: read-метод (`GetOrderStatus`) или write с `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`) (`resilience/retry-only-when-safe`).
   - `retry.BackOffDelay`, max 3 попытки (≤5 включая первую), `retry.Context(ctx)` (`R-RES-RE-2/3`).
   - Долгий retry (>30s) / durable → task-queue (`*_task` таблица) (`R-RES-RE-4/5`).
   - `retry.Do` на write-методе без `Idempotency-Key` → двойная операция → `resilience/retry-only-when-safe`.
   - Retry на 4xx — контрактная ошибка, повтор не поможет → `resilience/retry-only-when-safe`.
   - `retry.FixedDelay` без экспоненциального роста → бьёт пачкой по лежащей системе → `resilience/retry-with-backoff-and-limit`.
   - `retry.Do` без `retry.RetryIf` — ретраит `gobreaker.ErrOpenState` и 4xx → `resilience/retry-with-backoff-and-limit`.

   ### `R-RES-BH-*`
   - `semaphore.NewWeighted(maxConcurrent)` per-system отдельно от HTTP connection pool (`R-RES-BH-1/2`).
   - `maxConcurrent ≈ MaxIdleConnsPerHost × 0.8` — срабатывает раньше исчерпания пула (`resilience/bulkhead-is-semaphore-based`).
   - `sem.Acquire(ctx, 1)` до вызова `breaker.Execute` — контекст и OTel-трейс не теряются.
   - `errgroup` с фиксированным пулом горутин как bulkhead → теряется `context.Context`/OTel без явного проброса → `resilience/bulkhead-is-semaphore-based`.

   ### `R-RES-FB-*`
   - Fallback через `errors.As` в осознанной точке (кешированный результат, частичный ответ, разумный дефолт) (`R-RES-FB-1/2`).
   - `Money{Amount: 0}` как fallback для money-операций → бизнес-баг → `resilience/fallback-does-not-fake-success`.
   - `return result, nil` при фактической ошибке — тихий «успех» → `resilience/fallback-does-not-fake-success`.
   - Fallback во второй провайдер без собственного `gobreaker` на второй вызов → cascading failure → `resilience/fallback-does-not-fake-success`.

   ### `R-RES-OAS-*`
   - `gobreaker`/`retry.Do`/`sem.Acquire` — на public-методе структуры-адаптера, не на сгенерированном клиенте → `resilience/breaker-on-adapter-method`.
   - Для новых систем клиент генерируется из OpenAPI-спеки (oapi-codegen), спека в `adapters/out/<system>/openapi/`, codegen в `internal/generated/` → `resilience/client-generated-from-contract`.
   - Явный mapper generated DTO → domain-тип; port возвращает domain, не generated struct → `resilience/mapper-between-client-and-port`.
   - `gobreaker` встроен в сгенерированный клиент — регенерация затрёт → `resilience/breaker-on-adapter-method`.
   - `PaymentPort.Register` возвращает `generated.RegisterResponse` — domain port раскрывает transport-DTO → `R-RES-OAS-X3`.

   ### `R-RES-HC-*`
   - На каждую систему — отдельный health-индикатор в `/health/ready` (`resilience/cached-health-probe-per-system`).
   - TTL-кеш ~30s: `sync.Mutex` + `lastCheck time.Time` + `lastOK bool`; не ходить во внешнюю систему на каждый K8s-пинг (`resilience/cached-health-probe-per-system`).
   - Лёгкий probe: `GET /health` или `HEAD /` с `context.WithTimeout(ctx, 3*time.Second)` (`resilience/cached-health-probe-per-system`).
   - Readiness учитывает внешние системы, liveness — нет (`resilience/external-systems-affect-readiness`).
   - Probe без TTL-кеша → K8s-пробы каждые 5s = DDoS внешней системы → `resilience/cached-health-probe-per-system`.
   - Probe бизнес-операцией (`registerTestOrder`) — изменяет состояние, плодит мусорные данные → `resilience/cached-health-probe-per-system`.

   ### `R-RES-ASYNC-*`
   - Polling внешней системы — через task-queue (`*_task` таблица + ticker-планировщик), не `time.Sleep`-цикл в горутине хендлера (`resilience/async-calls-need-time-limit`).
   - `time.Sleep` в адаптере допустим только при total wait <2s (короткий transient backoff) (`resilience/no-long-synchronous-waits`).
   - Для async outbound (`goroutine` + channel) — `context.WithTimeout` обязателен (`resilience/async-calls-need-time-limit`).
   - `time.Sleep`-цикл с опросом в HTTP-хендлере или в горутине из него → исчерпывает goroutine-пул → `resilience/no-long-synchronous-waits`.
   - `time.Sleep(d)` с `d > 5s` → запах «должно быть task-queue» → `resilience/no-long-synchronous-waits`.

   ### `R-RES-OBS-*`
   - `promauto`: `circuit_breaker_state{system}` (Gauge), `retry_attempts_total{system,outcome}` (Counter), `bulkhead_rejected_total{system}` (Counter) (`resilience/resilience-state-is-observable`).
   - OTel-span на adapter-методе: атрибуты `external.system`, `circuit_breaker.state`; `span.RecordError` + `span.SetStatus(codes.Error, ...)` (`resilience/resilience-state-is-observable`).
   - WARN-лог на каждый state-transition CB в `OnStateChange` callback'е `gobreaker.Settings` (system, prev_state, new_state) (`resilience/resilience-state-is-observable`).
   - Отключение resilience-метрик без причины → SRE не увидит залипший half-open → `resilience/resilience-state-is-observable`.

4. **Cross-check:** retry write без ключа → `auth-patterns/money-commands-need-idempotency-key` + `resilience/retry-only-when-safe`; port-specific ошибки от CB → `error-handling/integration-exception-names-system` (`errors.As` + `Kind() Integration`); метрики/трейсинг → `ucp-go-observability-review`; структура out-adapter → `ucp-go-hexagonal-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — retry write без `Idempotency-Key` (`resilience/retry-only-when-safe`), `http.DefaultClient`/shared `*http.Client` (`resilience/client-per-external-system`), нет `Timeout` в `http.Client` (`resilience/timeout-hierarchy`), `time.Sleep`-цикл polling в хендлере (`resilience/no-long-synchronous-waits`), fallback `Money{0}` (`resilience/fallback-does-not-fake-success`), тихий `return result, nil` при ошибке (`resilience/fallback-does-not-fake-success`), `gobreaker` на репозитории (`resilience/no-protection-around-local-operations`/`resilience/no-protection-around-local-operations`).
   - **Предупреждение** — `gobreaker` на сгенерированном клиенте (`resilience/breaker-on-adapter-method`), самописный CB (`resilience/no-custom-breaker`), shared CB-state (`resilience/instance-names-match-system`), retry на 4xx (`resilience/retry-only-when-safe`), `FixedDelay` без backoff (`resilience/retry-with-backoff-and-limit`), `retry.Do` без `RetryIf` (`resilience/retry-with-backoff-and-limit`), `errgroup`-bulkhead (`resilience/bulkhead-is-semaphore-based`), health без TTL-кеша (`resilience/cached-health-probe-per-system`).
   - **Замечание** — port возвращает generated DTO (`R-RES-OAS-X3`), метрики resilience отключены (`resilience/resilience-state-is-observable`), probe бизнес-операцией (`resilience/cached-health-probe-per-system`), fallback во второй провайдер без CB (`resilience/fallback-does-not-fake-success`).

## Что не входит

- Структура out-adapter/портов — `ucp-go-hexagonal-review`. Скелет outbound-клиента — `ucp-go-integration-review`.
- Метрики/трейсинг — `ucp-go-observability-review`.
- Port-specific ошибки, `errors.As`, `Kind`-маркер — `ucp-go-error-handling-review`.

$ARGUMENTS
