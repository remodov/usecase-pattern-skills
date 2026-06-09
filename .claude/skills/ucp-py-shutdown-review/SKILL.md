---
name: ucp-py-shutdown-review
lang: python
description: Ревью graceful shutdown Python/FastAPI-сервиса по UCP (коды R-SHUT-*) — uvicorn graceful timeout, readiness→503 на SIGTERM, aiokafka stop() в lifespan, engine.dispose() после дренажа, фоновые задачи и CancelledError, k8s preStop.
when_to_use: Изменения в lifespan-shutdown, signal-хендлерах, k8s-манифестах или фоновых asyncio-задачах.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Graceful Shutdown (Python / uvicorn + lifespan + asyncio)

Ты ревьюишь корректное завершение на соответствие **контракту** `backend/graceful-shutdown/graceful-shutdown-rules.md`
(`R-SHUT-*`) и **Python-реализации** `backend/graceful-shutdown/python/graceful-shutdown-style-guide.md`.

## Зависимости

- **`.claude/docs/backend/graceful-shutdown/graceful-shutdown-rules.md`** + **`backend/graceful-shutdown/python/graceful-shutdown-style-guide.md`**.
- Парные: `backend/python/python-bootstrap/...` (`PYBOOT-13` health, lifespan), `backend/kafka/python/...` (consumer stop), `observability` (readiness/метрики), `auth-patterns` (`AUTH-19` идемпотентность).

## Инструкции

1. **Прочти** контракт + Python-style-guide. Цитируй коды (`R-SHUT-DB-X1`, `R-SHUT-SCHED-X1`), не префикс.

2. **Скоп.** `lifespan`-shutdown, signal-хендлеры, uvicorn-запуск/конфиг, фоновые asyncio-задачи/APScheduler, outbox-relay, k8s-манифесты (Deployment), health-эндпоинты; `git diff`.

3. **Прогон.**
   - **Базовое (`R-SHUT-1..3`):** readiness-флаг приложения — единый источник (свой `bool` не связанный с health → `R-SHUT-CFG-X1`); budget 60s.
   - **Runtime (`R-SHUT-CFG-*`):** uvicorn graceful + явный timeout (`R-SHUT-CFG-1/2`); readiness→503 первым (`R-SHUT-CFG-3`); раздельные live/ready (`R-SHUT-CFG-4`).
   - **HTTP (`R-SHUT-HTTP-*`):** preStop sleep (нет → `R-SHUT-K8S-X1`); `timeout-graceful-shutdown 0`/форс-kill → `R-SHUT-HTTP-X1`; долгие эндпоинты — 202+polling.
   - **Kafka (`R-SHUT-KFK-*`):** `consumer.stop()`/`producer.stop()` в lifespan-shutdown; manual commit; `enable_auto_commit=True` → `R-SHUT-KFK-X1`.
   - **БД (`R-SHUT-DB-*`):** `engine.dispose()` **после** дренажа; до завершения задач → `R-SHUT-DB-X1`.
   - **Async/outbox (`R-SHUT-SCHED-*`):** задачи дожимают итерацию + обрабатывают `CancelledError`; отмена без дожатия → `R-SHUT-SCHED-X1`; outbox завершает batch, проверяет readiness, не `while True`.
   - **k8s (`R-SHUT-K8S-*`):** grace 60s (default 30 при 30s graceful → `R-SHUT-K8S-X2`); preStop (нет → `R-SHUT-K8S-X1`); probes на /health/{live,ready}; maxUnavailable 0.
   - **Идемпотентность (`R-SHUT-IDEM-*`):** in-flight write retry-safe; money без `Idempotency-Key` под retry → `R-SHUT-IDEM-X1`.
   - **Observability (`R-SHUT-OBS-*`):** метрика+лог shutdown; нормальное закрытие пула на ERROR → `R-SHUT-OBS-X1`.

4. **Cross-check:** lifespan/health-wiring — `ucp-py-bootstrap-review`; aiokafka stop — `ucp-py-kafka-review`; idempotency — `ucp-py-distributed-review`/`ucp-py-auth-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — нет uvicorn graceful (`R-SHUT-CFG-1`), `engine.dispose()` до завершения задач (`R-SHUT-DB-X1`), отмена фоновых задач без дожатия (`R-SHUT-SCHED-X1`), `enable_auto_commit=True` (`R-SHUT-KFK-X1`), money без idempotency под retry (`R-SHUT-IDEM-X1`), нет preStop (`R-SHUT-K8S-X1`).
   - **Предупреждение** — свой `bool` вместо readiness-состояния (`R-SHUT-CFG-X1`), grace 30s при 30s graceful (`R-SHUT-K8S-X2`), consumer/producer не закрыты в lifespan, нет раздельных probes.
   - **Замечание** — нет метрики `app_shutdown_duration_seconds` (`R-SHUT-OBS-2`), нормальное закрытие на ERROR (`R-SHUT-OBS-X1`), долгий синхронный эндпоинт без 202.

## Что не входит

- lifespan/health/DI-композиция — `ucp-py-bootstrap-review`. aiokafka commit/offset — `ucp-py-kafka-review`.
- Идемпотентность-таблицы/saga — `ucp-py-distributed-review`. Idempotency-Key контракт — `ucp-py-auth-review`.

$ARGUMENTS
