---
name: ucp-fe-state-design
lang: any
track: frontend
description: Спроектировать управление состоянием React+TS по UCP frontend-методологии (коды FE-ST-*) — Redux Toolkit slice по домену, local UI-state vs стор, типизированные селекторы, server-data с RequestStatus, эффекты в thunk'ах.
when_to_use: Триггеры — «состояние X», «стор/slice для Y», «где хранить данные». При проектировании slice, селекторов или выборе local vs global state.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend State — проектирование (React + TS, Redux Toolkit)

Ты проектируешь управление состоянием по `frontend/fe-state/fe-state-rules.md` (`FE-ST-*`). Часть трека
`frontend` (карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-state/fe-state-rules.md` (`FE-ST-*`). Связанные: `fe-data-fetching` (thunks/запросы наполняют стор), `fe-component` (вью не держит бизнес-логику), `fe-forms` (состояние формы — в Formik). Коды — в обосновании, не в коде.

2. **Реши, где живёт состояние** (`FE-ST-1/2`): эфемерное UI (popup, таб, ввод) — локально (`useState`/Formik); доменное/разделяемое — в Redux-сторе. Ответ сервера — кеш со статусом операции (`FE-ST-3`), наполняется thunk'ом.

3. **Спроектируй slice** (Redux Toolkit):
   - Один slice — один домен; `createSlice` с типизированным `initialState`, редьюсеры через `PayloadAction<T>` (`FE-ST-4`).
   - Статусы операций — **карта `requestStatuses`** (enum `RequestState`: `INITIALIZED/PENDING/FULFILLED/REJECTED`), по одной на операцию (`fetch`/`edit`/`create`), а не один общий `isLoading` (`FE-ST-12`, `FE-ST-X7`).
   - Списки с пагинацией — форма list-state (`items`/`offset`/`limit`/`isListEnd`); append vs replace решает редьюсер (`FE-ST-13`).
   - Мутации — только в редьюсерах (Immer); снаружи иммутабельно (`FE-ST-5/6`, `FE-ST-X2`). Side-effect'ы — в thunk'ах (`FE-ST-11`, `FE-ST-X6`).

4. **Селекторы** (`FE-ST-7/8/9/14`): слоистые именованные селекторы (базовый → производные) как единая точка знания о форме стора; кросс-slice джойны и тяжёлые деривации — через `createSelector` (`reselect`), не сборка массива на рендер; не дублируй полем (`FE-ST-X4`); срез узкий.

5. **Типизация и инстанс** (`FE-ST-10/15`): типизированные `useAppSelector`/`useAppDispatch` из `RootState`/`AppDispatch`, без `any`; в host-режиме store-инстанс переиспользуется, не пересоздаётся (`FE-ST-X8`).

6. **Самопроверка** (чеклист §5) + предложи `ucp-fe-state-review`. Запросы — `ucp-fe-data-fetching-design`, формы — `ucp-fe-forms-design`.

## Антипаттерны, которые НЕ генерировать

- UI-эфемерида (hover/фокус/раскрытие) в глобальном сторе (`FE-ST-X1`); god-slice из несвязанных доменов (`FE-ST-X3`); один общий `isLoading`/`error` на slice с несколькими операциями (`FE-ST-X7`).
- Мутация состояния вне редьюсера (`FE-ST-X2`); дублирование источника правды (`FE-ST-X4`); производные данные в компоненте вместо селектора (`FE-ST-X5`); асинхронщина/недетерминизм в редьюсере (`FE-ST-X6`); пересоздание store на каждый mount в host-режиме (`FE-ST-X8`).

После работы скилла — обязательно `ucp-fe-state-review`.

$ARGUMENTS
