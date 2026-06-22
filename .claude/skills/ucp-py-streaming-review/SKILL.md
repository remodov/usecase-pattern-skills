---
name: ucp-py-streaming-review
lang: python
description: Ревью потокового/real-time соединения FastAPI по UCP (коды R-STREAM-*) — корректный выбор механизма (SSE vs WebSocket vs StreamingResponse), auth на handshake (токен до accept), backpressure и лимит соединений, heartbeat/idle-timeout, отмену при разрыве + освобождение ресурсов, короткие БД-сессии (не транзакция на всё соединение), fan-out через Redis pub/sub, отсутствие payload/PII в логах. Вызывается на ревью websocket-роутеров, SSE/StreamingResponse-эндпоинтов.
allowed-tools: Read Glob Grep
---

# Ревью streaming/real-time (Python / FastAPI + Starlette)

Ты проверяешь потоковое соединение против `backend/streaming/streaming-rules.md` (`R-STREAM-*`) и
`backend/streaming/python/streaming-style-guide.md`. Формат findings — `shared/review-finding-format.md` (`RFF-*`).

## Процесс ревью

1. **Прочитай** `.claude/docs/backend/streaming/streaming-rules.md` (`R-STREAM-*`), `.claude/docs/backend/streaming/python/streaming-style-guide.md` и `.claude/docs/shared/review-finding-format.md`. Связанные: `PYASYNC-*`, `AUTH-*`, `R-SQLA-SESS-*`, `R-OBS-*`.

2. **Определи объект:** `@router.websocket`-роутеры, `EventSourceResponse`/SSE-эндпоинты, `StreamingResponse`-выгрузки, pub/sub-подписчики.

3. **Проверь по подгруппам кодов** (цитируй коды в findings):
   - **Механизм** (`R-STREAM-1`): SSE/WebSocket/StreamingResponse по природе; нет WebSocket где хватает SSE (`X1`); нет сборки ответа в память (`X2`).
   - **Auth** (`R-STREAM-2/3`): токен валидируется до `accept` (WebSocket), авторизация на канал; нет открытого соединения (`X3`), нет бессрочного без переучёта `exp` (`X4`).
   - **Backpressure** (`R-STREAM-4/5`): ограниченная очередь, slow-consumer закрывается, лимит соединений; нет неограниченной очереди (`X5`).
   - **Heartbeat** (`R-STREAM-6`): ping + idle-timeout; нет соединения без них (`X6`).
   - **Отмена/ресурсы** (`R-STREAM-7/8`): `WebSocketDisconnect`/отмена освобождает подписки (`finally`); БД короткими сессиями; нет записи в закрытый канал (`X7`), нет транзакции на всё соединение (`X8`).
   - **Масштабирование** (`R-STREAM-9`): fan-out через Redis pub/sub; нет broadcast из in-memory реестра (`X9`).
   - **Observability** (`R-STREAM-10`): метрики соединений/разрывов; без payload/PII в логах (`X10`).

4. **Частые реальные дефекты** (приоритет): WebSocket без auth до `accept`; транзакция БД открыта на всё соединение; broadcast из локального dict при нескольких репликах; нет heartbeat → зависшие соединения; неограниченный буфер.

5. **Выдай findings** по `RFF-*` (severity, код, файл:строка, фикс) и предложи парный `ucp-py-streaming-design`.

## Что не входит

- Async event loop/отмена/таймауты по существу — `ucp-py-async-review`. JWT-валидация как механизм — `ucp-py-auth-review`. Сессии/транзакции — `ucp-py-sqlalchemy-review`. Контракт обычного REST — `ucp-py-api-review`.

$ARGUMENTS
