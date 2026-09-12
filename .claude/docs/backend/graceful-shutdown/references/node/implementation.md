# Graceful Shutdown — реализация на Node (NestJS lifecycle + kafkajs + pg)

Реализация язык-нейтрального контракта `../spec.md` (`R-SHUT-*`) на NestJS/Node. Коды общие с
Java/Python; механизм: вместо Spring graceful + `ApplicationAvailability` — **`app.enableShutdownHooks()`** +
lifecycle-хуки (`beforeApplicationShutdown` → закрытие HTTP-сервера → `onApplicationShutdown`) + readiness-флаг,
который читает terminus-проба. K8s-часть (`R-SHUT-K8S-*`) нейтральна.

`graceful-shutdown/no-work-lost-on-sigterm` — на SIGTERM сервис завершается без потерь: in-flight HTTP дожимаются, kafkajs-offset коммитится, фоновые
задачи/джобы доводят итерацию, БД-транзакции commit/rollback. `graceful-shutdown/shutdown-budget-is-explicit` — total budget 60s
(`terminationGracePeriodSeconds: 60`); внутри — preStop + HTTP drain + Kafka + БД. `graceful-shutdown/readiness-off-first` — единый источник
состояния — один shutdown-state сервис, на который завязан `/health/ready` (не разрозненные `boolean` по модулям);
SIGTERM переводит readiness в 503, k8s убирает pod из endpoints.

## 1. Runtime/конфигурация (`R-SHUT-CFG-*`)

`graceful-shutdown/web-server-graceful-enabled` — **`app.enableShutdownHooks()`** в `main.ts` обязателен — без него Nest не слушает SIGTERM,
процесс умирает сразу, активные HTTP → 502. `graceful-shutdown/shutdown-budget-is-explicit` — явный graceful-deadline (~30s): `server.close()` в Node
ждёт in-flight **неограниченно** — нужен force-таймер (`Promise.race` с `setTimeout(...).unref()`), 20–45s чтобы
влезть в 60s. `graceful-shutdown/readiness-off-first` — первым действием shutdown — readiness → 503:

```ts
@Injectable()
export class ShutdownStateService implements BeforeApplicationShutdown {
  private draining = false;
  isDraining(): boolean { return this.draining; }
  beforeApplicationShutdown(): void { this.draining = true; }   // /health/ready → 503 до дренажа
}
```

`graceful-shutdown/readiness-off-first` — раздельные `/health/live` + `/health/ready` на terminus (cross-ref `observability/liveness-and-readiness-split`); ready-индикатор
проверяет `isDraining()`.

`graceful-shutdown/readiness-off-first` — свой `let shuttingDown` в случайном модуле, не связанный с health-пробой (k8s не узнает).

## 2. HTTP drain (`R-SHUT-HTTP-*`)

`graceful-shutdown/web-server-graceful-enabled` — in-flight HTTP дожимаются: `app.close()` вызывает `server.close()` — новые соединения не
принимаются, активные ответы завершаются; для keep-alive — `server.closeIdleConnections()` (Node ≥ 18.2), иначе
drain висит на пустых сокетах. `graceful-shutdown/prestop-delay` — **preStop `sleep 10`** обязателен даже при graceful (k8s шлёт
SIGTERM до распространения «убрать из endpoints»). `graceful-shutdown/long-operations-are-async` — долгие синхронные эндпоинты (>10s) —
`202 Accepted` + polling / задача с `Idempotency-Key` (`auth-patterns/money-commands-need-idempotency-key`).

`graceful-shutdown/web-server-graceful-enabled` — `process.exit(0)` в собственном SIGTERM-хендлере / `server.closeAllConnections()` сразу —
рвёт активные ответы, аннулирует graceful.

## 3. Kafka shutdown (`R-SHUT-KFK-*`)

`graceful-shutdown/consumer-finishes-batch` — kafkajs consumer на остановке дожидается текущего `eachMessage`/`eachBatch` и коммитит offset:
`await consumer.disconnect()` в `beforeApplicationShutdown`, обёрнутый в таймаут ~20s:

```ts
async beforeApplicationShutdown(): Promise<void> {
  await Promise.race([this.consumer.disconnect(), timeout(20_000)]);
}
```

`graceful-shutdown/consumer-finishes-batch` — handler не запускает долгий cascade (chain HTTP с retry не уложится в таймаут) — cascade в
async-flow/outbox. `graceful-shutdown/consumer-finishes-batch` — явная commit-семантика: `eachBatch` с `resolveOffset()` после обработки записи +
`commitOffsetsIfNecessary()` (replay защищён идемпотентностью), не дефолт «как получится». `graceful-shutdown/consumer-finishes-batch` —
`await producer.disconnect()` (flush + close) на shutdown.

`graceful-shutdown/consumer-finishes-batch` — commit «вперёд» обработки: `resolveOffset()` до фактической обработки / fire-and-forget handler
без `await` — offset закоммичен, сообщение потеряно (cross-ref `kafka/manual-offset-commit`).

## 4. БД и persistence (`R-SHUT-DB-*`)

`graceful-shutdown/connection-pool-closes-last` — `pool.end()` (pg) / `dataSource.destroy()` (TypeORM) — в **`onApplicationShutdown`**: Nest вызывает
его после `beforeApplicationShutdown` и закрытия HTTP-сервера, т.е. после дренажа — порядок правильный по
конструкции. `graceful-shutdown/transactions-finish-in-own-channel` — активные транзакции завершаются своим каналом (HTTP — drain, consumer — batch commit,
фон — дожатие итерации). `graceful-shutdown/transactions-finish-in-own-channel` — миграции не запускаются на shutdown (это startup).

`graceful-shutdown/connection-pool-closes-last` — `pool.end()` в `beforeApplicationShutdown` / в начале shutdown — закроет пул под in-flight
запросами и работающими фоновыми задачами.

## 5. Фоновые задачи / очереди / outbox (`R-SHUT-SCHED-*`)

`graceful-shutdown/background-tasks-finish-iteration` — `@nestjs/schedule`-интервалы останавливаются через `SchedulerRegistry`, текущая итерация
дожимается: хранить in-flight Promise и `await` его на shutdown (~25s); BullMQ — `await worker.close()` (ждёт
активные джобы). `graceful-shutdown/background-tasks-finish-iteration` — долгий async-cascade — реагировать на shutdown-сигнал (`AbortSignal`/флаг):
дожать критичную секцию, не начинать следующую. `graceful-shutdown/outbox-relay-checks-readiness` — outbox-relay завершает текущий batch (атомарно
через `FOR UPDATE SKIP LOCKED`), не начинает новый; цикл проверяет `shutdownState.isDraining()`, не `while (true)`.

`graceful-shutdown/background-tasks-finish-iteration` — `clearInterval` без `await` in-flight Promise / `worker.close(true)` (force) — задача брошена
посреди итерации, частичные изменения без rollback (inconsistent state).

## 6. Kubernetes (`R-SHUT-K8S-*`, нейтрально)

`graceful-shutdown/shutdown-budget-is-explicit` — `terminationGracePeriodSeconds: 60` явно; preStop — бюджет сверху. `graceful-shutdown/readiness-off-first` —
`readinessProbe` → `/health/ready`, `livenessProbe` → `/health/live`; на shutdown readiness=503 (liveness-падение
рестартит pod). `graceful-shutdown/rolling-update-keeps-capacity` — `maxSurge: 1, maxUnavailable: 0` (нулевой downtime).

`graceful-shutdown/prestop-delay` — отсутствие preStop (5–15s трафика на умирающий pod → 502). `graceful-shutdown/shutdown-budget-is-explicit` — default
`terminationGracePeriodSeconds: 30` при 30s graceful (SIGKILL посреди дренажа).

## 7. Идемпотентность in-flight (`R-SHUT-IDEM-*`)

`graceful-shutdown/in-flight-operations-are-retry-safe` — операции, которые SIGTERM может прервать, retry-safe: write с `Idempotency-Key`, money-cascade в
task-queue, Kafka-handler через outbox + `processed_event` дедуп (сшивка с `auth-patterns/money-commands-need-idempotency-key`, `R-DIST-IDEM`).

`graceful-shutdown/in-flight-operations-are-retry-safe` — money-операция без `Idempotency-Key` под retry (SIGTERM в момент retry → двойное списание;
запрещено `resilience/retry-only-when-safe`).

## 8. Бюджеты и observability (`R-SHUT-OBS-*`)

`graceful-shutdown/shutdown-budget-is-explicit` — реалистичный cumulative-бюджет (preStop 10s + HTTP drain ≤25s + фоновые задачи/очереди ≤20s +
Kafka ≤15s ≤ 60s); не влезает — сократить scope (batch 100→20), не растить budget. `graceful-shutdown/shutdown-is-observable` — метрика
`app_shutdown_duration_seconds` (prom-client `Gauge`) + структурный лог начала/конца shutdown. `graceful-shutdown/shutdown-is-observable` —
лог факта SIGTERM («получили SIGTERM, начинаем graceful»).

`graceful-shutdown/shutdown-is-observable` — логирование нормального закрытия пула/consumer'а на ERROR (шум в alert-канале на каждый деплой) —
INFO.

## 9. Чеклист подключения к новому сервису (Node/NestJS)

1. `app.enableShutdownHooks()`; force-deadline ~30s поверх `server.close()`; readiness→503 первым; раздельные live/ready на terminus.
2. preStop sleep 10; in-flight HTTP дожимаются, `closeIdleConnections()` для keep-alive; долгие эндпоинты — 202+polling.
3. kafkajs `consumer.disconnect()`/`producer.disconnect()` с таймаутом в `beforeApplicationShutdown`; commit после обработки; cascade в outbox.
4. `pool.end()`/`dataSource.destroy()` в `onApplicationShutdown` (после дренажа), не раньше.
5. Интервалы/джобы дожимают итерацию (`await` in-flight, `worker.close()` без force); outbox завершает batch и смотрит на draining-флаг.
6. k8s: grace 60s, preStop, probes на `/health/{live,ready}`, maxUnavailable 0.
7. in-flight retry-safe (idempotency-key/outbox); метрика+лог shutdown; нормальное закрытие не ERROR.
