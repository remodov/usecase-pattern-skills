---
name: ucp-go-resilience-design
lang: go
description: Спроектировать защиту Go-сервиса от отказов внешних систем (требования resilience/*) — per-system *http.Client + Transport, gobreaker, semaphore bulkhead, avast/retry-go при идемпотентности, fallback, health-check с TTL, slog/OTel observability.
when_to_use: Подключение внешней системы или добавление resilience. Триггеры — «защити вызов X», «circuit breaker для Y», «таймауты/ретраи на Go».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Resilience — проектирование (Go / net/http + chi)

Ты проектируешь защиту от отказов по **контракту** `backend/resilience/spec.md` (`R-RES-*`) и
**Go-реализации** `backend/resilience/references/go/implementation.md`.

## Инструкции

1. **Прочитай** требования `go-style/*`. Коды в обосновании, не в коде. Связанные: `backend/hexagonal/go/...` (out-adapter/порт), `backend/error-handling/go/...` (apperr.Kind + errors.As), `backend/observability/go/...` (метрики/спаны).

2. **Определи границу** (`R-RES-WHERE-*`): outbound HTTP → полный набор (timeout + CB + bulkhead + опц. retry); internal s2s → timeout + CB; scheduler/outbox-relay → task-queue (`*_task`-таблица); inbound rate-limit → API Gateway. Не оборачивай репозитории, SQL, in-memory функции (`resilience/no-protection-around-local-operations`).

3. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев — соответствие выражается именами/типами/структурой; коды правил в комментариях не цитируй):

   ### 3.1 Per-system `*http.Client` + `*http.Transport` (`resilience/client-per-external-system`, `resilience/timeout-hierarchy`)
   Отдельный `*http.Client` на каждую систему с явными `DialContext` (connect), `ResponseHeaderTimeout` (read), `http.Client.Timeout` (call); `MaxIdleConnsPerHost ≈ maxConcurrent × 1.2`.

   ### 3.2 Типизированный конфиг (`resilience/declarative-configuration`)
   `<System>ClientConfig` с полями через `envconfig`-теги: `ConnectTimeout`, `ReadTimeout`, `CallTimeout`, `MaxConcurrent`, `BaseURL`; дефолты через `default:`-тег; имя системы = envconfig-префикс = имя в CB = имя в метриках.

   ### 3.3 `capTimeout` — уважение TimeBudget (`resilience/respect-remaining-time-budget`)
   Если во входящем `context.Context` есть дедлайн и `remaining < callTimeout` — использовать `remaining - 100ms` как таймаут вызова.

   ### 3.4 Circuit Breaker — `gobreaker.CircuitBreaker` per-system (`R-RES-CB-1..6`)
   На public-методе адаптера, не на сгенерированном клиенте; count-based окно 50, min 10 запросов, failure rate 50% (30% для платёжных); open 30s → half-open (3 пробных); `OnStateChange` → `slog.Warn` + обновление метрики. При `ErrOpenState` / `ErrTooManyRequests` — маппинг в port-specific `<System>UnavailableError`.

   ### 3.5 Bulkhead — `semaphore.NewWeighted` per-system (`R-RES-BH-1..3`)
   `golang.org/x/sync/semaphore`, размер `≈ MaxIdleConnsPerHost × 0.8`; `Acquire(ctx, 1)` до CB-вызова, `defer Release(1)`; context и OTel-трейс сохраняются в той же горутине.

   ### 3.6 Retry — `retry.Do` только при идемпотентности (`R-RES-RE-1..3`)
   `github.com/avast/retry-go/v4`; только на read-методах или write с `Idempotency-Key`; `retry.Attempts(3)`, `retry.DelayType(retry.BackOffDelay)`, `retry.Delay(200ms)`; `retry.RetryIf` — только timeout и 5xx, не `ErrOpenState`, не 4xx.

   ### 3.7 Mapper generated DTO → domain (`resilience/mapper-between-client-and-port`)
   Отдельный `mapper.go` в `adapters/out/<system>/`; адаптер возвращает domain-тип из `core/`, не generated struct; port не раскрывает transport-детали.

   ### 3.8 Health-check с TTL-кешем (`R-RES-HC-1..4`)
   `<System>HealthChecker` с `sync.Mutex`, полями `lastCheck time.Time`, `lastOK bool`, `ttl time.Duration`; probe `GET /health` или `HEAD /` с `context.WithTimeout(3s)`; результат кешируется на TTL ~30s; отражается в `/health/ready`.

   ### 3.9 Polling / async через task-queue (`R-RES-ASYNC-1..3`)
   Polling внешней системы — через таблицу `*_task` (поля `status`, `retry_count`, `next_attempt_at`, `last_error`) + scheduler с `time.NewTicker(5s)`; `time.Sleep` в адаптере допустим только при total wait <2s.

4. **Observability** (`R-RES-OBS-*`): `promauto.NewGaugeVec` `circuit_breaker_state{system}`, `promauto.NewCounterVec` `retry_attempts_total{system,outcome}` и `bulkhead_rejected_total{system}`; обновление CB-состояния в `OnStateChange`; OTel-span на adapter-методе с атрибутами `external.system` и `circuit_breaker.state`; `span.RecordError` + `span.SetStatus(codes.Error)`.

5. **Самопроверка** по чеклисту из `backend/resilience/references/go/implementation.md` §«Чеклист подключения к новому сервису (Go)». Скелет HTTP-клиента целиком — `ucp-go-integration-design`.

6. **Финальный шаг:** предложи «запусти `ucp-go-resilience-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `http.DefaultClient` или один `*http.Client` на несколько систем (`resilience/client-per-external-system`); `&http.Client{}` без `Timeout` и без `Transport` с DialContext (`resilience/timeout-hierarchy`/`resilience/client-per-external-system`).
- `gobreaker` / `retry.Do` / `sem.Acquire` на репозитории, SQL-запросе, in-memory функции (`resilience/no-protection-around-local-operations`/`resilience/no-protection-around-local-operations`); один CB с `Name: "default"` на несколько систем (`resilience/instance-names-match-system`).
- Самописный CB на `sync.Mutex` + счётчик (`resilience/no-custom-breaker`); `gobreaker` встроен в сгенерированный клиент — регенерация затрёт (`resilience/breaker-on-adapter-method`).
- `retry.Do` на write без `Idempotency-Key` (`resilience/retry-only-when-safe`); retry на 4xx (`resilience/retry-only-when-safe`); `retry.FixedDelay` без роста задержки (`resilience/retry-with-backoff-and-limit`); retry на `ErrOpenState` без согласования с `RetryIf` (`resilience/retry-with-backoff-and-limit`).
- `time.Sleep`-цикл в HTTP-handler'е (`resilience/no-long-synchronous-waits`); `time.Sleep > 5s` в адаптере (`resilience/no-long-synchronous-waits`).
- Probe `/health` без TTL-кеша (`resilience/cached-health-probe-per-system`); probe бизнес-операцией (`resilience/cached-health-probe-per-system`).
- Fallback `Money{Amount: 0}` для money-операций (`resilience/fallback-does-not-fake-success`); `return result, nil` при фактической ошибке (`resilience/fallback-does-not-fake-success`); fallback с outbound в резервный провайдер без собственного CB (`resilience/fallback-does-not-fake-success`).
- Адаптер возвращает generated DTO из port-метода (`R-RES-OAS-X3`).

После работы скилла — обязательно `ucp-go-resilience-review`.

$ARGUMENTS
