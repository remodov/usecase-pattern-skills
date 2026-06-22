---
name: ucp-node-shutdown-review
lang: node
description: Ревью graceful shutdown NestJS-сервиса (Node) по UCP (коды R-SHUT-*) — enableShutdownHooks, readiness→503 на SIGTERM, kafkajs disconnect с таймаутом, dataSource.destroy() после дренажа, дожатие фоновых задач, k8s preStop.
when_to_use: Изменения в main.ts/shutdown-хуках, lifecycle-хендлерах NestJS, k8s-манифестах или фоновых джобах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Graceful Shutdown (Node / NestJS lifecycle + kafkajs + pg)

Ты ревьюишь корректное завершение на соответствие **контракту** `backend/graceful-shutdown/graceful-shutdown-rules.md`
(`R-SHUT-*`) и **Node-реализации** `backend/graceful-shutdown/node/graceful-shutdown-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/graceful-shutdown-rules.md`** + **`backend/graceful-shutdown/node/graceful-shutdown-style-guide.md`**.
- Парные: `backend/node/nest-bootstrap/...` (`NESTBOOT-12` shutdown hooks, `NESTBOOT-13` health), `backend/kafka/node/...` (consumer disconnect), `observability` (readiness/метрики), `auth-patterns` (`AUTH-19` идемпотентность).

## Инструкции

1. **Прочти** контракт + Node-style-guide. Цитируй коды (`R-SHUT-DB-X1`, `R-SHUT-SCHED-X1`), не префикс.

2. **Скоп.** `main.ts`, lifecycle-хуки (`beforeApplicationShutdown`/`onApplicationShutdown`), собственные SIGTERM-хендлеры, `@nestjs/schedule`-джобы/BullMQ-воркеры, outbox-relay, k8s-манифесты (Deployment), terminus health-эндпоинты; `git diff`.

3. **Прогон.**
   - **Базовое (`R-SHUT-1..3`):** единый shutdown-state сервис, на который завязан `/health/ready` (свой `let shuttingDown` не связанный с health → `R-SHUT-CFG-X1`); budget 60s.
   - **Runtime (`R-SHUT-CFG-*`):** `app.enableShutdownHooks()` в `main.ts` (`R-SHUT-CFG-1`); force-deadline ~30s поверх `server.close()` — `Promise.race` + `setTimeout(...).unref()` (`R-SHUT-CFG-2`); readiness→503 первым в `beforeApplicationShutdown` (`R-SHUT-CFG-3`); раздельные live/ready на terminus (`R-SHUT-CFG-4`).
   - **HTTP (`R-SHUT-HTTP-*`):** preStop sleep (нет → `R-SHUT-K8S-X1`); `closeIdleConnections()` для keep-alive; `process.exit(0)` в SIGTERM-хендлере / `closeAllConnections()` сразу → `R-SHUT-HTTP-X1`; долгие эндпоинты — 202+polling.
   - **Kafka (`R-SHUT-KFK-*`):** `consumer.disconnect()`/`producer.disconnect()` с таймаутом в `beforeApplicationShutdown`; commit после обработки (`resolveOffset` до обработки / fire-and-forget handler → `R-SHUT-KFK-X1`); cascade в outbox, не в handler.
   - **БД (`R-SHUT-DB-*`):** `dataSource.destroy()`/`pool.end()` в `onApplicationShutdown` — **после** дренажа; в `beforeApplicationShutdown`/раньше задач → `R-SHUT-DB-X1`.
   - **Фон/outbox (`R-SHUT-SCHED-*`):** интервалы через `SchedulerRegistry`, in-flight Promise awaited, `worker.close()` без force; `clearInterval` без `await`/`worker.close(true)` → `R-SHUT-SCHED-X1`; outbox завершает batch, проверяет `isDraining()`, не `while (true)`.
   - **k8s (`R-SHUT-K8S-*`):** grace 60s (default 30 при 30s graceful → `R-SHUT-K8S-X2`); preStop (нет → `R-SHUT-K8S-X1`); probes на /health/{live,ready}; maxUnavailable 0.
   - **Идемпотентность (`R-SHUT-IDEM-*`):** in-flight write retry-safe; money без `Idempotency-Key` под retry → `R-SHUT-IDEM-X1`.
   - **Observability (`R-SHUT-OBS-*`):** метрика+лог shutdown; нормальное закрытие пула/consumer на ERROR → `R-SHUT-OBS-X1`.

4. **Cross-check:** shutdown-hooks/health-wiring — `ucp-node-bootstrap-review`; kafkajs commit/offset — `ucp-node-kafka-review`; idempotency — `ucp-node-distributed-review`/`ucp-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — нет `enableShutdownHooks()` (`R-SHUT-CFG-1`), `dataSource.destroy()`/`pool.end()` до завершения задач (`R-SHUT-DB-X1`), отмена фоновых задач без дожатия (`R-SHUT-SCHED-X1`), commit «вперёд» обработки (`R-SHUT-KFK-X1`), money без idempotency под retry (`R-SHUT-IDEM-X1`), нет preStop (`R-SHUT-K8S-X1`), `process.exit(0)` в SIGTERM-хендлере (`R-SHUT-HTTP-X1`).
   - **Предупреждение** — свой флаг вместо shutdown-state с health (`R-SHUT-CFG-X1`), grace 30s при 30s graceful (`R-SHUT-K8S-X2`), consumer/producer без disconnect в hooks, нет force-deadline поверх `server.close()` (`R-SHUT-CFG-2`), нет раздельных probes.
   - **Замечание** — нет метрики `app_shutdown_duration_seconds` (`R-SHUT-OBS-2`), нормальное закрытие на ERROR (`R-SHUT-OBS-X1`), долгий синхронный эндпоинт без 202.

## Что не входит

- Shutdown-hooks/health/DI-композиция — `ucp-node-bootstrap-review`. kafkajs commit/offset-семантика — `ucp-node-kafka-review`.
- Идемпотентность-таблицы/saga — `ucp-node-distributed-review`. Idempotency-Key контракт — `ucp-auth-review`.

$ARGUMENTS
