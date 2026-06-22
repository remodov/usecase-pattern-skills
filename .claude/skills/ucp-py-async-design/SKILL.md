---
name: ucp-py-async-design
lang: python
description: Спроектировать async-корректный код FastAPI-сервиса по UCP (коды PYASYNC-*) — не блокировать event loop (anyio.to_thread/run_in_executor, async-native httpx/asyncpg/redis.asyncio), структурированная конкурентность (TaskGroup/gather), отмена/таймауты (asyncio.timeout, CancelledError re-raise), жизненный цикл фоновых задач (lifespan), async-ресурсы (своя AsyncSession на задачу). Триггеры — «асинхронный X», «параллельные вызовы», «блокирует event loop», «фоновая корутина».
when_to_use: При написании async-хендлеров/адаптеров/фоновых задач, параллельных вызовов, интеграции sync-кода. Связан с bootstrap (lifespan), scheduler (фоновые), sqlalchemy (сессии).
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование async-кода (Python / asyncio + FastAPI)

Ты пишешь async-корректный код согласно `backend/python/async/async-rules.md` (`PYASYNC-*`). Один поток, один event
loop: любой блокирующий вызов замораживает весь сервис; любая неотменённая задача — утечка/потеря ошибки.

## Инструкции

1. **Прочитай** `.claude/docs/backend/python/async/async-rules.md` (`PYASYNC-*`). Связанные: `backend/scheduler/scheduler-rules.md` (`R-JOB-*` — фоновая обработка), `backend/graceful-shutdown/...` (`R-SHUT-*` — останов задач), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-SESS-*` — сессии), `backend/resilience/resilience-rules.md` (`R-RES-TO-*` — таймауты).

2. **Произведи код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Не блокировать loop:** async-native клиенты (`httpx.AsyncClient`/`asyncpg`/`redis.asyncio`); блокирующее/CPU-bound — `await anyio.to_thread.run_sync(...)` / process-pool (`PYASYNC-1/2`).
   - **Конкурентность:** `asyncio.TaskGroup` (или `gather`) для параллельных await; долгоживущие задачи — в `lifespan` со ссылкой (`PYASYNC-3/4`).
   - **Отмена/таймауты:** `async with asyncio.timeout(...)` на внешние ожидания; `CancelledError` — только cleanup + `raise` (`PYASYNC-5/6`).
   - **Ресурсы:** `async with` для сессий/клиентов; на конкурентную задачу — своя `AsyncSession`/`AsyncClient` из фабрики (`PYASYNC-7/8`).

3. **Самопроверка** + предложи `ucp-py-async-review`. Фоновую обработку — `ucp-py-scheduler-design`; останов — `ucp-py-shutdown-review`.

## Антипаттерны, которые НЕ генерировать

- `requests`/`time.sleep`/sync-драйвер/`subprocess.run`/чтение большого файла в `async def` без offload (`PYASYNC-X1`).
- `create_task` без сохранения ссылки (`PYASYNC-X2`); fire-and-forget важной работы на запрос (`PYASYNC-X3` — в очередь/scheduler).
- Глотание `CancelledError` (`PYASYNC-X4`); безлимитный `await` без таймаута (`PYASYNC-X5`).
- Общий `AsyncSession` в `gather`/`TaskGroup` (`PYASYNC-X6`); `asyncio.run`/новый loop внутри запущенного loop (`PYASYNC-X7`).

После работы скилла — обязательно `ucp-py-async-review`.

$ARGUMENTS
