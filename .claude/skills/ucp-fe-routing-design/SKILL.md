---
name: ucp-fe-routing-design
lang: any
track: frontend
description: Спроектировать роутинг React+TS (react-router 6) по UCP frontend-методологии (коды FE-RT-*) — централизованный типизированный ROUTES, ролевые guard'ы на границе роутера, типизированные params, навигация через useNavigate/Link, lazy+Suspense.
when_to_use: Триггеры — «новый роут/страница X», «guard по роли», «параметр в URL», «code-splitting». При добавлении маршрута, защите раздела или организации навигации.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend Routing — проектирование (React + TS, react-router 6)

Ты проектируешь роутинг по `frontend/fe-routing/fe-routing-rules.md` (`FE-RT-*`). Часть трека `frontend`
(карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-routing/fe-routing-rules.md` (`FE-RT-*`). Связанные: `fe-state` (роли пользователя — из стора, `userRolesSelector`), `fe-component` (вью не зашивает выбор маршрута/проверку прав), `fe-data-fetching` (данные роута грузит контейнер). Коды — в обосновании, не в коде.

2. **Централизуй маршрут** (`FE-RT-1/2/3`): новый роут — записью в типизированный `ROUTES` (`createRoutes<T>`), `{ path, roles?, title? }`; путь для переходов берётся через `getRoutePath(ROUTES.X)` / `generatePath(...)`, не строкой. Ключи `ROUTES` ↔ `COMPONENTS` держи сшитыми (один источник для рендера).

3. **Спроектируй guard** (`FE-RT-4/5/6/11`): для защищённого раздела задай `roles?: UserRoles[]` на роуте; доступ проверяй централизованно — декларативным проходом по единому списку (`ROUTES_VALUES.map`) с `intersection(route.roles ?? [], userRoles ?? [])`, пустые `roles` → публичный роут; единый редирект/`NotFound`/`AccessDenied`, не ad-hoc в компоненте. Пока роли не загружены — не показывай защищённый контент даже на миг.

4. **Параметры и навигация** (`FE-RT-7/8/9`): params типизируй и читай `useParams<{ ... }>()`, отсутствие параметра обрабатывай явно; навигация — `useNavigate`/`<Link>`/`generatePath`, не `window.location`; решение о переходе — в контейнере, вью получает колбэк.

5. **Code-splitting** (`FE-RT-10`): тяжёлую страницу подключай `React.lazy` + `Suspense` с осмысленным `fallback`.

6. **Самопроверка** (чеклист §5) + предложи `ucp-fe-routing-review`. Состояние/роли — `ucp-fe-state-design`, вью — `ucp-fe-component-design`, данные роута — `ucp-fe-data-fetching-design`.

## Антипаттерны, которые НЕ генерировать

- Хардкод path-строк вместо `ROUTES`/`getRoutePath` (`FE-RT-X1`); дублирование списка роутов без сшивки типами (`FE-RT-X2`).
- Защищённый роут без `roles` (`FE-RT-X3`); ad-hoc проверка прав в компоненте (`FE-RT-X4`).
- Нетипизированные params/`any` (`FE-RT-X5`); `window.location.href` для внутренней навигации (`FE-RT-X6`); `React.lazy` без `Suspense`-fallback (`FE-RT-X7`).

После работы скилла — обязательно `ucp-fe-routing-review`.

$ARGUMENTS
