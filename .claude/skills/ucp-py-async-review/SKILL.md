---
name: ucp-py-async-review
lang: python
description: Ревью async-корректности FastAPI-сервиса по UCP (коды PYASYNC-*) — блокирующие вызовы в event loop (requests/time.sleep/sync-драйверы/subprocess в async def), осиротевшие create_task, проглоченный CancelledError, отсутствие таймаутов, общий AsyncSession в gather, asyncio.run внутри loop, фоновые задачи без отмены в lifespan. Вызывается на ревью async-хендлеров, адаптеров, фоновых корутин, параллельных вызовов.
allowed-tools: Read Glob Grep
---

# Ревью async-кода (Python / asyncio + FastAPI)

Ты проверяешь async-корректность против `backend/python/async/async-rules.md` (`PYASYNC-*`). Формат findings —
`shared/review-finding-format.md` (`RFF-*`).

## Процесс ревью

1. **Прочитай** `.claude/docs/backend/python/async/async-rules.md` (`PYASYNC-*`) и `.claude/docs/shared/review-finding-format.md`. Связанные: `R-JOB-*`, `R-SHUT-*`, `R-SQLA-SESS-*`, `R-RES-TO-*`.

2. **Определи объект:** `async def`-хендлеры, out-adapter'ы, фоновые корутины/`lifespan`, места с `gather`/`create_task`/`run_in_executor`.

3. **Проверь по подгруппам кодов** (цитируй коды в findings):
   - **Блокировка loop** (`PYASYNC-1/2`): нет `requests`/`time.sleep`/sync-драйвера/`subprocess.run`/чтения большого файла в `async def` (`X1`); клиенты async-native.
   - **Конкурентность** (`PYASYNC-3/4`): параллелизм через `TaskGroup`/`gather`; нет `create_task` без ссылки (`X2`); fire-and-forget важной работы (`X3`) → очередь/scheduler; фоновые задачи в `lifespan` со ссылкой.
   - **Отмена/таймауты** (`PYASYNC-5/6`): внешние `await` под `asyncio.timeout` (нет `X5`); `CancelledError` re-raise, не глотается (`X4`).
   - **Ресурсы** (`PYASYNC-7/8`): `async with`; на конкурентную задачу своя `AsyncSession`/`AsyncClient` (нет общей в `gather` — `X6`); нет `asyncio.run`/нового loop внутри loop (`X7`).

4. **Частые реальные дефекты** (приоритет): sync-драйвер БД или `requests` в async-сервисе; `time.sleep`; `except Exception` глотающий `CancelledError`; `gather` на одной сессии; отсутствие таймаута на httpx-вызов; фоновая задача без `cancel()` на shutdown.

5. **Выдай findings** по `RFF-*` (severity, код, файл:строка, фикс) и предложи парный `ucp-py-async-design`.

## Что не входит

- Фоновая обработка/планировщик как паттерн — `ucp-py-scheduler-review`. Останов задач при shutdown — `ucp-py-shutdown-review`. Транзакции/сессии по существу — `ucp-py-sqlalchemy-review`. Retry/CB/таймаут-политики — `ucp-py-resilience-review`.

$ARGUMENTS
