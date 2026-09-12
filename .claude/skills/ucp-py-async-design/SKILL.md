---
name: ucp-py-async-design
lang: python
description: Спроектировать async-корректный код FastAPI-сервиса по UCP (требования async/*) — не блокировать event loop, структурированная конкурентность, отмена и таймауты, фоновые задачи в lifespan, сессия на задачу.
when_to_use: При написании async-хендлеров, адаптеров, фоновых задач и параллельных вызовов. Связан с bootstrap, scheduler, sqlalchemy.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование async-кода (Python / asyncio + FastAPI)

Ты пишешь async-корректный код согласно `backend/python/async/spec.md` (`PYASYNC-*`). Один поток, один event
loop: любой блокирующий вызов замораживает весь сервис; любая неотменённая задача — утечка/потеря ошибки.

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/async/spec.md` (`PYASYNC-*`). Связанные: `backend/scheduler/spec.md` (`R-JOB-*` — фоновая обработка), `backend/graceful-shutdown/...` (`R-SHUT-*` — останов задач), `backend/python/sqlalchemy/spec.md` (`R-SQLA-SESS-*` — сессии), `backend/resilience/spec.md` (`R-RES-TO-*` — таймауты).

2. **Произведи код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Не блокировать loop:** async-native клиенты (`httpx.AsyncClient`/`asyncpg`/`redis.asyncio`); блокирующее/CPU-bound — `await anyio.to_thread.run_sync(...)` / process-pool (`PYASYNC-1/2`).
   - **Конкурентность:** `asyncio.TaskGroup` (или `gather`) для параллельных await; долгоживущие задачи — в `lifespan` со ссылкой (`PYASYNC-3/4`).
   - **Отмена/таймауты:** `async with asyncio.timeout(...)` на внешние ожидания; `CancelledError` — только cleanup + `raise` (`PYASYNC-5/6`).
   - **Ресурсы:** `async with` для сессий/клиентов; на конкурентную задачу — своя `AsyncSession`/`AsyncClient` из фабрики (`PYASYNC-7/8`).

3. **Самопроверка** + предложи `ucp-py-async-review`. Фоновую обработку — `ucp-py-scheduler-design`; останов — `ucp-py-shutdown-review`.

## Антипаттерны, которые НЕ генерировать

- `requests`/`time.sleep`/sync-драйвер/`subprocess.run`/чтение большого файла в `async def` без offload (`async/no-blocking-in-event-loop`).
- `create_task` без сохранения ссылки (`async/background-task-owned-by-lifespan`); fire-and-forget важной работы на запрос (`async/no-fire-and-forget-for-important-work` — в очередь/scheduler).
- Глотание `CancelledError` (`async/cancellation-propagates`); безлимитный `await` без таймаута (`async/external-waits-have-timeouts`).
- Общий `AsyncSession` в `gather`/`TaskGroup` (`async/no-shared-resource-across-tasks`); `asyncio.run`/новый loop внутри запущенного loop (`async/no-nested-event-loop`).

После работы скилла — обязательно `ucp-py-async-review`.

$ARGUMENTS
