---
name: ucp-go-shutdown-review
lang: go
description: Ревью graceful shutdown Go-сервиса (net/http + chi) по UCP — os.Signal + context.WithCancel, http.Server.Shutdown, atomic.Bool readiness, sync.WaitGroup для горутин, kafka-go CommitMessages, pgxpool.Close() последним, k8s preStop.
when_to_use: Изменения в server.go, main.go (shutdown-последовательность), health-эндпоинтах, Kafka-consumer/producer, outbox-relay, фоновых горутинах или k8s-манифестах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*) Bash(go vet*)
---

# Ревью Graceful Shutdown (Go / net/http + chi)

Ты ревьюишь корректное завершение на соответствие **контракту** `backend/graceful-shutdown/spec.md`
(`R-SHUT-*`) и **Go-реализации** `backend/graceful-shutdown/references/go/implementation.md`.

Парадигма: в Go нет `ApplicationAvailability` и `@PreDestroy`; механизм — **`os.Signal` канал + `context.WithCancel`**
+ `http.Server.Shutdown` + `sync.WaitGroup` для фоновых горутин. Ошибки — значения (`apperr.Kind` + `errors.As` +
`%w`), как в `error-handling/references/go/implementation.md`.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/spec.md`** + **`backend/graceful-shutdown/references/go/implementation.md`**.
- Парные: `backend/error-handling/references/go/implementation.md` (ошибки-значения, `%w`), `backend/kafka/...` (consumer stop), `backend/observability/...` (readiness/метрики), `backend/auth-patterns/...` (`auth-patterns/money-commands-need-idempotency-key` идемпотентность).

## Инструкции

1. **Прочти** требования `go-style/*`. Цитируй коды (`graceful-shutdown/connection-pool-closes-last`, `graceful-shutdown/background-tasks-finish-iteration`), не префикс.

2. **Скоп.** `server.go`/`main.go` (shutdown-последовательность), `health/*.go`, `consumer/*.go`, `scheduler/*.go` (outbox-relay, фоновые горутины), `adapters/out/*.go`, k8s-манифесты (Deployment); `git diff`.

3. **Прогон.**
   - **Базовое (`R-SHUT-1..3`):** readiness-флаг — единый источник (`atomic.Bool` в `health.State`; свой `bool` без atomic и без связи с health → `graceful-shutdown/readiness-off-first`); budget 60s.
   - **Runtime (`R-SHUT-CFG-*`):** `http.Server.Shutdown(ctx)` вместо `srv.Close()` (`graceful-shutdown/web-server-graceful-enabled`); явный `context.WithTimeout` 20–25s (`graceful-shutdown/shutdown-budget-is-explicit`); `appState.SetNotReady()` первым до Shutdown (`graceful-shutdown/readiness-off-first`); раздельные `/health/live` и `/health/ready` chi-маршруты (`graceful-shutdown/readiness-off-first`).
   - **HTTP (`R-SHUT-HTTP-*`):** `preStop: sleep 10` в Deployment (нет → `graceful-shutdown/prestop-delay`); `srv.Close()` вместо `srv.Shutdown(ctx)` → `graceful-shutdown/web-server-graceful-enabled`; долгие эндпоинты (>10s) — 202+polling.
   - **Kafka (`R-SHUT-KFK-*`):** consumer управляется `context.Context`; `CommitMessages` после каждого сообщения (`graceful-shutdown/consumer-finishes-batch`); `writer.Close()` на shutdown (`graceful-shutdown/consumer-finishes-batch`); `CommitInterval`-режим (авто-коммит) → `graceful-shutdown/consumer-finishes-batch`.
   - **БД (`R-SHUT-DB-*`):** `pgxpool.Pool.Close()` **последним** в shutdown-последовательности — после `WaitGroup.Wait()` по задачам и consumer'у; до завершения горутин → `graceful-shutdown/connection-pool-closes-last`.
   - **Async/outbox (`R-SHUT-SCHED-*`):** горутины завершают текущую итерацию (`ctx.Done()` перед `ticker.C`) + `sync.WaitGroup`; критичная секция транзакции — `context.Background()`, не родительский ctx; отмена без `WaitGroup.Wait()` → `graceful-shutdown/background-tasks-finish-iteration`; outbox-relay завершает текущий batch, проверяет `ctx.Done()`, не `for { ... }` без проверки.
   - **k8s (`R-SHUT-K8S-*`):** `terminationGracePeriodSeconds: 60` (default 30 при 25s graceful → `graceful-shutdown/shutdown-budget-is-explicit`); preStop (нет → `graceful-shutdown/prestop-delay`); probes на `/health/live` и `/health/ready`; `maxUnavailable: 0`.
   - **Идемпотентность (`R-SHUT-IDEM-*`):** write-операции retry-safe; out-adapter выставляет `Idempotency-Key` в заголовке; money-cascade — через outbox/task-queue; Kafka-handler — `ON CONFLICT DO NOTHING` по `event_id`; money без `Idempotency-Key` под retry → `graceful-shutdown/in-flight-operations-are-retry-safe`.
   - **Observability (`R-SHUT-OBS-*`):** `app_shutdown_duration_seconds` (promauto Gauge) + структурный лог `slog.InfoContext` начала/конца; нормальное закрытие пула/consumer'а на `slog.Error` → `graceful-shutdown/shutdown-is-observable`.

4. **Cross-check:** shutdown-последовательность/health-wiring — `ucp-go-bootstrap-review`; kafka CommitMessages — `ucp-go-kafka-review`; idempotency — `ucp-go-distributed-review`/`ucp-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — `srv.Close()` вместо `srv.Shutdown(ctx)` (`graceful-shutdown/web-server-graceful-enabled`), `pool.Close()` до завершения горутин (`graceful-shutdown/connection-pool-closes-last`), горутина без `WaitGroup.Wait()` (`graceful-shutdown/background-tasks-finish-iteration`), `CommitInterval`-авто-коммит (`graceful-shutdown/consumer-finishes-batch`), money без `Idempotency-Key` под retry (`graceful-shutdown/in-flight-operations-are-retry-safe`), нет preStop (`graceful-shutdown/prestop-delay`).
   - **Предупреждение** — `var shuttingDown bool` без `atomic.Bool` без связи с health (`graceful-shutdown/readiness-off-first`), `terminationGracePeriodSeconds: 30` при 25s graceful (`graceful-shutdown/shutdown-budget-is-explicit`), writer/reader не закрыты на shutdown, нет раздельных probes.
   - **Замечание** — нет `app_shutdown_duration_seconds` (`graceful-shutdown/shutdown-is-observable`), нормальное закрытие пула/consumer'а на `slog.Error` (`graceful-shutdown/shutdown-is-observable`), долгий sync-эндпоинт без 202.

## Что не входит

- Health-wiring/DI-композиция — `ucp-go-bootstrap-review`. kafka CommitMessages/offset — `ucp-go-kafka-review`.
- Идемпотентность-таблицы/saga — `ucp-go-distributed-review`. Idempotency-Key контракт — `ucp-auth-review`.

$ARGUMENTS
