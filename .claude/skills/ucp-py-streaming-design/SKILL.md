---
name: ucp-py-streaming-design
lang: python
description: Спроектировать потоковое/real-time соединение FastAPI по UCP (коды R-STREAM-*) — выбор механизма (SSE / WebSocket / StreamingResponse), auth на handshake, backpressure и лимит соединений, heartbeat/idle-timeout, отмена при разрыве + освобождение ресурсов, короткие БД-сессии (не транзакция на всё соединение), fan-out через Redis pub/sub при нескольких репликах. Триггеры — «websocket», «SSE/server-sent events», «стриминг ответа», «real-time нотификации», «выгрузка большого файла».
when_to_use: При добавлении WebSocket/SSE-эндпоинта или потоковой выгрузки. Связан с async (event loop/отмена), auth (handshake), sqlalchemy (сессии), kafka/caching (pub/sub).
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование streaming/real-time (Python / FastAPI + Starlette)

Ты проектируешь долгоживущее/потоковое соединение согласно `backend/streaming/streaming-rules.md` (`R-STREAM-*`) и
`backend/streaming/python/streaming-style-guide.md`. Соединение живёт долго и держит ресурсы — выбери минимально
достаточный механизм, аутентифицируй на установлении, ограничивай буферы и освобождай ресурсы при разрыве.

## Инструкции

1. **Прочитай** `.claude/docs/backend/streaming/streaming-rules.md` (`R-STREAM-*`) и `.claude/docs/backend/streaming/python/streaming-style-guide.md`. Связанные: `backend/python/async/async-rules.md` (`PYASYNC-*` — event loop/отмена/таймауты), `backend/auth-patterns/...` (`AUTH-*` — handshake-auth), `backend/python/sqlalchemy/sqlalchemy-rules.md` (`R-SQLA-SESS-*`), `backend/graceful-shutdown/...` (`R-SHUT-*` — закрытие соединений на shutdown).

2. **Произведи код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Механизм** по природе: SSE (`EventSourceResponse`) для server→client; WebSocket (`@router.websocket`) для bidir; `StreamingResponse` + async-генератор для больших выгрузок (`R-STREAM-1`).
   - **Auth на handshake:** для WebSocket валидировать токен **до** `ws.accept()`, авторизовать подписку на ресурс (`R-STREAM-2/3`).
   - **Backpressure:** ограниченная `asyncio.Queue`, закрытие slow-consumer; лимит соединений на инстанс (`R-STREAM-4/5`).
   - **Heartbeat:** SSE `ping=`, WebSocket периодический ping + idle-timeout (`R-STREAM-6`).
   - **Отмена/ресурсы:** `WebSocketDisconnect`/отмена → `finally` освобождает подписки; БД короткими сессиями per-message, не транзакция на всё соединение (`R-STREAM-7/8`).
   - **Fan-out:** Redis pub/sub между репликами, не in-memory реестр (`R-STREAM-9`).
   - **Метрики/логи:** активные соединения/разрывы; без payload/PII (`R-STREAM-10`).

3. **Самопроверка** + предложи `ucp-py-streaming-review`. Async-корректность — `ucp-py-async-design`; auth-деталь — `ucp-py-auth-design`.

## Антипаттерны, которые НЕ генерировать

- WebSocket где хватает SSE (`R-STREAM-X1`); весь ответ в память вместо chunked (`R-STREAM-X2`).
- Приём соединения без проверки токена (`R-STREAM-X3`); бессрочное соединение без переучёта `exp` (`R-STREAM-X4`).
- Неограниченная очередь исходящих (`R-STREAM-X5`); соединение без heartbeat/idle-timeout (`R-STREAM-X6`).
- Запись в закрытый канал (`R-STREAM-X7`); транзакция/сессия БД на всё соединение (`R-STREAM-X8`).
- Broadcast из in-memory реестра при нескольких репликах (`R-STREAM-X9`); payload/PII в логах (`R-STREAM-X10`).

После работы скилла — обязательно `ucp-py-streaming-review`.

$ARGUMENTS
