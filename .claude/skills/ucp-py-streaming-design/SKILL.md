---
name: ucp-py-streaming-design
lang: python
description: Спроектировать потоковое соединение FastAPI по UCP (требования streaming/*) — выбор SSE / WebSocket / StreamingResponse, auth на handshake, backpressure, heartbeat, отмена при разрыве, fan-out через Redis.
when_to_use: При добавлении WebSocket- или SSE-эндпоинта, потоковой выгрузки. Связан с async, auth, sqlalchemy, kafka.
allowed-tools: Read Glob Grep Write Edit Bash(python*) Bash(pytest*)
---

# Проектирование streaming/real-time (Python / FastAPI + Starlette)

Ты проектируешь долгоживущее/потоковое соединение согласно `backend/streaming/spec.md` (`R-STREAM-*`) и
`backend/streaming/references/python/implementation.md`. Соединение живёт долго и держит ресурсы — выбери минимально
достаточный механизм, аутентифицируй на установлении, ограничивай буферы и освобождай ресурсы при разрыве.

## Инструкции

1. **Прочитай** `.claude/docs/backend/streaming/spec.md` (`R-STREAM-*`) и `.claude/docs/backend/streaming/references/python/implementation.md`. Связанные: `backend/python/async/spec.md` (`PYASYNC-*` — event loop/отмена/таймауты), `backend/auth-patterns/...` (`AUTH-*` — handshake-auth), `backend/python/sqlalchemy/spec.md` (`R-SQLA-SESS-*`), `backend/graceful-shutdown/...` (`R-SHUT-*` — закрытие соединений на shutdown).

2. **Произведи код** (async, тайп-хинты; коды правил НЕ цитируй в коде):
   - **Механизм** по природе: SSE (`EventSourceResponse`) для server→client; WebSocket (`@router.websocket`) для bidir; `StreamingResponse` + async-генератор для больших выгрузок (`streaming/mechanism-matches-exchange`).
   - **Auth на handshake:** для WebSocket валидировать токен **до** `ws.accept()`, авторизовать подписку на ресурс (`R-STREAM-2/3`).
   - **Backpressure:** ограниченная `asyncio.Queue`, закрытие slow-consumer; лимит соединений на инстанс (`R-STREAM-4/5`).
   - **Heartbeat:** SSE `ping=`, WebSocket периодический ping + idle-timeout (`streaming/heartbeat-and-idle-timeout`).
   - **Отмена/ресурсы:** `WebSocketDisconnect`/отмена → `finally` освобождает подписки; БД короткими сессиями per-message, не транзакция на всё соединение (`R-STREAM-7/8`).
   - **Fan-out:** Redis pub/sub между репликами, не in-memory реестр (`streaming/fanout-works-across-instances`).
   - **Метрики/логи:** активные соединения/разрывы; без payload/PII (`streaming/connections-observable-without-payloads`).

3. **Самопроверка** + предложи `ucp-py-streaming-review`. Async-корректность — `ucp-py-async-design`; auth-деталь — `ucp-py-auth-design`.

## Антипаттерны, которые НЕ генерировать

- WebSocket где хватает SSE (`streaming/mechanism-matches-exchange`); весь ответ в память вместо chunked (`streaming/large-response-is-streamed`).
- Приём соединения без проверки токена (`streaming/authenticate-on-handshake`); бессрочное соединение без переучёта `exp` (`streaming/long-lived-connections-recheck-rights`).
- Неограниченная очередь исходящих (`streaming/backpressure-is-bounded`); соединение без heartbeat/idle-timeout (`streaming/heartbeat-and-idle-timeout`).
- Запись в закрытый канал (`streaming/disconnect-cancels-work`); транзакция/сессия БД на всё соединение (`streaming/no-resources-held-for-connection-lifetime`).
- Broadcast из in-memory реестра при нескольких репликах (`streaming/fanout-works-across-instances`); payload/PII в логах (`streaming/connections-observable-without-payloads`).

После работы скилла — обязательно `ucp-py-streaming-review`.

$ARGUMENTS
