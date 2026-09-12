---
name: ucp-py-streaming-review
lang: python
description: Ревью потокового соединения FastAPI по UCP (требования streaming/*) — выбор механизма, auth на handshake, backpressure, heartbeat, отмена при разрыве, короткие БД-сессии, fan-out, PII в логах.
when_to_use: Ревью websocket-роутеров, SSE- и StreamingResponse-эндпоинтов.
allowed-tools: Read Glob Grep
---

# Ревью streaming/real-time (Python / FastAPI + Starlette)

Ты проверяешь потоковое соединение против `backend/streaming/spec.md` (`R-STREAM-*`) и
`backend/streaming/references/python/implementation.md`. Формат findings — `shared/review-format/spec.md` (`review-format/*`).

## Процесс ревью

1. **Прочитай** `.claude/docs/backend/streaming/spec.md` (`R-STREAM-*`), `.claude/docs/backend/streaming/references/python/implementation.md` и `.claude/docs/shared/review-format/spec.md`. Связанные: `PYASYNC-*`, `AUTH-*`, `R-SQLA-SESS-*`, `R-OBS-*`.

2. **Определи объект:** `@router.websocket`-роутеры, `EventSourceResponse`/SSE-эндпоинты, `StreamingResponse`-выгрузки, pub/sub-подписчики.

3. **Проверь по подгруппам кодов** (цитируй коды в findings):
   - **Механизм** (`streaming/mechanism-matches-exchange`): SSE/WebSocket/StreamingResponse по природе; нет WebSocket где хватает SSE (`X1`); нет сборки ответа в память (`X2`).
   - **Auth** (`R-STREAM-2/3`): токен валидируется до `accept` (WebSocket), авторизация на канал; нет открытого соединения (`X3`), нет бессрочного без переучёта `exp` (`X4`).
   - **Backpressure** (`R-STREAM-4/5`): ограниченная очередь, slow-consumer закрывается, лимит соединений; нет неограниченной очереди (`X5`).
   - **Heartbeat** (`streaming/heartbeat-and-idle-timeout`): ping + idle-timeout; нет соединения без них (`X6`).
   - **Отмена/ресурсы** (`R-STREAM-7/8`): `WebSocketDisconnect`/отмена освобождает подписки (`finally`); БД короткими сессиями; нет записи в закрытый канал (`X7`), нет транзакции на всё соединение (`X8`).
   - **Масштабирование** (`streaming/fanout-works-across-instances`): fan-out через Redis pub/sub; нет broadcast из in-memory реестра (`X9`).
   - **Observability** (`streaming/connections-observable-without-payloads`): метрики соединений/разрывов; без payload/PII в логах (`X10`).

4. **Частые реальные дефекты** (приоритет): WebSocket без auth до `accept`; транзакция БД открыта на всё соединение; broadcast из локального dict при нескольких репликах; нет heartbeat → зависшие соединения; неограниченный буфер.

5. **Выдай findings** по `review-format/*` (severity, код, файл:строка, фикс) и предложи парный `ucp-py-streaming-design`.

## Что не входит

- Async event loop/отмена/таймауты по существу — `ucp-py-async-review`. JWT-валидация как механизм — `ucp-py-auth-review`. Сессии/транзакции — `ucp-py-sqlalchemy-review`. Контракт обычного REST — `ucp-py-api-review`.

$ARGUMENTS
