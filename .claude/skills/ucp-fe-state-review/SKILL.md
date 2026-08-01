---
name: ucp-fe-state-review
lang: any
track: frontend
description: Ревью управления состоянием React+TS по UCP frontend-методологии (коды FE-ST-*) — Redux Toolkit slice по домену, иммутабельность вне редьюсеров, именованные селекторы, server-data с RequestStatus, эффекты в thunk'ах.
when_to_use: Изменения в slice/store/selectors/thunks (*.slice.ts, store/**); ревью где живёт и как меняется состояние.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend State (React + TS, Redux Toolkit)

Ты ревьюишь управление состоянием на соответствие `frontend/fe-state/fe-state-rules.md` (`FE-ST-*`).

## Зависимости

- **`.claude/docs/frontend/fe-state/fe-state-rules.md`** (`FE-ST-*`).
- Парные: `fe-data-fetching` (thunks/request-status), `fe-component`, `fe-forms`.

## Инструкции

1. **Прочти** `fe-state-rules.md`. Цитируй конкретные коды (`FE-ST-X2`), не префикс.

2. **Скоп.** `store/**`, `*-slice.ts`, `selectors.ts`, `thunks.ts`, `useSelector`/`useDispatch` в компонентах; `git diff` на этих файлах.

3. **Прогон.**
   - **Где состояние (`FE-ST-1/2/3/12/13`):** UI-эфемерида в глобальном сторе → `FE-ST-X1`; server-data без статуса операции → нарушение `FE-ST-3`; один общий `isLoading` на slice с несколькими операциями → `FE-ST-X7`; пагинация без формы list-state/решения append-replace в редьюсере → `FE-ST-13`.
   - **Slice/иммутабельность (`FE-ST-4/5/6/15`):** мутация состояния вне редьюсера (`state.x.push` в компоненте/thunk/селекторе) → `FE-ST-X2`; несвязанные домены в одном slice → `FE-ST-X3`; пересоздание store на каждый mount в host-режиме → `FE-ST-X8`.
   - **Селекторы (`FE-ST-7/8/9/14`):** инлайн `useSelector(s => …)` вместо именованных слоистых селекторов; кросс-slice джойн/деривация без `createSelector` (новый массив на рендер) → `FE-ST-14`; дублирование источника правды → `FE-ST-X4`; производные данные считаются в компоненте → `FE-ST-X5`; широкий срез (весь slice) ломает referential equality.
   - **Типизация/эффекты (`FE-ST-10/11`):** `any` в стейте/пэйлоаде; запрос/асинхронщина/недетерминизм в редьюсере → `FE-ST-X6`.

4. **Cross-check:** запросы/thunks — `ucp-fe-data-fetching-review`; вью — `ucp-fe-component-review`; формы — `ucp-fe-forms-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — мутация вне редьюсера (`FE-ST-X2`), `any` в стейте, асинхронщина в редьюсере (`FE-ST-X6`), дублирование источника правды (`FE-ST-X4`).
   - **Предупреждение** — UI-эфемерида в сторе (`FE-ST-X1`), server-data без статуса операции, один общий `isLoading` (`FE-ST-X7`), производные в компоненте (`FE-ST-X5`), god-slice (`FE-ST-X3`), пересоздание store в host-режиме (`FE-ST-X8`).
   - **Замечание** — инлайн-селекторы вместо слоистых именованных, кросс-slice джойн без `createSelector` (`FE-ST-14`), широкий срез без мемоизации.

## Что не входит

- Сами запросы/кеш/отмена — `ucp-fe-data-fetching-review`. Состояние формы — `ucp-fe-forms-review`. Рендер/props — `ucp-fe-component-review`.

$ARGUMENTS
