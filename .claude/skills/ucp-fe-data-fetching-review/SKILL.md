---
name: ucp-fe-data-fetching-review
lang: any
track: frontend
description: Ревью загрузки данных React+TS по UCP frontend-методологии (коды FE-DATA-*) — запрос в thunk а не в компоненте, URL из ~/utils/endpoints, middlewareHandler+RequestStatus, ошибки через error-slice, типизация get<T>, отмена гонок, Promise.allSettled.
when_to_use: Изменения в fetcher'ах/thunks/endpoints (fetchers/**, thunks.ts, endpoints.ts) или fetch/useEffect в компонентах; ревью как и где грузятся данные.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Data Fetching (React + TS, Fetcher + thunks)

Ты ревьюишь загрузку данных на соответствие `frontend/fe-data-fetching/fe-data-fetching-rules.md` (`FE-DATA-*`).

## Зависимости

- **`.claude/docs/frontend/fe-data-fetching/fe-data-fetching-rules.md`** (`FE-DATA-*`).
- Парные: `fe-component` (запрос не во вью), `fe-state` (результат в slice с RequestStatus), `fe-forms` (submit → thunk).

## Инструкции

1. **Прочти** `fe-data-fetching-rules.md`. Цитируй конкретные коды (`FE-DATA-X5`), не префикс.

2. **Скоп.** `src/fetchers/**`, `~/fetchers/utils`, `~/utils/endpoints`, `thunks.ts`, `*-slice.ts`, `store/rtk-services/**`, а также `fetch`/`useEffect`/прямые вызовы fetcher'ов в компонентах; `git diff` на этих файлах.

3. **Прогон.**
   - **Где запрос (`FE-DATA-1/2/3`):** `fetch`/`axios`/прямой fetcher в JSX или теле презентационного компонента → `FE-DATA-X1` (cross-ref `FE-CMP-X1`); запрос в `useEffect` в обход thunk (минуя статусы/middleware) → `FE-DATA-X2`.
   - **Транспорт/fetcher/эндпоинты (`FE-DATA-4/5/6/13`):** ручной `fetch`/`Request` вместо `get/post/put`; ручной `response.json()`/разбор статуса в обход транспорта → `FE-DATA-X9`; не используется `.parsedBody`/типизированный `RequestError`; хардкод URL вместо `~/utils/endpoints` → `FE-DATA-X3`; дублирование запроса вместо доменной fetcher-функции → `FE-DATA-X4`.
   - **Контракт thunk (`FE-DATA-7/14/15/8`):** запрос без `middlewareHandler`/`requestStatusAction` → `FE-DATA-X6`; **свой `try/catch` поверх `middlewareHandler`** (двойная обработка) или пустой `catch {}` → `FE-DATA-X5`; результат `middlewareHandler` не прокинут наверх, хотя нужен для пост-действия (`FE-DATA-15`); нет loading/error в UI → `FE-DATA-8`.
   - **Типизация/гонки/параллель (`FE-DATA-10/11/12`):** `any`/нетипизированный ответ fetcher'а → `FE-DATA-X7`; нет отмены устаревших ответов (гонка перезаписывает свежий стейт) → `FE-DATA-X8`; последовательный `await` в цикле вместо `Promise.allSettled`.

4. **Cross-check:** стор/slice — `ucp-fe-state-review`; вью/props — `ucp-fe-component-review`; формы — `ucp-fe-forms-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `fetch`/fetcher в компоненте (`FE-DATA-X1`), свой `try/catch` поверх `middlewareHandler`/пустой `catch` (`FE-DATA-X5`), `any` в ответе (`FE-DATA-X7`), гонка перезаписывает свежий стейт (`FE-DATA-X8`).
   - **Предупреждение** — запрос в обход thunk/статусов (`FE-DATA-X2`), ручной разбор ответа в обход транспорта (`FE-DATA-X9`), хардкод URL (`FE-DATA-X3`), нет loading/error в UI (`FE-DATA-X6`).
   - **Замечание** — дублирование запроса вместо fetcher-функции (`FE-DATA-X4`), последовательные запросы вместо `Promise.allSettled`.

## Что не входит

- Структура slice/селекторы/иммутабельность — `ucp-fe-state-review`. Рендер/props/мемоизация — `ucp-fe-component-review`. Состояние формы — `ucp-fe-forms-review`.

$ARGUMENTS
