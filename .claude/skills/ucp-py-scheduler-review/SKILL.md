---
name: ucp-py-scheduler-review
lang: python
description: Проверить фоновую обработку FastAPI-сервиса по UCP (коды R-JOB-*) — корректный выбор механизма (work queue vs periodic vs after-response), идемпотентность read-before-write, антидубли на репликах (FOR UPDATE SKIP LOCKED, beat-singleton), отсутствие in-process APScheduler без leader-election, retry+DLQ+recovery, UTC tz-aware время, pydantic-settings, метрики queue-depth/lag. Вызывается на ревью фоновых хендлеров, /internal/jobs роутеров, claim-запросов, celery-beat конфигов, Redis-консьюмеров.
allowed-tools: Read Glob Grep
---

# Ревью фоновой обработки (Python / FastAPI, БД-as-queue + Celery-beat)

Ты проверяешь фоновую работу против `backend/scheduler/scheduler-rules.md` (`R-JOB-*`) и
`backend/scheduler/python/scheduler-style-guide.md`. Формат findings — `shared/review-finding-format.md` (`RFF-*`).

## Процесс ревью

1. **Прочитай** `.claude/docs/backend/scheduler/scheduler-rules.md` (`R-JOB-*`), `.claude/docs/backend/scheduler/python/scheduler-style-guide.md` и `.claude/docs/shared/review-finding-format.md`. Связанные: `R-DIST-IDEM-*`, `R-RES-RETRY-*`, `R-SQLA-*`, `PG-W-*`, `R-OBS-*`.

2. **Определи объект:** фоновые хендлеры/UseCase периодики, `/internal/jobs/*` роутеры, claim-запросы репозитория, celery-beat/CronJob конфиги, Redis reliable-queue консьюмеры.

3. **Проверь по подгруппам кодов** (цитируй коды в findings):
   - **KIND** (`R-JOB-KIND-*`): механизм соответствует природе; нет `BackgroundTasks`/in-memory для денег/периодики/гарантий (`X1`).
   - **IDEM** (`R-JOB-IDEM-*`): job идемпотентен; read-before-write по natural-key; нет опоры на exactly-once (`X1`).
   - **DUP** (`R-JOB-DUP-*`): claim через `with_for_update(skip_locked=True)`; периодика — один источник тика (внешний beat single-instance / CronJob Forbid / leader-election). Нет in-process `APScheduler`/`while`-loop в репликах без координации (`X1`); нет расчёта «воркер один» (`X2`).
   - **REL** (`R-JOB-REL-*`): retry+backoff+DLQ; recovery зависших по visibility-timeout; транспорт→повтор / бизнес→терминал. Нет blocking sleep-retry под claim (`X1`); Redis processing-list/recover — per-replica, не общий (`X2`).
   - **TIME/CFG** (`R-JOB-TIME-*`, `R-JOB-CFG-*`): UTC tz-aware cutoff/TTL, `DateTime(timezone=True)`; параметры через `pydantic-settings`. Нет naive `datetime.now()` (`X1`).
   - **OBS** (`R-JOB-OBS-*`): метрики processed/duration/queue-depth/lag; structlog correlation-id.

4. **Частые реальные дефекты** (приоритет при ревью): naive `datetime.now()` для TTL-cutoff; async-логика/async SQLAlchemy внутри sync Celery-task (вместо task→HTTP); in-process планировщик в каждой реплике; Redis `recover()` с общим processing-list (двойная обработка); самописный `os.environ`-Settings вместо `pydantic-settings`.

5. **Выдай findings** по `RFF-*` (severity, код, файл:строка, фикс) и предложи парный `ucp-py-scheduler-design` для исправлений.

## Что не входит

- Сам retry/CB-механизм по существу — `ucp-py-resilience-review`. Транзакции/изоляция/locks на уровне PG — `ucp-pg-runtime-review`. Контракт `/internal/jobs/*` как REST — `ucp-py-api-review` (но эти эндпоинты внутренние, `include_in_schema=False`).

$ARGUMENTS
