---
name: ucp-py-shutdown-review
lang: python
description: Ревью graceful shutdown Python/FastAPI-сервиса по UCP (требования graceful-shutdown/*) — uvicorn graceful timeout, readiness→503 на SIGTERM, aiokafka stop() в lifespan, engine.dispose() после дренажа, фоновые задачи и CancelledError, k8s preStop.
when_to_use: Изменения в lifespan-shutdown, signal-хендлерах, k8s-манифестах или фоновых asyncio-задачах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Graceful Shutdown (Python / uvicorn + lifespan + asyncio)

Ты ревьюишь корректное завершение на соответствие **контракту** `backend/graceful-shutdown/spec.md`
(`R-SHUT-*`) и **Python-реализации** `backend/graceful-shutdown/references/python/implementation.md`.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/spec.md`** + **`backend/graceful-shutdown/references/python/implementation.md`**.
- Парные: `backend/python/python-bootstrap/...` (`python-bootstrap/liveness-and-readiness-split` health, lifespan), `backend/kafka/python/...` (consumer stop), `observability` (readiness/метрики), `auth-patterns` (`auth-patterns/money-commands-need-idempotency-key` идемпотентность).

## Инструкции

1. **Прочти** требования `python-style/*`. Цитируй коды (`graceful-shutdown/connection-pool-closes-last`, `graceful-shutdown/background-tasks-finish-iteration`), не префикс.

2. **Скоп.** `lifespan`-shutdown, signal-хендлеры, uvicorn-запуск/конфиг, фоновые asyncio-задачи/APScheduler, outbox-relay, k8s-манифесты (Deployment), health-эндпоинты; `git diff`.

3. **Прогон.**
   - **Базовое (`R-SHUT-1..3`):** readiness-флаг приложения — единый источник (свой `bool` не связанный с health → `graceful-shutdown/readiness-off-first`); budget 60s.
   - **Runtime (`R-SHUT-CFG-*`):** uvicorn graceful + явный timeout (`R-SHUT-CFG-1/2`); readiness→503 первым (`graceful-shutdown/readiness-off-first`); раздельные live/ready (`graceful-shutdown/readiness-off-first`).
   - **HTTP (`R-SHUT-HTTP-*`):** preStop sleep (нет → `graceful-shutdown/prestop-delay`); `timeout-graceful-shutdown 0`/форс-kill → `graceful-shutdown/web-server-graceful-enabled`; долгие эндпоинты — 202+polling.
   - **Kafka (`R-SHUT-KFK-*`):** `consumer.stop()`/`producer.stop()` в lifespan-shutdown; manual commit; `enable_auto_commit=True` → `graceful-shutdown/consumer-finishes-batch`.
   - **БД (`R-SHUT-DB-*`):** `engine.dispose()` **после** дренажа; до завершения задач → `graceful-shutdown/connection-pool-closes-last`.
   - **Async/outbox (`R-SHUT-SCHED-*`):** задачи дожимают итерацию + обрабатывают `CancelledError`; отмена без дожатия → `graceful-shutdown/background-tasks-finish-iteration`; outbox завершает batch, проверяет readiness, не `while True`.
   - **k8s (`R-SHUT-K8S-*`):** grace 60s (default 30 при 30s graceful → `graceful-shutdown/shutdown-budget-is-explicit`); preStop (нет → `graceful-shutdown/prestop-delay`); probes на /health/{live,ready}; maxUnavailable 0.
   - **Идемпотентность (`R-SHUT-IDEM-*`):** in-flight write retry-safe; money без `Idempotency-Key` под retry → `graceful-shutdown/in-flight-operations-are-retry-safe`.
   - **Observability (`R-SHUT-OBS-*`):** метрика+лог shutdown; нормальное закрытие пула на ERROR → `graceful-shutdown/shutdown-is-observable`.

4. **Cross-check:** lifespan/health-wiring — `ucp-py-bootstrap-review`; aiokafka stop — `ucp-py-kafka-review`; idempotency — `ucp-py-distributed-review`/`ucp-py-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-format/spec.md` (`review-format/*`), Read-проверка строки обязательна.

6. **Серьёзность** (`review-format/severity-scale-is-shared`):
   - **Критично** — нет uvicorn graceful (`graceful-shutdown/web-server-graceful-enabled`), `engine.dispose()` до завершения задач (`graceful-shutdown/connection-pool-closes-last`), отмена фоновых задач без дожатия (`graceful-shutdown/background-tasks-finish-iteration`), `enable_auto_commit=True` (`graceful-shutdown/consumer-finishes-batch`), money без idempotency под retry (`graceful-shutdown/in-flight-operations-are-retry-safe`), нет preStop (`graceful-shutdown/prestop-delay`).
   - **Предупреждение** — свой `bool` вместо readiness-состояния (`graceful-shutdown/readiness-off-first`), grace 30s при 30s graceful (`graceful-shutdown/shutdown-budget-is-explicit`), consumer/producer не закрыты в lifespan, нет раздельных probes.
   - **Замечание** — нет метрики `app_shutdown_duration_seconds` (`graceful-shutdown/shutdown-is-observable`), нормальное закрытие на ERROR (`graceful-shutdown/shutdown-is-observable`), долгий синхронный эндпоинт без 202.

## Что не входит

- lifespan/health/DI-композиция — `ucp-py-bootstrap-review`. aiokafka commit/offset — `ucp-py-kafka-review`.
- Идемпотентность-таблицы/saga — `ucp-py-distributed-review`. Idempotency-Key контракт — `ucp-py-auth-review`.

$ARGUMENTS
