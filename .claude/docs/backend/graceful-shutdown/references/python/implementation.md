# Graceful Shutdown — реализация на Python (uvicorn + lifespan + asyncio)

Реализация язык-нейтрального контракта `../spec.md` (`R-SHUT-*`) на FastAPI/uvicorn. Коды общие
с Java; механизм: вместо Spring graceful + `ApplicationAvailability` — **uvicorn graceful shutdown** +
**lifespan-shutdown** + readiness-флаг в `contextvar`/состоянии приложения. K8s-часть (`R-SHUT-K8S-*`) нейтральна.

`graceful-shutdown/no-work-lost-on-sigterm` — на SIGTERM сервис завершается без потерь: in-flight HTTP дожимаются, Kafka-offset коммитится, фоновые
asyncio-задачи доводят итерацию, БД-транзакции commit/rollback. `graceful-shutdown/shutdown-budget-is-explicit` — total budget 60s
(`terminationGracePeriodSeconds: 60`); внутри — preStop + uvicorn graceful + Kafka + БД. `graceful-shutdown/readiness-off-first` — единый источник
состояния — readiness-флаг приложения (не разрозненные `bool`); SIGTERM переводит readiness в `not ready`, `/health/
ready` → 503, k8s убирает pod из endpoints.

## 1. Runtime/конфигурация (`R-SHUT-CFG-*`)

`graceful-shutdown/web-server-graceful-enabled` — uvicorn graceful обязателен: `--timeout-graceful-shutdown 30` (или `Server.should_exit`); без него
активные запросы рвутся. `graceful-shutdown/shutdown-budget-is-explicit` — graceful-timeout явный (20–45s, чтобы влезть в 60s). `graceful-shutdown/readiness-off-first` —
shutdown-хендлер первым переводит readiness в 503 (в `lifespan`-shutdown или signal-handler). `graceful-shutdown/readiness-off-first` —
раздельные `/health/live` + `/health/ready` (cross-ref `python-bootstrap/liveness-and-readiness-split`, `observability/liveness-and-readiness-split`).

`graceful-shutdown/readiness-off-first` — свой `shutting_down: bool` вместо readiness-состояния приложения, не связанный с health (k8s не
узнает).

```python
# Единый источник readiness (R-SHUT-3): один объект, на который смотрит и /health/ready, и shutdown.
# НЕ разрозненные shutting_down: bool, не связанные с health (R-SHUT-CFG-X1).
class ReadinessState:
    def __init__(self) -> None:
        self._ready = False

    def mark_ready(self) -> None:
        self._ready = True

    def mark_not_ready(self) -> None:                      # SIGTERM → readiness=503 первым делом (R-SHUT-CFG-3)
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

# /health/ready читает тот же объект → на shutdown отдаёт 503, k8s убирает pod из endpoints (R-SHUT-CFG-4).
@router.get("/health/ready")
async def ready(state: ReadinessState = Depends(get_readiness_state)) -> JSONResponse:
    code = 200 if state.is_ready() else 503
    return JSONResponse({"status": "UP" if state.is_ready() else "DOWN"}, status_code=code)
```

uvicorn graceful обязателен (`R-SHUT-CFG-1/2`) — явный timeout, чтобы влезть в 60s-бюджет:

```bash
# R-SHUT-CFG-1/2: --timeout-graceful-shutdown явный (20–45s), не 0 (R-SHUT-HTTP-X1) — иначе in-flight рвутся.
uvicorn service.app.main:app --host 0.0.0.0 --port 8080 --timeout-graceful-shutdown 25
```

## 2. HTTP drain (`R-SHUT-HTTP-*`)

`graceful-shutdown/web-server-graceful-enabled` — in-flight HTTP дожимаются (uvicorn graceful). `graceful-shutdown/prestop-delay` — **preStop `sleep 10`** обязателен
даже при graceful (k8s шлёт SIGTERM до распространения «убрать из endpoints»). `graceful-shutdown/long-operations-are-async` — долгие синхронные
эндпоинты (>10s) — `202 Accepted` + polling / задача (`auth-patterns/money-commands-need-idempotency-key`).

`graceful-shutdown/web-server-graceful-enabled` — `--timeout-graceful-shutdown 0` / форсированный kill воркеров — аннулирует graceful.

## 3. Kafka shutdown (`R-SHUT-KFK-*`)

`graceful-shutdown/consumer-finishes-batch` — aiokafka consumer на остановке коммитит offset и закрывается (`await consumer.stop()` в lifespan-
shutdown; не оставлять задачу висеть). `graceful-shutdown/consumer-finishes-batch` — listener не запускает долгий cascade (в async-flow/outbox).
`graceful-shutdown/consumer-finishes-batch` — manual commit после обработки (cross-ref `kafka/manual-offset-commit`). `graceful-shutdown/consumer-finishes-batch` — `await producer.stop()`
(flush + close) на shutdown.

`graceful-shutdown/consumer-finishes-batch` — `enable_auto_commit=True` (потеря/дубль; запрещено `kafka/manual-offset-commit`).

```python
# R-SHUT-KFK-1/4: consumer и producer останавливаются в lifespan-shutdown — commit offset + flush + close.
# consumer.stop() докоммитит обработанное (manual commit, R-SHUT-KFK-3); producer.stop() сделает flush буфера.
async def stop_kafka(consumer: AIOKafkaConsumer, producer: AIOKafkaProducer) -> None:
    await consumer.stop()                                  # R-SHUT-KFK-1: не оставлять задачу висеть
    await producer.stop()                                  # R-SHUT-KFK-4: flush + close, иначе теряются буферы
```

## 4. БД и persistence (`R-SHUT-DB-*`)

`graceful-shutdown/connection-pool-closes-last` — `engine.dispose()` (закрытие пула SQLAlchemy) в lifespan-shutdown **после** дренажа HTTP/задач, не
раньше. `graceful-shutdown/transactions-finish-in-own-channel` — активные транзакции завершаются своим каналом (HTTP — graceful, фон — отмена с дожатием
итерации). `graceful-shutdown/transactions-finish-in-own-channel` — Liquibase-миграции не запускаются на shutdown (это startup/деплой).

`graceful-shutdown/connection-pool-closes-last` — `engine.dispose()` в начале shutdown, до завершения фоновых задач (закроет пул под работающими тасками).

```python
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

log = structlog.get_logger(__name__)

# Lifespan связывает порядок shutdown (R-SHUT-3): readiness→503 ПЕРВЫМ, затем дренаж, engine.dispose() ПОСЛЕДНИМ.
@asynccontextmanager
async def lifespan(app: FastAPI):
    container: Container = app.container
    state: ReadinessState = container.readiness_state()
    consumer, producer = container.kafka_consumer(), container.kafka_producer()
    relay_task = asyncio.create_task(outbox_relay_loop(container.outbox_relay(), state))

    await consumer.start()
    await producer.start()
    state.mark_ready()                                     # принимаем трафик
    log.info("startup_complete")
    yield
    # --- SIGTERM: uvicorn останавливает lifespan после дренажа in-flight HTTP (R-SHUT-HTTP-1) ---
    log.info("shutdown_started")                           # R-SHUT-OBS-3: лог факта SIGTERM
    state.mark_not_ready()                                 # R-SHUT-CFG-3: readiness→503 ПЕРВЫМ, k8s убирает из endpoints
    await stop_background_task(relay_task)                 # R-SHUT-SCHED-1: дожать фоновые задачи
    await stop_kafka(consumer, producer)                  # R-SHUT-KFK-1/4: commit + flush
    await container.engine().dispose()                    # R-SHUT-DB-1: пул закрываем ПОСЛЕ дренажа, не раньше (R-SHUT-DB-X1)
    log.info("shutdown_complete")                          # R-SHUT-OBS-X1: нормальное закрытие — INFO, не ERROR
```

## 5. Scheduled / async / outbox (`R-SHUT-SCHED-*`)

`graceful-shutdown/background-tasks-finish-iteration` — фоновые asyncio-задачи/APScheduler завершают текущую итерацию: на shutdown — `task.cancel()` +
`await` с дожатием (или `scheduler.shutdown(wait=True)`), не оставлять незавершённые. `graceful-shutdown/background-tasks-finish-iteration` — долгий async
cascade — корректная обработка `asyncio.CancelledError` (дожать критичную секцию, затем re-raise). `graceful-shutdown/outbox-relay-checks-readiness` —
outbox-relay завершает текущий batch (`FOR UPDATE SKIP LOCKED`), не начинает новый; цикл проверяет readiness-флаг,
не `while True`.

`graceful-shutdown/background-tasks-finish-iteration` — отмена фоновых задач без дожатия/обработки `CancelledError` — частичные изменения без rollback
(inconsistent state).

```python
import asyncio
import contextlib

# R-SHUT-SCHED-3: outbox-relay цикл проверяет readiness, не while True; завершает текущий batch, не начинает новый.
async def outbox_relay_loop(relay: OutboxRelay, state: ReadinessState) -> None:
    while state.is_ready():                                # на shutdown readiness снят → новый batch не начинаем
        try:
            await relay.run_once(batch=50)                 # FOR UPDATE SKIP LOCKED — текущий batch дожимается
        except asyncio.CancelledError:
            # R-SHUT-SCHED-2: дожать критичную секцию (commit текущего batch), затем re-raise.
            await relay.finish_current_batch()
            raise                                          # пробрасываем — иначе задача не завершится
        await asyncio.sleep(1)

# R-SHUT-SCHED-1: на shutdown — task.cancel() + await с обработкой CancelledError (не оставлять незавершённые).
async def stop_background_task(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):      # ожидаем дожатие; X1 — отмена без await = inconsistent state
        await task
```

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

`graceful-shutdown/shutdown-budget-is-explicit` — реалистичный cumulative-бюджет (preStop 10s + uvicorn graceful ≤25s + задачи ≤20s + Kafka ≤15s ≤
60s); не влезает — сократить scope (batch 100→20), не растить budget. `graceful-shutdown/shutdown-is-observable` — метрика
`app_shutdown_duration_seconds` + структурный лог начала/конца. `graceful-shutdown/shutdown-is-observable` — лог факта SIGTERM.

`graceful-shutdown/shutdown-is-observable` — логирование нормального закрытия пула/движка на ERROR (шум в alert-канале на каждый деплой) — INFO.

## 9. Чеклист подключения к новому сервису (Python)

1. uvicorn graceful + явный timeout; readiness→503 первым на SIGTERM; раздельные live/ready.
2. preStop sleep 10; in-flight HTTP дожимаются; долгие эндпоинты — 202+polling.
3. aiokafka consumer/producer `stop()` в lifespan-shutdown; manual commit; cascade в outbox.
4. `engine.dispose()` после дренажа, не раньше; транзакции завершаются своим каналом.
5. Фоновые задачи дожимают итерацию + обрабатывают `CancelledError`; outbox завершает batch.
6. k8s: grace 60s, preStop, probes на /health/{live,ready}, maxUnavailable 0.
7. in-flight retry-safe (idempotency-key/outbox); метрика+лог shutdown; нормальное закрытие не ERROR.
