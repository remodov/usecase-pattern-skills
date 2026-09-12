---
name: ucp-py-scheduler-design
lang: python
description: Спроектировать фоновую обработку FastAPI-сервиса по UCP (требования scheduler/*) — очередь на БД с SKIP LOCKED, периодика через внешний beat, идемпотентность, retry и DLQ, recovery зависших, UTC.
when_to_use: После ucp-py-pattern-design и ucp-py-sqlalchemy-design. Триггеры — «фоновая задача», «периодический прогон», «очередь задач».
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование фоновой обработки (Python / FastAPI, БД-as-queue + Celery-beat)

Ты проектируешь фоновую работу согласно `backend/scheduler/spec.md` (`R-JOB-*`) и
`backend/scheduler/references/python/implementation.md`. Фоновая работа — **at-least-once**: корректность держится
на идемпотентности и атомарном захвате, а не на «ровно один раз» и не на «воркер один».

## Инструкции

1. **Прочитай** `.claude/docs/backend/scheduler/spec.md` (`R-JOB-*`) и `.claude/docs/backend/scheduler/references/python/implementation.md`. Связанные: `backend/distributed-patterns/spec.md` (`R-DIST-IDEM-*`), `backend/resilience/spec.md` (`R-RES-RETRY-*` — backoff/DLQ), `backend/python/sqlalchemy/spec.md` (`R-SQLA-*` — claim-запрос, типы времени), `backend/pg-runtime/spec.md` (`PG-W-*` — SKIP LOCKED), `backend/observability/spec.md` (`R-OBS-*`).

2. **Определи ось задачи** (`scheduler/mechanism-matches-work`): work queue (что делать), periodic tick (когда), event-retry, или after-response side-effect. Не смешивай их в один механизм.

3. **Произведи дизайн/код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Work queue** — `claim_due(*, limit, now)` в репозитории через `select(...).with_for_update(skip_locked=True).limit(...)`; хендлер обрабатывает батч, каждую единицу — идемпотентно (`scheduler/work-unit-claimed-atomically`, `scheduler/job-is-idempotent`).
   - **Periodic tick** — внешний Celery-beat (или k8s CronJob `Forbid`), который делает `POST /internal/jobs/<name>` (`APIRouter(include_in_schema=False)`); эндпоинт делегирует в `Dispatcher` (`scheduler/single-source-of-tick`). Async-логика — в хендлере, не внутри Celery-task.
   - **Идемпотентность** — read-before-write по natural-key перед внешним вызовом (`scheduler/read-before-write-by-natural-key`).
   - **Надёжность** — retry+backoff, DLQ после лимита, recovery зависших по visibility-timeout; транспортная ошибка → повтор, бизнес-ошибка → терминал (`R-JOB-REL-1/2/3`).
   - **Время/конфиг** — `datetime.now(timezone.utc)`, `DateTime(timezone=True)`; параметры через `pydantic-settings` (`scheduler/time-is-timezone-aware`, `scheduler/job-parameters-are-typed-config`).
   - **Метрики/логи** — processed/duration/queue-depth/lag + structlog correlation-id (`R-JOB-OBS-*`).

4. **Самопроверка** + предложи `ucp-py-scheduler-review`.

## Антипаттерны, которые НЕ генерировать

- In-process `APScheduler`/`while True`-loop в каждой реплике без leader-election (`scheduler/single-source-of-tick`); расчёт «воркер один» вместо claim (`scheduler/work-unit-claimed-atomically`).
- `BackgroundTasks`/in-memory для денег/периодики/гарантий (`scheduler/mechanism-matches-work`); опора на exactly-once вместо идемпотентности (`scheduler/job-is-idempotent`).
- Blocking `asyncio.sleep`-retry, удерживающий claim (`scheduler/bounded-retries-then-parking`); recovery, возвращающий в общую очередь занятую другой репликой единицу (`scheduler/stuck-claims-are-recovered`).
- Naive `datetime.now()` для cutoff/TTL (`scheduler/time-is-timezone-aware`); async-логика и async SQLAlchemy внутри sync Celery-task.

После работы скилла — обязательно `ucp-py-scheduler-review`.

$ARGUMENTS
