---
name: ucp-py-scheduler-design
lang: python
description: Спроектировать фоновую обработку FastAPI-сервиса по UCP (коды R-JOB-*) — work queue на БД-as-queue (FOR UPDATE SKIP LOCKED) и/или периодику через внешний Celery-beat → internal HTTP → Dispatcher, идемпотентность read-before-write, retry+DLQ, recovery зависших, UTC tz-aware, метрики. Триггеры — «фоновая задача», «периодический прогон», «очередь задач», «шедулер на FastAPI».
when_to_use: После ucp-py-pattern-design (есть Dispatcher/UseCase) и ucp-py-sqlalchemy-design (есть репозиторий). Когда нужно периодически обрабатывать записи, чистить просроченное, ретраить операции.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование фоновой обработки (Python / FastAPI, БД-as-queue + Celery-beat)

Ты проектируешь фоновую работу согласно `backend/scheduler/scheduler-rules.md` (`R-JOB-*`) и
`backend/scheduler/python/scheduler-style-guide.md`. Фоновая работа — **at-least-once**: корректность держится
на идемпотентности и атомарном захвате, а не на «ровно один раз» и не на «воркер один».

## Инструкции

1. **Прочитай** `.claude/docs/backend/scheduler/scheduler-rules.md` (`R-JOB-*`) и `.claude/docs/backend/scheduler/python/scheduler-style-guide.md`. Связанные: `backend/distributed-patterns/distributed-patterns-rules.md` (`R-DIST-IDEM-*`), `backend/resilience/resilience-rules.md` (`R-RES-RETRY-*` — backoff/DLQ), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-*` — claim-запрос, типы времени), `backend/pg-runtime/pg-runtime-rules.md` (`PG-W-*` — SKIP LOCKED), `backend/observability/observability-rules.md` (`R-OBS-*`).

2. **Определи ось задачи** (`R-JOB-KIND-1`): work queue (что делать), periodic tick (когда), event-retry, или after-response side-effect. Не смешивай их в один механизм.

3. **Произведи дизайн/код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Work queue** — `claim_due(*, limit, now)` в репозитории через `select(...).with_for_update(skip_locked=True).limit(...)`; хендлер обрабатывает батч, каждую единицу — идемпотентно (`R-JOB-DUP-1`, `R-JOB-IDEM-1`).
   - **Periodic tick** — внешний Celery-beat (или k8s CronJob `Forbid`), который делает `POST /internal/jobs/<name>` (`APIRouter(include_in_schema=False)`); эндпоинт делегирует в `Dispatcher` (`R-JOB-DUP-2`). Async-логика — в хендлере, не внутри Celery-task.
   - **Идемпотентность** — read-before-write по natural-key перед внешним вызовом (`R-JOB-IDEM-2`).
   - **Надёжность** — retry+backoff, DLQ после лимита, recovery зависших по visibility-timeout; транспортная ошибка → повтор, бизнес-ошибка → терминал (`R-JOB-REL-1/2/3`).
   - **Время/конфиг** — `datetime.now(timezone.utc)`, `DateTime(timezone=True)`; параметры через `pydantic-settings` (`R-JOB-TIME-1`, `R-JOB-CFG-1`).
   - **Метрики/логи** — processed/duration/queue-depth/lag + structlog correlation-id (`R-JOB-OBS-*`).

4. **Самопроверка** + предложи `ucp-py-scheduler-review`.

## Антипаттерны, которые НЕ генерировать

- In-process `APScheduler`/`while True`-loop в каждой реплике без leader-election (`R-JOB-DUP-X1`); расчёт «воркер один» вместо claim (`R-JOB-DUP-X2`).
- `BackgroundTasks`/in-memory для денег/периодики/гарантий (`R-JOB-KIND-X1`); опора на exactly-once вместо идемпотентности (`R-JOB-IDEM-X1`).
- Blocking `asyncio.sleep`-retry, удерживающий claim (`R-JOB-REL-X1`); recovery, возвращающий в общую очередь занятую другой репликой единицу (`R-JOB-REL-X2`).
- Naive `datetime.now()` для cutoff/TTL (`R-JOB-TIME-X1`); async-логика и async SQLAlchemy внутри sync Celery-task.

После работы скилла — обязательно `ucp-py-scheduler-review`.

$ARGUMENTS
