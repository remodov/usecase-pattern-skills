---
name: ucp-go-resilience-review
lang: go
description: Ревью защиты Go-сервиса (net/http + chi) от отказов внешних систем по UCP (коды R-RES-*) — per-system *http.Client + gobreaker + semaphore + retry-go, timeout-иерархия, health TTL-кеш, task-queue polling, метрики promauto.
when_to_use: Изменения в adapters/out/**/*.go, *config.go с OutboundConfig, health-индикаторах, scheduler polling или любом коде с gobreaker/retry.Do/semaphore.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Resilience (Go / net/http + chi)

Ты ревьюишь Go-сервис на соответствие **общему контракту** `backend/resilience/resilience-rules.md`
(`R-RES-*`, коды едины с Java/Python) и его **Go-реализации** `backend/resilience/go/resilience-style-guide.md`.
Помни парадигму: в Go ошибки — **значения**, не исключения; port-specific ошибки через `errors.As`/`errors.Is`;
`gobreaker.ErrOpenState` надо явно фильтровать в `retry.RetryIf`; semaphore работает в горутине хендлера, не создаёт отдельного пула.

## Зависимости

- **`.claude/docs/backend/resilience/resilience-rules.md`** — общий контракт (`R-RES-WHERE-*`/`ISO-*`/`TO-*`/`CB-*`/`RE-*`/`BH-*`/`FB-*`/`CFG-*`/`OAS-*`/`HC-*`/`ASYNC-*`/`OBS-*`).
- **`.claude/docs/backend/resilience/go/resilience-style-guide.md`** — Go-реализация (`*http.Client`+`*http.Transport`, `gobreaker.CircuitBreaker`, `semaphore.Weighted`, `retry.Do`+`retry.RetryIf`, `capTimeout`, `promauto`, OTel).
- Парные: `backend/hexagonal/go/...` (out-adapter/порт), `backend/observability/go/...` (метрики/спаны), `backend/auth-patterns/auth-patterns-rules.md` (`AUTH-19` idempotency для retry), `backend/error-handling/go/...` (port-specific ошибки через `errors.As`).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй конкретные коды (`R-RES-CB-X3`, `R-RES-RE-X1`), не только группу.

2. **Скоп.**
   - `adapters/out/**/*.go` — адаптеры, клиенты, health-индикаторы, mapper'ы.
   - `**/config.go` / `OutboundConfig` / `*ClientConfig` — конфиги таймаутов и пулов.
   - `scheduler/**/*.go` — polling-планировщики (task-queue vs sleep-цикл).
   - `git diff` на изменённые `.go`.
   - **`Grep`**: `http.DefaultClient` (shared transport), `&http.Client{}` без `Timeout` (дефолт ∞), `gobreaker.NewCircuitBreaker` (проверить `Name` и `ReadyToTrip`), `retry.Do` (проверить `RetryIf`), `time.Sleep` в хендлерах (polling-запах).

3. **Прогон по подгруппам.**

   ### `R-RES-WHERE-*`
   - Outbound HTTP к внешним системам — полный набор timeout + CB + bulkhead + (опц.) retry (`R-RES-WHERE-1`).
   - Internal s2s — timeout + CB (`R-RES-WHERE-2`).
   - Scheduler/outbox-relay — task-queue, не in-memory (`R-RES-WHERE-3`).
   - `gobreaker`/`retry.Do` вокруг репозитория/SQL/in-memory → `R-RES-WHERE-X1`.

   ### `R-RES-ISO-*`
   - Каждая система — отдельный `*http.Client` со своим `*http.Transport`, `gobreaker.CircuitBreaker`, `semaphore.Weighted`, конфигом (`R-RES-ISO-1`).
   - `MaxIdleConnsPerHost ≈ maxConcurrent × 1.2`, суммарно ≤ пул БД / 2 (`R-RES-ISO-2`).
   - Единое имя системы (`sber`, `receipt`, `insurance`) в `gobreaker.Settings.Name`, метриках, логах (`R-RES-ISO-3`).
   - `http.DefaultClient` или один `*http.Client` на несколько систем → `R-RES-ISO-X1`.
   - `&http.Client{}` без явного `Transport` — shared `http.DefaultTransport` → `R-RES-ISO-X2`.

   ### `R-RES-TO-*`
   - Иерархия: `Transport.DialContext` (connect) < `Transport.ResponseHeaderTimeout` (read) < `http.Client.Timeout` (call) (`R-RES-TO-1`).
   - Per-system конфиг через `envconfig`-теги (`SberClientConfig{ConnectTimeout, ReadTimeout, CallTimeout}`) (`R-RES-TO-2`).
   - `capTimeout` уважает входящий дедлайн контекста: `min(callTimeout, remainingBudget - 100ms)` (`R-RES-TO-3`).
   - `&http.Client{}` без `Timeout` и без `Transport` с `DialContext` → `R-RES-TO-X1`.
   - `CallTimeout < ReadTimeout` — `http.Client.Timeout` срабатывает раньше `ResponseHeaderTimeout` → `R-RES-TO-X2`.
   - `ReadTimeout > 60s` в синхронном хендлере → task-queue → `R-RES-TO-X3`.

   ### `R-RES-CB-*`
   - `gobreaker.CircuitBreaker` на **public-методе** структуры-адаптера, не на `*http.Client`, не на хендлере, не на репозитории (`R-RES-CB-1`).
   - Count-based окно 50, min requests 10, failure rate ≥50% (платёжные ≥30%), open 30s, half-open 3 пробных (`R-RES-CB-2..5`).
   - `gobreaker.ErrOpenState`/`ErrTooManyRequests` → port-specific `*SystemUnavailableError` (`R-RES-CB-6`).
   - `gobreaker` вокруг репозитория/SQL → `R-RES-CB-X1`.
   - Самописный CB на `sync.Mutex` + счётчик → `R-RES-CB-X2`.
   - `Name: "default"` или одно имя для нескольких систем — делят state → `R-RES-CB-X3`.

   ### `R-RES-RE-*`
   - `retry.Do` только при идемпотентности: read-метод (`GetOrderStatus`) или write с `Idempotency-Key` (`AUTH-19`) (`R-RES-RE-1`).
   - `retry.BackOffDelay`, max 3 попытки (≤5 включая первую), `retry.Context(ctx)` (`R-RES-RE-2/3`).
   - Долгий retry (>30s) / durable → task-queue (`*_task` таблица) (`R-RES-RE-4/5`).
   - `retry.Do` на write-методе без `Idempotency-Key` → двойная операция → `R-RES-RE-X1`.
   - Retry на 4xx — контрактная ошибка, повтор не поможет → `R-RES-RE-X2`.
   - `retry.FixedDelay` без экспоненциального роста → бьёт пачкой по лежащей системе → `R-RES-RE-X3`.
   - `retry.Do` без `retry.RetryIf` — ретраит `gobreaker.ErrOpenState` и 4xx → `R-RES-RE-X4`.

   ### `R-RES-BH-*`
   - `semaphore.NewWeighted(maxConcurrent)` per-system отдельно от HTTP connection pool (`R-RES-BH-1/2`).
   - `maxConcurrent ≈ MaxIdleConnsPerHost × 0.8` — срабатывает раньше исчерпания пула (`R-RES-BH-3`).
   - `sem.Acquire(ctx, 1)` до вызова `breaker.Execute` — контекст и OTel-трейс не теряются.
   - `errgroup` с фиксированным пулом горутин как bulkhead → теряется `context.Context`/OTel без явного проброса → `R-RES-BH-X1`.

   ### `R-RES-FB-*`
   - Fallback через `errors.As` в осознанной точке (кешированный результат, частичный ответ, разумный дефолт) (`R-RES-FB-1/2`).
   - `Money{Amount: 0}` как fallback для money-операций → бизнес-баг → `R-RES-FB-X1`.
   - `return result, nil` при фактической ошибке — тихий «успех» → `R-RES-FB-X2`.
   - Fallback во второй провайдер без собственного `gobreaker` на второй вызов → cascading failure → `R-RES-FB-X3`.

   ### `R-RES-OAS-*`
   - `gobreaker`/`retry.Do`/`sem.Acquire` — на public-методе структуры-адаптера, не на сгенерированном клиенте → `R-RES-OAS-1`.
   - Для новых систем клиент генерируется из OpenAPI-спеки (oapi-codegen), спека в `adapters/out/<system>/openapi/`, codegen в `internal/generated/` → `R-RES-OAS-2`.
   - Явный mapper generated DTO → domain-тип; port возвращает domain, не generated struct → `R-RES-OAS-4`.
   - `gobreaker` встроен в сгенерированный клиент — регенерация затрёт → `R-RES-OAS-X1`.
   - `PaymentPort.Register` возвращает `generated.RegisterResponse` — domain port раскрывает transport-DTO → `R-RES-OAS-X3`.

   ### `R-RES-HC-*`
   - На каждую систему — отдельный health-индикатор в `/health/ready` (`R-RES-HC-1`).
   - TTL-кеш ~30s: `sync.Mutex` + `lastCheck time.Time` + `lastOK bool`; не ходить во внешнюю систему на каждый K8s-пинг (`R-RES-HC-2`).
   - Лёгкий probe: `GET /health` или `HEAD /` с `context.WithTimeout(ctx, 3*time.Second)` (`R-RES-HC-3`).
   - Readiness учитывает внешние системы, liveness — нет (`R-RES-HC-4`).
   - Probe без TTL-кеша → K8s-пробы каждые 5s = DDoS внешней системы → `R-RES-HC-X1`.
   - Probe бизнес-операцией (`registerTestOrder`) — изменяет состояние, плодит мусорные данные → `R-RES-HC-X2`.

   ### `R-RES-ASYNC-*`
   - Polling внешней системы — через task-queue (`*_task` таблица + ticker-планировщик), не `time.Sleep`-цикл в горутине хендлера (`R-RES-ASYNC-1`).
   - `time.Sleep` в адаптере допустим только при total wait <2s (короткий transient backoff) (`R-RES-ASYNC-2`).
   - Для async outbound (`goroutine` + channel) — `context.WithTimeout` обязателен (`R-RES-ASYNC-3`).
   - `time.Sleep`-цикл с опросом в HTTP-хендлере или в горутине из него → исчерпывает goroutine-пул → `R-RES-ASYNC-X1`.
   - `time.Sleep(d)` с `d > 5s` → запах «должно быть task-queue» → `R-RES-ASYNC-X2`.

   ### `R-RES-OBS-*`
   - `promauto`: `circuit_breaker_state{system}` (Gauge), `retry_attempts_total{system,outcome}` (Counter), `bulkhead_rejected_total{system}` (Counter) (`R-RES-OBS-1`).
   - OTel-span на adapter-методе: атрибуты `external.system`, `circuit_breaker.state`; `span.RecordError` + `span.SetStatus(codes.Error, ...)` (`R-RES-OBS-2`).
   - WARN-лог на каждый state-transition CB в `OnStateChange` callback'е `gobreaker.Settings` (system, prev_state, new_state) (`R-RES-OBS-3`).
   - Отключение resilience-метрик без причины → SRE не увидит залипший half-open → `R-RES-OBS-X1`.

4. **Cross-check:** retry write без ключа → `AUTH-19` + `R-RES-RE-X1`; port-specific ошибки от CB → `R-ERR-HIER-4` (`errors.As` + `Kind() Integration`); метрики/трейсинг → `ucp-go-observability-review`; структура out-adapter → `ucp-go-hexagonal-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна, код правила в каждой находке.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — retry write без `Idempotency-Key` (`R-RES-RE-X1`), `http.DefaultClient`/shared `*http.Client` (`R-RES-ISO-X1`), нет `Timeout` в `http.Client` (`R-RES-TO-X1`), `time.Sleep`-цикл polling в хендлере (`R-RES-ASYNC-X1`), fallback `Money{0}` (`R-RES-FB-X1`), тихий `return result, nil` при ошибке (`R-RES-FB-X2`), `gobreaker` на репозитории (`R-RES-CB-X1`/`R-RES-WHERE-X1`).
   - **Предупреждение** — `gobreaker` на сгенерированном клиенте (`R-RES-OAS-X1`), самописный CB (`R-RES-CB-X2`), shared CB-state (`R-RES-CB-X3`), retry на 4xx (`R-RES-RE-X2`), `FixedDelay` без backoff (`R-RES-RE-X3`), `retry.Do` без `RetryIf` (`R-RES-RE-X4`), `errgroup`-bulkhead (`R-RES-BH-X1`), health без TTL-кеша (`R-RES-HC-X1`).
   - **Замечание** — port возвращает generated DTO (`R-RES-OAS-X3`), метрики resilience отключены (`R-RES-OBS-X1`), probe бизнес-операцией (`R-RES-HC-X2`), fallback во второй провайдер без CB (`R-RES-FB-X3`).

## Что не входит

- Структура out-adapter/портов — `ucp-go-hexagonal-review`. Скелет outbound-клиента — `ucp-go-integration-review`.
- Метрики/трейсинг — `ucp-go-observability-review`.
- Port-specific ошибки, `errors.As`, `Kind`-маркер — `ucp-go-error-handling-review`.

$ARGUMENTS
