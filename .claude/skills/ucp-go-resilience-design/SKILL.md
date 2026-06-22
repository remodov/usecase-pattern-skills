---
name: ucp-go-resilience-design
lang: go
description: Спроектировать защиту Go-сервиса от отказов внешних систем (коды R-RES-*) — per-system *http.Client + Transport, gobreaker, semaphore bulkhead, avast/retry-go при идемпотентности, fallback, health-check с TTL, slog/OTel observability.
when_to_use: Подключение внешней системы или добавление resilience. Триггеры — «защити вызов X», «circuit breaker для Y», «таймауты/ретраи на Go».
allowed-tools: Read Glob Grep Write Edit Bash(go build*) Bash(go vet*) Bash(go test*)
---

# Resilience — проектирование (Go / net/http + chi)

Ты проектируешь защиту от отказов по **контракту** `backend/resilience/resilience-rules.md` (`R-RES-*`) и
**Go-реализации** `backend/resilience/go/resilience-style-guide.md`.

## Инструкции

1. **Прочитай** контракт + Go-style-guide. Коды в обосновании, не в коде. Связанные: `backend/hexagonal/go/...` (out-adapter/порт), `backend/error-handling/go/...` (apperr.Kind + errors.As), `backend/observability/go/...` (метрики/спаны).

2. **Определи границу** (`R-RES-WHERE-*`): outbound HTTP → полный набор (timeout + CB + bulkhead + опц. retry); internal s2s → timeout + CB; scheduler/outbox-relay → task-queue (`*_task`-таблица); inbound rate-limit → API Gateway. Не оборачивай репозитории, SQL, in-memory функции (`R-RES-WHERE-X1`).

3. **Произведи код** (полные `.go`-файлы, gofmt; без комментариев — соответствие выражается именами/типами/структурой; коды правил в комментариях не цитируй):

   ### 3.1 Per-system `*http.Client` + `*http.Transport` (`R-RES-ISO-1`, `R-RES-TO-1`)
   Отдельный `*http.Client` на каждую систему с явными `DialContext` (connect), `ResponseHeaderTimeout` (read), `http.Client.Timeout` (call); `MaxIdleConnsPerHost ≈ maxConcurrent × 1.2`.

   ### 3.2 Типизированный конфиг (`R-RES-CFG-1`)
   `<System>ClientConfig` с полями через `envconfig`-теги: `ConnectTimeout`, `ReadTimeout`, `CallTimeout`, `MaxConcurrent`, `BaseURL`; дефолты через `default:`-тег; имя системы = envconfig-префикс = имя в CB = имя в метриках.

   ### 3.3 `capTimeout` — уважение TimeBudget (`R-RES-TO-3`)
   Если во входящем `context.Context` есть дедлайн и `remaining < callTimeout` — использовать `remaining - 100ms` как таймаут вызова.

   ### 3.4 Circuit Breaker — `gobreaker.CircuitBreaker` per-system (`R-RES-CB-1..6`)
   На public-методе адаптера, не на сгенерированном клиенте; count-based окно 50, min 10 запросов, failure rate 50% (30% для платёжных); open 30s → half-open (3 пробных); `OnStateChange` → `slog.Warn` + обновление метрики. При `ErrOpenState` / `ErrTooManyRequests` — маппинг в port-specific `<System>UnavailableError`.

   ### 3.5 Bulkhead — `semaphore.NewWeighted` per-system (`R-RES-BH-1..3`)
   `golang.org/x/sync/semaphore`, размер `≈ MaxIdleConnsPerHost × 0.8`; `Acquire(ctx, 1)` до CB-вызова, `defer Release(1)`; context и OTel-трейс сохраняются в той же горутине.

   ### 3.6 Retry — `retry.Do` только при идемпотентности (`R-RES-RE-1..3`)
   `github.com/avast/retry-go/v4`; только на read-методах или write с `Idempotency-Key`; `retry.Attempts(3)`, `retry.DelayType(retry.BackOffDelay)`, `retry.Delay(200ms)`; `retry.RetryIf` — только timeout и 5xx, не `ErrOpenState`, не 4xx.

   ### 3.7 Mapper generated DTO → domain (`R-RES-OAS-4`)
   Отдельный `mapper.go` в `adapters/out/<system>/`; адаптер возвращает domain-тип из `core/`, не generated struct; port не раскрывает transport-детали.

   ### 3.8 Health-check с TTL-кешем (`R-RES-HC-1..4`)
   `<System>HealthChecker` с `sync.Mutex`, полями `lastCheck time.Time`, `lastOK bool`, `ttl time.Duration`; probe `GET /health` или `HEAD /` с `context.WithTimeout(3s)`; результат кешируется на TTL ~30s; отражается в `/health/ready`.

   ### 3.9 Polling / async через task-queue (`R-RES-ASYNC-1..3`)
   Polling внешней системы — через таблицу `*_task` (поля `status`, `retry_count`, `next_attempt_at`, `last_error`) + scheduler с `time.NewTicker(5s)`; `time.Sleep` в адаптере допустим только при total wait <2s.

4. **Observability** (`R-RES-OBS-*`): `promauto.NewGaugeVec` `circuit_breaker_state{system}`, `promauto.NewCounterVec` `retry_attempts_total{system,outcome}` и `bulkhead_rejected_total{system}`; обновление CB-состояния в `OnStateChange`; OTel-span на adapter-методе с атрибутами `external.system` и `circuit_breaker.state`; `span.RecordError` + `span.SetStatus(codes.Error)`.

5. **Самопроверка** по чеклисту из `backend/resilience/go/resilience-style-guide.md` §«Чеклист подключения к новому сервису (Go)». Скелет HTTP-клиента целиком — `ucp-go-integration-design`.

6. **Финальный шаг:** предложи «запусти `ucp-go-resilience-review` для верификации».

## Антипаттерны, которые НЕ генерировать

- `http.DefaultClient` или один `*http.Client` на несколько систем (`R-RES-ISO-X1`); `&http.Client{}` без `Timeout` и без `Transport` с DialContext (`R-RES-TO-X1`/`R-RES-ISO-X2`).
- `gobreaker` / `retry.Do` / `sem.Acquire` на репозитории, SQL-запросе, in-memory функции (`R-RES-WHERE-X1`/`R-RES-CB-X1`); один CB с `Name: "default"` на несколько систем (`R-RES-CB-X3`).
- Самописный CB на `sync.Mutex` + счётчик (`R-RES-CB-X2`); `gobreaker` встроен в сгенерированный клиент — регенерация затрёт (`R-RES-OAS-X1`).
- `retry.Do` на write без `Idempotency-Key` (`R-RES-RE-X1`); retry на 4xx (`R-RES-RE-X2`); `retry.FixedDelay` без роста задержки (`R-RES-RE-X3`); retry на `ErrOpenState` без согласования с `RetryIf` (`R-RES-RE-X4`).
- `time.Sleep`-цикл в HTTP-handler'е (`R-RES-ASYNC-X1`); `time.Sleep > 5s` в адаптере (`R-RES-ASYNC-X2`).
- Probe `/health` без TTL-кеша (`R-RES-HC-X1`); probe бизнес-операцией (`R-RES-HC-X2`).
- Fallback `Money{Amount: 0}` для money-операций (`R-RES-FB-X1`); `return result, nil` при фактической ошибке (`R-RES-FB-X2`); fallback с outbound в резервный провайдер без собственного CB (`R-RES-FB-X3`).
- Адаптер возвращает generated DTO из port-метода (`R-RES-OAS-X3`).

После работы скилла — обязательно `ucp-go-resilience-review`.

$ARGUMENTS
