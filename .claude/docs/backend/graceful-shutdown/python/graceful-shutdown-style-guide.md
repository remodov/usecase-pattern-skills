# Graceful Shutdown — Python Style Guide (uvicorn + lifespan + asyncio)

Реализация язык-нейтрального контракта `../graceful-shutdown-rules.md` (`R-SHUT-*`) на FastAPI/uvicorn. Коды общие
с Java; механизм: вместо Spring graceful + `ApplicationAvailability` — **uvicorn graceful shutdown** +
**lifespan-shutdown** + readiness-флаг в `contextvar`/состоянии приложения. K8s-часть (`R-SHUT-K8S-*`) нейтральна.

`R-SHUT-1` — на SIGTERM сервис завершается без потерь: in-flight HTTP дожимаются, Kafka-offset коммитится, фоновые
asyncio-задачи доводят итерацию, БД-транзакции commit/rollback. `R-SHUT-2` — total budget 60s
(`terminationGracePeriodSeconds: 60`); внутри — preStop + uvicorn graceful + Kafka + БД. `R-SHUT-3` — единый источник
состояния — readiness-флаг приложения (не разрозненные `bool`); SIGTERM переводит readiness в `not ready`, `/health/
ready` → 503, k8s убирает pod из endpoints.

## 1. Runtime/конфигурация (`R-SHUT-CFG-*`)

`R-SHUT-CFG-1` — uvicorn graceful обязателен: `--timeout-graceful-shutdown 30` (или `Server.should_exit`); без него
активные запросы рвутся. `R-SHUT-CFG-2` — graceful-timeout явный (20–45s, чтобы влезть в 60s). `R-SHUT-CFG-3` —
shutdown-хендлер первым переводит readiness в 503 (в `lifespan`-shutdown или signal-handler). `R-SHUT-CFG-4` —
раздельные `/health/live` + `/health/ready` (cross-ref `PYBOOT-13`, `R-OBS-HC-1`).

`R-SHUT-CFG-X1` — свой `shutting_down: bool` вместо readiness-состояния приложения, не связанный с health (k8s не
узнает).

## 2. HTTP drain (`R-SHUT-HTTP-*`)

`R-SHUT-HTTP-1` — in-flight HTTP дожимаются (uvicorn graceful). `R-SHUT-HTTP-2` — **preStop `sleep 10`** обязателен
даже при graceful (k8s шлёт SIGTERM до распространения «убрать из endpoints»). `R-SHUT-HTTP-3` — долгие синхронные
эндпоинты (>10s) — `202 Accepted` + polling / задача (`AUTH-19`).

`R-SHUT-HTTP-X1` — `--timeout-graceful-shutdown 0` / форсированный kill воркеров — аннулирует graceful.

## 3. Kafka shutdown (`R-SHUT-KFK-*`)

`R-SHUT-KFK-1` — aiokafka consumer на остановке коммитит offset и закрывается (`await consumer.stop()` в lifespan-
shutdown; не оставлять задачу висеть). `R-SHUT-KFK-2` — listener не запускает долгий cascade (в async-flow/outbox).
`R-SHUT-KFK-3` — manual commit после обработки (cross-ref `R-KFK-CONS-2`). `R-SHUT-KFK-4` — `await producer.stop()`
(flush + close) на shutdown.

`R-SHUT-KFK-X1` — `enable_auto_commit=True` (потеря/дубль; запрещено `R-KFK-CONS-X1`).

## 4. БД и persistence (`R-SHUT-DB-*`)

`R-SHUT-DB-1` — `engine.dispose()` (закрытие пула SQLAlchemy) в lifespan-shutdown **после** дренажа HTTP/задач, не
раньше. `R-SHUT-DB-2` — активные транзакции завершаются своим каналом (HTTP — graceful, фон — отмена с дожатием
итерации). `R-SHUT-DB-3` — Alembic не запускается на shutdown (это startup).

`R-SHUT-DB-X1` — `engine.dispose()` в начале shutdown, до завершения фоновых задач (закроет пул под работающими тасками).

## 5. Scheduled / async / outbox (`R-SHUT-SCHED-*`)

`R-SHUT-SCHED-1` — фоновые asyncio-задачи/APScheduler завершают текущую итерацию: на shutdown — `task.cancel()` +
`await` с дожатием (или `scheduler.shutdown(wait=True)`), не оставлять незавершённые. `R-SHUT-SCHED-2` — долгий async
cascade — корректная обработка `asyncio.CancelledError` (дожать критичную секцию, затем re-raise). `R-SHUT-SCHED-3` —
outbox-relay завершает текущий batch (`FOR UPDATE SKIP LOCKED`), не начинает новый; цикл проверяет readiness-флаг,
не `while True`.

`R-SHUT-SCHED-X1` — отмена фоновых задач без дожатия/обработки `CancelledError` — частичные изменения без rollback
(inconsistent state).

## 6. Kubernetes (`R-SHUT-K8S-*`, нейтрально)

`R-SHUT-K8S-1` — `terminationGracePeriodSeconds: 60` явно; preStop — бюджет сверху. `R-SHUT-K8S-2` —
`readinessProbe` → `/health/ready`, `livenessProbe` → `/health/live`; на shutdown readiness=503 (liveness-падение
рестартит pod). `R-SHUT-K8S-3` — `maxSurge: 1, maxUnavailable: 0` (нулевой downtime).

`R-SHUT-K8S-X1` — отсутствие preStop (5–15s трафика на умирающий pod → 502). `R-SHUT-K8S-X2` — default
`terminationGracePeriodSeconds: 30` при 30s graceful (SIGKILL посреди дренажа).

## 7. Идемпотентность in-flight (`R-SHUT-IDEM-*`)

`R-SHUT-IDEM-1` — операции, которые SIGTERM может прервать, retry-safe: write с `Idempotency-Key`, money-cascade в
task-queue, Kafka-handler через outbox + `processed_event` дедуп (сшивка с `AUTH-19`, `R-DIST-IDEM`).

`R-SHUT-IDEM-X1` — money-операция без `Idempotency-Key` под retry (SIGTERM в момент retry → двойное списание;
запрещено `R-RES-RE-X1`).

## 8. Бюджеты и observability (`R-SHUT-OBS-*`)

`R-SHUT-OBS-1` — реалистичный cumulative-бюджет (preStop 10s + uvicorn graceful ≤25s + задачи ≤20s + Kafka ≤15s ≤
60s); не влезает — сократить scope (batch 100→20), не растить budget. `R-SHUT-OBS-2` — метрика
`app_shutdown_duration_seconds` + структурный лог начала/конца. `R-SHUT-OBS-3` — лог факта SIGTERM.

`R-SHUT-OBS-X1` — логирование нормального закрытия пула/движка на ERROR (шум в alert-канале на каждый деплой) — INFO.

## 9. Чеклист подключения к новому сервису (Python)

1. uvicorn graceful + явный timeout; readiness→503 первым на SIGTERM; раздельные live/ready.
2. preStop sleep 10; in-flight HTTP дожимаются; долгие эндпоинты — 202+polling.
3. aiokafka consumer/producer `stop()` в lifespan-shutdown; manual commit; cascade в outbox.
4. `engine.dispose()` после дренажа, не раньше; транзакции завершаются своим каналом.
5. Фоновые задачи дожимают итерацию + обрабатывают `CancelledError`; outbox завершает batch.
6. k8s: grace 60s, preStop, probes на /health/{live,ready}, maxUnavailable 0.
7. in-flight retry-safe (idempotency-key/outbox); метрика+лог shutdown; нормальное закрытие не ERROR.
