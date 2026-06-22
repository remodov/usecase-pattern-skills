# Streaming & Real-time — Python Style Guide (FastAPI / Starlette)

Реализация контракта `../streaming-rules.md` (`R-STREAM-*`). Те же коды и разделы — здесь идиома на FastAPI/Starlette.
Стек: FastAPI `WebSocket`, `sse-starlette` (`EventSourceResponse`), `StreamingResponse`, `redis.asyncio` pub/sub для
fan-out. Async-дисциплина — по `python/async/async-rules.md` (`PYASYNC-*`).

## 1. Выбор механизма (`R-STREAM-1`)

| Природа | FastAPI-механизм |
|---|---|
| server→client поток (нотификации, прогресс) | **SSE** — `sse-starlette` `EventSourceResponse` |
| двунаправленный интерактив (чат, совместная сессия) | **WebSocket** — `@router.websocket` |
| разовая выгрузка большого тела (отчёт, файл) | **`StreamingResponse`** с async-генератором (chunked) |

```python
# SSE: однонаправленный поток (R-STREAM-1) — проще WebSocket, авто-reconnect на клиенте
from sse_starlette.sse import EventSourceResponse

@router.get("/orders/{order_id}/events")
async def order_events(order_id: UUID, principal: Principal = Depends(require_roles("customer"))):
    async def gen():
        async for evt in subscribe_order(order_id):       # источник — pub/sub, не БД-курсор (R-STREAM-8)
            yield {"event": evt.type_, "data": evt.model_dump_json()}
    return EventSourceResponse(gen())                      # heartbeat — параметр ping (R-STREAM-6)

# StreamingResponse: большая выгрузка без загрузки в память (R-STREAM-X2)
@router.get("/orders/export")
async def export_orders():
    async def rows():
        async for chunk in repo.stream_csv():             # короткие чтения, не одна транзакция на весь стрим
            yield chunk
    return StreamingResponse(rows(), media_type="text/csv")
```

- **AVOID** WebSocket, где хватает SSE (`R-STREAM-X1`); формирование всего ответа в память (`R-STREAM-X2`).

## 2. Auth на установлении (`R-STREAM-2/3`)

WebSocket **не проходит** обычные HTTP-зависимости auth так же, как REST — проверяем токен явно при `accept`:

```python
@router.websocket("/ws/orders/{order_id}")
async def ws_orders(ws: WebSocket, order_id: UUID):
    try:
        principal = await authenticate_ws(ws)             # R-STREAM-2: валидируем токен ДО accept
        authorize_subscription(principal, order_id)       # R-STREAM-3: права на конкретный ресурс
    except (AuthError, ForbiddenError):
        await ws.close(code=1008)                         # policy violation
        return
    await ws.accept()
    ...
```

- **AVOID** приём соединения без проверки токена (`R-STREAM-X3`); бессрочное соединение без переучёта `exp` (`R-STREAM-X4`).

## 3. Backpressure и лимиты (`R-STREAM-4/5`)

```python
# R-STREAM-4: ограниченная очередь на соединение; переполнение медленным клиентом → закрыть, не копить
queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
try:
    msg = queue.put_nowait(payload)
except asyncio.QueueFull:
    await ws.close(code=1011)                            # slow consumer (R-STREAM-X5)
# R-STREAM-5: глобальный лимит соединений на инстанс (semaphore/счётчик), 503 при превышении
```

- **AVOID** неограниченной очереди исходящих (`R-STREAM-X5`).

## 4. Heartbeat / idle-timeout (`R-STREAM-6`)

- SSE — `EventSourceResponse(gen(), ping=15)` (ping-комментарий каждые 15 c).
- WebSocket — периодический `await ws.send_json({"type": "ping"})` + закрытие при отсутствии pong/активности по таймауту (`asyncio.timeout`, cross-ref `PYASYNC-5`).
- **AVOID** соединения без heartbeat/idle-timeout (`R-STREAM-X6`).

## 5. Отмена при разрыве и ресурсы (`R-STREAM-7/8`)

```python
await ws.accept()
sub = await pubsub.subscribe(channel(order_id))
try:
    async for evt in sub:
        await ws.send_text(evt)
except WebSocketDisconnect:
    pass                                                  # R-STREAM-7: разрыв → выходим, останавливаем продьюсер
finally:
    await pubsub.unsubscribe(channel(order_id))          # освобождаем подписку/ресурсы
```

- БД-доступ — короткими сессиями per-message/per-chunk через репозиторий, **не** одна транзакция на всё соединение (`R-STREAM-8`, cross-ref `R-SQLA-SESS-1`).
- **AVOID** записи в закрытый канал (`R-STREAM-X7`); открытой транзакции на всю длину соединения (`R-STREAM-X8`).

## 6. Масштабирование (`R-STREAM-9`)

Несколько uvicorn-реплик: in-memory реестр соединений виден только своей реплике. Fan-out — через **Redis pub/sub**:
продьюсер публикует в канал, каждая реплика рассылает своим локальным подписчикам.

```python
# публикация (из command-handler/outbox-consumer): доходит до подписчиков на всех репликах (R-STREAM-9)
await redis.publish(channel(order_id), evt.model_dump_json())
```

- **AVOID** broadcast из локального in-memory реестра соединений (`R-STREAM-X9`).

## 7. Наблюдаемость (`R-STREAM-10`)

- Метрики `prometheus-client`: `stream_connections_active{kind}` (Gauge), `stream_messages_total`, `stream_disconnects_total`, длительность соединения (Histogram).
- Лог — событие соединения + идентификаторы (`order_id`, `principal.sub`), **без** payload/PII (`R-STREAM-X10`, cross-ref `R-OBS-LOG-X1`).

## Чеклист подключения к новому сервису (Python / FastAPI)

- [ ] Механизм по природе: SSE (server→client) / WebSocket (bidir) / `StreamingResponse` (выгрузка).
- [ ] Токен валидируется на handshake (WebSocket — до `accept`); авторизация на канал/ресурс.
- [ ] Ограниченная очередь + лимит соединений на инстанс; slow-consumer закрывается.
- [ ] Heartbeat (`ping`) + idle-timeout.
- [ ] `WebSocketDisconnect`/отмена освобождает подписки; БД — короткими сессиями, не транзакция на всё соединение.
- [ ] Fan-out через Redis pub/sub (не in-memory) при нескольких репликах.
- [ ] Метрики активных соединений/разрывов; без payload/PII в логах.
