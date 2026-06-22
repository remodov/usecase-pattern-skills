---
name: ucp-go-shutdown-review
lang: go
description: Ревью graceful shutdown Go-сервиса (net/http + chi) по UCP (коды R-SHUT-*) — os.Signal + context.WithCancel, http.Server.Shutdown, atomic.Bool readiness, sync.WaitGroup для горутин, kafka-go CommitMessages, pgxpool.Close() последним, k8s preStop.
when_to_use: Изменения в server.go, main.go (shutdown-последовательность), health-эндпоинтах, Kafka-consumer/producer, outbox-relay, фоновых горутинах или k8s-манифестах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Graceful Shutdown (Go / net/http + chi)

Ты ревьюишь корректное завершение на соответствие **контракту** `backend/graceful-shutdown/graceful-shutdown-rules.md`
(`R-SHUT-*`) и **Go-реализации** `backend/graceful-shutdown/go/graceful-shutdown-style-guide.md`.

Парадигма: в Go нет `ApplicationAvailability` и `@PreDestroy`; механизм — **`os.Signal` канал + `context.WithCancel`**
+ `http.Server.Shutdown` + `sync.WaitGroup` для фоновых горутин. Ошибки — значения (`apperr.Kind` + `errors.As` +
`%w`), как в `error-handling/go/error-handling-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/graceful-shutdown-rules.md`** + **`backend/graceful-shutdown/go/graceful-shutdown-style-guide.md`**.
- Парные: `backend/error-handling/go/error-handling-style-guide.md` (ошибки-значения, `%w`), `backend/kafka/...` (consumer stop), `backend/observability/...` (readiness/метрики), `backend/auth-patterns/...` (`AUTH-19` идемпотентность).

## Инструкции

1. **Прочти** контракт + Go-style-guide. Цитируй коды (`R-SHUT-DB-X1`, `R-SHUT-SCHED-X1`), не префикс.

2. **Скоп.** `server.go`/`main.go` (shutdown-последовательность), `health/*.go`, `consumer/*.go`, `scheduler/*.go` (outbox-relay, фоновые горутины), `adapters/out/*.go`, k8s-манифесты (Deployment); `git diff`.

3. **Прогон.**
   - **Базовое (`R-SHUT-1..3`):** readiness-флаг — единый источник (`atomic.Bool` в `health.State`; свой `bool` без atomic и без связи с health → `R-SHUT-CFG-X1`); budget 60s.
   - **Runtime (`R-SHUT-CFG-*`):** `http.Server.Shutdown(ctx)` вместо `srv.Close()` (`R-SHUT-CFG-1`); явный `context.WithTimeout` 20–25s (`R-SHUT-CFG-2`); `appState.SetNotReady()` первым до Shutdown (`R-SHUT-CFG-3`); раздельные `/health/live` и `/health/ready` chi-маршруты (`R-SHUT-CFG-4`).
   - **HTTP (`R-SHUT-HTTP-*`):** `preStop: sleep 10` в Deployment (нет → `R-SHUT-K8S-X1`); `srv.Close()` вместо `srv.Shutdown(ctx)` → `R-SHUT-HTTP-X1`; долгие эндпоинты (>10s) — 202+polling.
   - **Kafka (`R-SHUT-KFK-*`):** consumer управляется `context.Context`; `CommitMessages` после каждого сообщения (`R-SHUT-KFK-3`); `writer.Close()` на shutdown (`R-SHUT-KFK-4`); `CommitInterval`-режим (авто-коммит) → `R-SHUT-KFK-X1`.
   - **БД (`R-SHUT-DB-*`):** `pgxpool.Pool.Close()` **последним** в shutdown-последовательности — после `WaitGroup.Wait()` по задачам и consumer'у; до завершения горутин → `R-SHUT-DB-X1`.
   - **Async/outbox (`R-SHUT-SCHED-*`):** горутины завершают текущую итерацию (`ctx.Done()` перед `ticker.C`) + `sync.WaitGroup`; критичная секция транзакции — `context.Background()`, не родительский ctx; отмена без `WaitGroup.Wait()` → `R-SHUT-SCHED-X1`; outbox-relay завершает текущий batch, проверяет `ctx.Done()`, не `for { ... }` без проверки.
   - **k8s (`R-SHUT-K8S-*`):** `terminationGracePeriodSeconds: 60` (default 30 при 25s graceful → `R-SHUT-K8S-X2`); preStop (нет → `R-SHUT-K8S-X1`); probes на `/health/live` и `/health/ready`; `maxUnavailable: 0`.
   - **Идемпотентность (`R-SHUT-IDEM-*`):** write-операции retry-safe; out-adapter выставляет `Idempotency-Key` в заголовке; money-cascade — через outbox/task-queue; Kafka-handler — `ON CONFLICT DO NOTHING` по `event_id`; money без `Idempotency-Key` под retry → `R-SHUT-IDEM-X1`.
   - **Observability (`R-SHUT-OBS-*`):** `app_shutdown_duration_seconds` (promauto Gauge) + структурный лог `slog.InfoContext` начала/конца; нормальное закрытие пула/consumer'а на `slog.Error` → `R-SHUT-OBS-X1`.

4. **Cross-check:** shutdown-последовательность/health-wiring — `ucp-go-bootstrap-review`; kafka CommitMessages — `ucp-go-kafka-review`; idempotency — `ucp-go-distributed-review`/`ucp-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `srv.Close()` вместо `srv.Shutdown(ctx)` (`R-SHUT-HTTP-X1`), `pool.Close()` до завершения горутин (`R-SHUT-DB-X1`), горутина без `WaitGroup.Wait()` (`R-SHUT-SCHED-X1`), `CommitInterval`-авто-коммит (`R-SHUT-KFK-X1`), money без `Idempotency-Key` под retry (`R-SHUT-IDEM-X1`), нет preStop (`R-SHUT-K8S-X1`).
   - **Предупреждение** — `var shuttingDown bool` без `atomic.Bool` без связи с health (`R-SHUT-CFG-X1`), `terminationGracePeriodSeconds: 30` при 25s graceful (`R-SHUT-K8S-X2`), writer/reader не закрыты на shutdown, нет раздельных probes.
   - **Замечание** — нет `app_shutdown_duration_seconds` (`R-SHUT-OBS-2`), нормальное закрытие пула/consumer'а на `slog.Error` (`R-SHUT-OBS-X1`), долгий sync-эндпоинт без 202.

## Что не входит

- Health-wiring/DI-композиция — `ucp-go-bootstrap-review`. kafka CommitMessages/offset — `ucp-go-kafka-review`.
- Идемпотентность-таблицы/saga — `ucp-go-distributed-review`. Idempotency-Key контракт — `ucp-auth-review`.

$ARGUMENTS
