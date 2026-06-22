# Async — индекс правил (Python asyncio / FastAPI)

> **Что это.** Дисциплина asyncio в FastAPI-сервисе: не блокировать event loop, структурированная конкурентность,
> отмена/таймауты, жизненный цикл фоновых задач, async-ресурсы. Языко-специфичный concern (как `python-style` /
> `sqlalchemy`) — **только Python**, префикс `PYASYNC-*`. Скиллы читают этот файл; код-примеры включены.
> Коды: `PYASYNC-<N>` — обязательно, `PYASYNC-X<N>` — антипаттерн (запрещено).
> Сшивки: фоновые задачи/планировщик — `scheduler-rules.md` (`R-JOB-*`); останов задач — `graceful-shutdown`
> (`R-SHUT-*`); сессии — `sqlalchemy` (`R-SQLA-SESS-*`); таймауты исходящих — `resilience` (`R-RES-TO-*`).

Суть: один поток, один event loop. Любой **блокирующий** вызов в `async def` останавливает весь сервис; любая
**незавершённая/неотменённая** задача — утечка или потеря ошибки. Корректность async — это не «добавить `async`»,
а не блокировать loop и управлять жизненным циклом задач.

## 1. Не блокировать event loop
**MUST:**
- **PYASYNC-1.** Блокирующий I/O и CPU-bound в `async`-контексте — выносить с loop: I/O — `await anyio.to_thread.run_sync(...)` / `loop.run_in_executor(...)`; тяжёлый CPU — в процесс-пул/отдельный воркер.
- **PYASYNC-2.** Библиотеки — async-native в hot-path: `httpx.AsyncClient` (не `requests`), async-драйвер БД (`asyncpg`), `redis.asyncio`, `aiokafka`.

**MUST NOT:**
- **PYASYNC-X1.** Блокирующий вызов в `async def` без offload: `requests.get`, `time.sleep` (вместо `await asyncio.sleep`), sync-драйвер БД, `open(...).read()` большого файла, `subprocess.run`, тяжёлый `json`/crypto на больших данных — замораживают loop для всех запросов.

```python
import anyio

# PYASYNC-X1 — AVOID: блокирует loop для всех запросов
def handler_bad():
    data = requests.get(url).json()        # sync HTTP в async-сервисе
    time.sleep(1)                          # замораживает loop

# PYASYNC-1 — PREFER
async def handler_ok():
    data = (await client.get(url)).json()  # httpx.AsyncClient (PYASYNC-2)
    await asyncio.sleep(1)                  # не time.sleep
    result = await anyio.to_thread.run_sync(cpu_or_blocking_call, payload)  # offload блокирующего
```

## 2. Структурированная конкурентность
**MUST:**
- **PYASYNC-3.** Параллельные ожидания — через `asyncio.TaskGroup` (3.11+) или `asyncio.gather` с обработкой результатов/ошибок; дочерние задачи завершаются вместе с родителем.
- **PYASYNC-4.** Долгоживущая фоновая задача создаётся в `lifespan` и хранит ссылку; на остановку — `cancel()` + `await` (cross-ref `R-SHUT-*`, `R-JOB-*`).

**MUST NOT:**
- **PYASYNC-X2.** `asyncio.create_task(...)` без сохранения ссылки — задачу может собрать GC, исключение в ней теряется (нет `await`/`add_done_callback`).
- **PYASYNC-X3.** Fire-and-forget на запрос (`create_task` в эндпоинте без отслеживания) для важной работы — при падении воркера теряется; для фоновой работы — очередь/scheduler (`R-JOB-KIND-*`).

```python
# PYASYNC-3 — PREFER: TaskGroup (отмена остальных при ошибке любой)
async def load_all(ids: list[UUID]) -> list[Order]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_order(i)) for i in ids]
    return [t.result() for t in tasks]

# PYASYNC-X2 — AVOID
asyncio.create_task(send_email(user))      # ссылка не сохранена → GC/потеря исключения
```

## 3. Отмена и таймауты
**MUST:**
- **PYASYNC-5.** Внешние ожидания ограничены по времени: `async with asyncio.timeout(...)` / `asyncio.wait_for(...)` (cross-ref `R-RES-TO-*`).
- **PYASYNC-6.** `CancelledError` ловить только для очистки ресурсов — и **обязательно** перевозбуждать (`raise`); отмена должна доходить до верха.

**MUST NOT:**
- **PYASYNC-X4.** Глотать `asyncio.CancelledError` (`except CancelledError: pass` / `except Exception` без re-raise CancelledError) — ломает отмену и graceful shutdown.
- **PYASYNC-X5.** Безлимитный `await` на внешний ресурс без таймаута — зависший upstream держит соединение/воркер.

```python
# PYASYNC-5/6
async def call_provider(cmd):
    try:
        async with asyncio.timeout(5):           # PYASYNC-5: ограничение времени
            return await provider.charge(cmd)
    except asyncio.CancelledError:
        await provider.aclose()                  # очистка
        raise                                    # PYASYNC-X4: обязательный re-raise
```

## 4. Async-ресурсы
**MUST:**
- **PYASYNC-7.** Ресурсы (`AsyncSession`, `AsyncClient`, соединения) — через `async with`; не утекают при ошибке/отмене.
- **PYASYNC-8.** `AsyncSession`/`AsyncClient` не разделять между конкурентными задачами — на конкурентную работу свой объект (cross-ref `R-SQLA-SESS-2`).

**MUST NOT:**
- **PYASYNC-X6.** Один `AsyncSession` в `gather`/`TaskGroup` параллельно — `InvalidRequestError`/гонки; на задачу — своя сессия из фабрики.
- **PYASYNC-X7.** `asyncio.run(...)` / новый event loop внутри уже запущенного loop (FastAPI-хендлер) — `RuntimeError`; sync-границу проходить через executor.

```python
# PYASYNC-X6 — AVOID: общая сессия в конкурентных задачах
async with session.begin():
    await asyncio.gather(repo.a(session), repo.b(session))   # гонка по одной сессии

# PYASYNC-8 — PREFER: своя сессия на задачу
async def work(factory):
    async with factory() as s, s.begin():
        await repo.a(s)
await asyncio.gather(work(factory), work(factory))
```

## Чеклист подключения к новому сервису (Python / FastAPI)

- [ ] В hot-path нет sync I/O/`time.sleep`/sync-драйверов; блокирующее — через `anyio.to_thread`/executor.
- [ ] Параллелизм — `TaskGroup`/`gather`; нет «осиротевших» `create_task` без ссылки.
- [ ] Фоновые задачи — в `lifespan`, с `cancel()`+`await` на shutdown.
- [ ] Внешние `await` — под `asyncio.timeout`; `CancelledError` re-raise, не глотается.
- [ ] Ресурсы — `async with`; на конкурентную задачу — своя `AsyncSession`/`AsyncClient`.
- [ ] Нет `asyncio.run`/нового loop внутри запущенного loop.
