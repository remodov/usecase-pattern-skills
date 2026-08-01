---
name: ucp-fe-routing-review
lang: any
track: frontend
description: Ревью роутинга React+TS (react-router 6) по UCP frontend-методологии (коды FE-RT-*) — централизованный типизированный ROUTES, ролевые guard'ы на границе роутера, типизированные params, навигация через useNavigate/Link, lazy+Suspense.
when_to_use: Изменения в роутах/навигации (routes/**, ROUTES, useParams/useNavigate, lazy/Suspense); ревью маршрутов, guard'ов по ролям и code-splitting.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Routing (React + TS, react-router 6)

Ты ревьюишь роутинг на соответствие `frontend/fe-routing/fe-routing-rules.md` (`FE-RT-*`).

## Зависимости

- **`.claude/docs/frontend/fe-routing/fe-routing-rules.md`** (`FE-RT-*`).
- Парные: `fe-state` (роли из стора), `fe-component` (выбор маршрута не в глубоком вью), `fe-data-fetching` (данные роута — в контейнере).

## Инструкции

1. **Прочти** `fe-routing-rules.md`. Цитируй конкретные коды (`FE-RT-X1`), не префикс.

2. **Скоп.** `routes/**`, `ROUTES`/`COMPONENTS`/`ROUTES_VALUES`, `createRoutes`/`getRoutePath`/`generatePath`, `useParams`/`useNavigate`/`<Link>`, `React.lazy`/`Suspense`; `git diff` на этих файлах.

3. **Прогон.**
   - **Централизация (`FE-RT-1/2/3`):** path-строка по месту (`'/new/...'`, конкатенация) вместо `ROUTES`+`getRoutePath`/`generatePath` → `FE-RT-X1`; список роутов продублирован без сшивки типами → `FE-RT-X2`.
   - **Guard'ы (`FE-RT-4/5/6/11`):** чувствительный роут без `roles` → `FE-RT-X3`; ad-hoc проверка прав внутри страницы вместо централизованного прохода `ROUTES_VALUES` + `intersection` → `FE-RT-X4`; роли берутся не из стора (`fe-state`); защищённый контент протекает, пока роли не загружены → `FE-RT-11`.
   - **Params/навигация (`FE-RT-7/8/9`):** `useParams()` без типа / `as any` → `FE-RT-X5`; `window.location.href`/`history.pushState` для внутренней навигации → `FE-RT-X6`; выбор маршрута зашит в глубокий вью вместо контейнера/колбэка.
   - **Code-splitting (`FE-RT-10`):** `React.lazy` без `Suspense`-fallback (или пустой fallback) → `FE-RT-X7`.

4. **Cross-check:** роли/состояние — `ucp-fe-state-review`; вью/декомпозиция — `ucp-fe-component-review`; данные роута — `ucp-fe-data-fetching-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — защищённый роут без guard (`FE-RT-X3`), ad-hoc проверка прав вместо централизованной (`FE-RT-X4`), `window.location` для внутренней навигации (`FE-RT-X6`), `lazy` без fallback (`FE-RT-X7`).
   - **Предупреждение** — хардкод path-строк (`FE-RT-X1`), дублирование списка роутов (`FE-RT-X2`), нетипизированные params (`FE-RT-X5`).
   - **Замечание** — выбор маршрута в глубоком вью вместо контейнера, роли из props вместо стора.

## Что не входит

- Сама логика стора/ролей — `ucp-fe-state-review`. Рендер/props страницы — `ucp-fe-component-review`. Загрузка данных роута — `ucp-fe-data-fetching-review`.

$ARGUMENTS
