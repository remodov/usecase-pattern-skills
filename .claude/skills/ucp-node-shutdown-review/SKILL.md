---
name: ucp-node-shutdown-review
lang: node
description: Ревью graceful shutdown NestJS-сервиса (Node) по UCP (требования graceful-shutdown/*) — enableShutdownHooks, readiness→503 на SIGTERM, kafkajs disconnect с таймаутом, dataSource.destroy() после дренажа, дожатие фоновых задач, k8s preStop.
when_to_use: Изменения в main.ts/shutdown-хуках, lifecycle-хендлерах NestJS, k8s-манифестах или фоновых джобах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Graceful Shutdown (Node / NestJS lifecycle + kafkajs + pg)

Ты ревьюишь корректное завершение на соответствие **контракту** `backend/graceful-shutdown/spec.md`
(`R-SHUT-*`) и **Node-реализации** `backend/graceful-shutdown/references/node/implementation.md`.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/spec.md`** + **`backend/graceful-shutdown/references/node/implementation.md`**.
- Парные: `backend/node/nest-bootstrap/...` (`nest-bootstrap/shutdown-hooks-enabled` shutdown hooks, `nest-bootstrap/liveness-and-readiness-split` health), `backend/kafka/node/...` (consumer disconnect), `observability` (readiness/метрики), `auth-patterns` (`auth-patterns/money-commands-need-idempotency-key` идемпотентность).

## Инструкции

1. **Прочти** требования `node-style/*`. Цитируй коды (`graceful-shutdown/connection-pool-closes-last`, `graceful-shutdown/background-tasks-finish-iteration`), не префикс.

2. **Скоп.** `main.ts`, lifecycle-хуки (`beforeApplicationShutdown`/`onApplicationShutdown`), собственные SIGTERM-хендлеры, `@nestjs/schedule`-джобы/BullMQ-воркеры, outbox-relay, k8s-манифесты (Deployment), terminus health-эндпоинты; `git diff`.

3. **Прогон.**
   - **Базовое (`R-SHUT-1..3`):** единый shutdown-state сервис, на который завязан `/health/ready` (свой `let shuttingDown` не связанный с health → `graceful-shutdown/readiness-off-first`); budget 60s.
   - **Runtime (`R-SHUT-CFG-*`):** `app.enableShutdownHooks()` в `main.ts` (`graceful-shutdown/web-server-graceful-enabled`); force-deadline ~30s поверх `server.close()` — `Promise.race` + `setTimeout(...).unref()` (`graceful-shutdown/shutdown-budget-is-explicit`); readiness→503 первым в `beforeApplicationShutdown` (`graceful-shutdown/readiness-off-first`); раздельные live/ready на terminus (`graceful-shutdown/readiness-off-first`).
   - **HTTP (`R-SHUT-HTTP-*`):** preStop sleep (нет → `graceful-shutdown/prestop-delay`); `closeIdleConnections()` для keep-alive; `process.exit(0)` в SIGTERM-хендлере / `closeAllConnections()` сразу → `graceful-shutdown/web-server-graceful-enabled`; долгие эндпоинты — 202+polling.
   - **Kafka (`R-SHUT-KFK-*`):** `consumer.disconnect()`/`producer.disconnect()` с таймаутом в `beforeApplicationShutdown`; commit после обработки (`resolveOffset` до обработки / fire-and-forget handler → `graceful-shutdown/consumer-finishes-batch`); cascade в outbox, не в handler.
   - **БД (`R-SHUT-DB-*`):** `dataSource.destroy()`/`pool.end()` в `onApplicationShutdown` — **после** дренажа; в `beforeApplicationShutdown`/раньше задач → `graceful-shutdown/connection-pool-closes-last`.
   - **Фон/outbox (`R-SHUT-SCHED-*`):** интервалы через `SchedulerRegistry`, in-flight Promise awaited, `worker.close()` без force; `clearInterval` без `await`/`worker.close(true)` → `graceful-shutdown/background-tasks-finish-iteration`; outbox завершает batch, проверяет `isDraining()`, не `while (true)`.
   - **k8s (`R-SHUT-K8S-*`):** grace 60s (default 30 при 30s graceful → `graceful-shutdown/shutdown-budget-is-explicit`); preStop (нет → `graceful-shutdown/prestop-delay`); probes на /health/{live,ready}; maxUnavailable 0.
   - **Идемпотентность (`R-SHUT-IDEM-*`):** in-flight write retry-safe; money без `Idempotency-Key` под retry → `graceful-shutdown/in-flight-operations-are-retry-safe`.
   - **Observability (`R-SHUT-OBS-*`):** метрика+лог shutdown; нормальное закрытие пула/consumer на ERROR → `graceful-shutdown/shutdown-is-observable`.

4. **Cross-check:** shutdown-hooks/health-wiring — `ucp-node-bootstrap-review`; kafkajs commit/offset — `ucp-node-kafka-review`; idempotency — `ucp-node-distributed-review`/`ucp-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — нет `enableShutdownHooks()` (`graceful-shutdown/web-server-graceful-enabled`), `dataSource.destroy()`/`pool.end()` до завершения задач (`graceful-shutdown/connection-pool-closes-last`), отмена фоновых задач без дожатия (`graceful-shutdown/background-tasks-finish-iteration`), commit «вперёд» обработки (`graceful-shutdown/consumer-finishes-batch`), money без idempotency под retry (`graceful-shutdown/in-flight-operations-are-retry-safe`), нет preStop (`graceful-shutdown/prestop-delay`), `process.exit(0)` в SIGTERM-хендлере (`graceful-shutdown/web-server-graceful-enabled`).
   - **Предупреждение** — свой флаг вместо shutdown-state с health (`graceful-shutdown/readiness-off-first`), grace 30s при 30s graceful (`graceful-shutdown/shutdown-budget-is-explicit`), consumer/producer без disconnect в hooks, нет force-deadline поверх `server.close()` (`graceful-shutdown/shutdown-budget-is-explicit`), нет раздельных probes.
   - **Замечание** — нет метрики `app_shutdown_duration_seconds` (`graceful-shutdown/shutdown-is-observable`), нормальное закрытие на ERROR (`graceful-shutdown/shutdown-is-observable`), долгий синхронный эндпоинт без 202.

## Что не входит

- Shutdown-hooks/health/DI-композиция — `ucp-node-bootstrap-review`. kafkajs commit/offset-семантика — `ucp-node-kafka-review`.
- Идемпотентность-таблицы/saga — `ucp-node-distributed-review`. Idempotency-Key контракт — `ucp-auth-review`.

$ARGUMENTS
