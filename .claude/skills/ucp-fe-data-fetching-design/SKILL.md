---
name: ucp-fe-data-fetching-design
lang: any
track: frontend
description: Спроектировать загрузку данных React+TS по UCP frontend-методологии (коды FE-DATA-*) — Fetcher+доменные fetcher'ы, URL из ~/utils/endpoints, запросы в redux-thunk через middlewareHandler с RequestStatus, типизация get<T>, отмена гонок.
when_to_use: Триггеры — «загрузить X», «запрос/fetch к API», «дёрнуть эндпоинт», «thunk для Y». При проектировании fetcher'а, thunk'а или подключения данных к компоненту.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend Data Fetching — проектирование (React + TS, Fetcher + thunks)

Ты проектируешь загрузку данных по `frontend/fe-data-fetching/fe-data-fetching-rules.md` (`FE-DATA-*`). Часть
трека `frontend` (карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-data-fetching/fe-data-fetching-rules.md` (`FE-DATA-*`). Связанные: `fe-component` (запрос не в презентационном компоненте, `FE-CMP-X1`), `fe-state` (результат в RTK slice с `RequestStatus`), `fe-forms` (submit зовёт thunk). Коды — в обосновании, не в коде.

2. **Реши, где живёт запрос** (`FE-DATA-1/2/3`): инициируй через thunk; компонент диспатчит thunk и читает результат из стора. Запуск на маунте/смене параметров — `useEffect`, диспатчащий thunk, а не `fetch` напрямую.

3. **Спроектируй слой транспорта и fetcher'ов** (`FE-DATA-4/5/6/13`):
   - Вызов через типизированные хелперы `get/post/put` (`~/fetchers/utils`) / доменную fetcher-функцию; читай `HttpResponse<T>.parsedBody`, не парси тело и статус вручную (`FE-DATA-X9`).
   - Не-2xx транспорт уже превратил в типизированный `RequestError` (`statusCode` + сериализованные поля) — лови/пробрасывай его (`FE-DATA-13`).
   - URL — только из `~/utils/endpoints` (константа или билдер `getEndpointClientById(id)`), без хардкода (`FE-DATA-X3`). Доменный fetcher — узкая функция на ресурс/действие.

4. **Контракт thunk** (`FE-DATA-7/14/15/8`): оберни запрос `middlewareHandler(dispatch, requestStatusAction, handler)` — он сам даёт жизненный цикл `RequestState` (`INITIALIZED→PENDING→FULFILLED|REJECTED`), сериализует ошибку в `error-slice` и логирует; **свой `try/catch` поверх не пиши** (`FE-DATA-X5`). `middlewareHandler` не реджектит и **возвращает значение** `handler`'а — прокинь его наверх (для пост-действий, напр. навигации после submit, `FE-DATA-15`). Loading/error отрази в UI по статусу операции.

5. **Типизация, гонки, параллель** (`FE-DATA-10/11/12`): ответ — `get<T>` без `any`; устаревшие ответы отменяй/игнорируй (`AbortController`/проверка актуальности); независимые запросы — `Promise.allSettled`.

6. **RTK Query** (`createBaseQuery`, чеклист п.6): для нового эндпоинта допустима как альтернатива Fetcher+thunk — но статусы и типизация обязательны так же.

7. **Самопроверка** (чеклист §5) + предложи `ucp-fe-data-fetching-review`. Стор/slice — `ucp-fe-state-design`, вью — `ucp-fe-component-design`, формы — `ucp-fe-forms-design`.

## Антипаттерны, которые НЕ генерировать

- `fetch`/`axios`/прямой fetcher в JSX или теле компонента (`FE-DATA-X1`); запрос в `useEffect` в обход thunk (`FE-DATA-X2`).
- Хардкод URL вместо `~/utils/endpoints` (`FE-DATA-X3`); дублирование запроса вместо единой fetcher-функции (`FE-DATA-X4`).
- Свой `try/catch` поверх `middlewareHandler` или пустой `catch` (`FE-DATA-X5`); запрос без `requestStatusAction`/loading/error в UI (`FE-DATA-X6`).
- Ручной `response.json()`/разбор статуса в обход транспорта (`FE-DATA-X9`); `any`/нетипизированный ответ (`FE-DATA-X7`); игнор гонок — устаревший ответ перезаписывает свежий стейт (`FE-DATA-X8`).

После работы скилла — обязательно `ucp-fe-data-fetching-review`.

$ARGUMENTS
