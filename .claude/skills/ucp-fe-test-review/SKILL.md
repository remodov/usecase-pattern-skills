---
name: ucp-fe-test-review
lang: any
track: frontend
description: Ревью тестов компонентов React+TS по UCP frontend-методологии (коды FE-TEST-*) на Jest + Testing Library — поведение вместо реализации, юзер-центричные запросы getByRole + userEvent, renderWithProviders, мок на сетевой границе, async через findBy.
when_to_use: Изменения в тестах (*.test.tsx, *.test.ts, __tests__/**, test-utils); ревью что и как проверяется — поведение, запросы, моки, async.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Test (React + TS, Jest + Testing Library)

Ты ревьюишь тесты на соответствие `frontend/fe-test/fe-test-rules.md` (`FE-TEST-*`).

## Зависимости

- **`.claude/docs/frontend/fe-test/fe-test-rules.md`** (`FE-TEST-*`).
- Парные: `fe-component` (что есть наблюдаемое поведение вью), `fe-state` (реальный store, не мок slice), `fe-data-fetching` (мок на границе), `fe-forms`, `fe-a11y` (роли).

## Инструкции

1. **Прочти** `fe-test-rules.md`. Цитируй конкретные коды (`FE-TEST-X3`), не префикс.

2. **Скоп.** `*.test.tsx`, `*.test.ts`, `__tests__/**`, `test-utils`/`renderWithProviders`; `git diff` на этих файлах.

3. **Прогон.**
   - **Что тестируем (`FE-TEST-1/2/3`):** проверка внутреннего стейта/инстанса/приватных функций вместо DOM → `FE-TEST-X1`; тотальный `toMatchSnapshot` вместо assert'ов → `FE-TEST-X2`; имя теста описывает реализацию, а не поведение → `FE-TEST-2`; не покрыты значимые ветки (ошибка/пусто/загрузка) → `FE-TEST-3`.
   - **Запросы/взаимодействия (`FE-TEST-4/5/6`):** `container.querySelector`/`className`/`getByTestId` при наличии роли/лейбла → `FE-TEST-X3`; привязка к `nth-child`/индексам/порядку DOM → `FE-TEST-X4`; `fireEvent` для пользовательского действия вместо `userEvent` → нарушение `FE-TEST-5`.
   - **Окружение/моки (`FE-TEST-7/8/9`):** голый `render` там, где нужны провайдеры, вместо `renderWithProviders` → нарушение `FE-TEST-7`; `jest.mock` на внутренние хуки/функции/селекторы компонента → `FE-TEST-X5`; общий мутируемый store/состояние между тестами, нет `clearAllMocks`/`cleanup` → `FE-TEST-X6`.
   - **Async/имена (`FE-TEST-10/11`):** `setTimeout`/`sleep`/фиксированная задержка вместо `findBy`/`waitFor` → `FE-TEST-X7`; ручной `act`/подавление warning'а вместо `await findBy*`/`await userEvent` → `FE-TEST-X8`; имена не по-русски/неосмысленные → нарушение `FE-TEST-11`.

4. **Cross-check:** мок запроса/thunk — `ucp-fe-data-fetching-review`; вью — `ucp-fe-component-review`; стор/селекторы — `ucp-fe-state-review`; формы — `ucp-fe-forms-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — мок реализации вместо границы (`FE-TEST-X5`), проверка внутреннего стейта вместо поведения (`FE-TEST-X1`), `setTimeout` вместо `findBy`/`waitFor` дающий флаки (`FE-TEST-X7`), общий мутируемый store между тестами (`FE-TEST-X6`).
   - **Предупреждение** — `getByTestId`/`className` при наличии роли (`FE-TEST-X3`), тотальный snapshot (`FE-TEST-X2`), голый `render` вместо `renderWithProviders`, `fireEvent` вместо `userEvent`, не покрыты значимые ветки.
   - **Замечание** — привязка к порядку DOM (`FE-TEST-X4`), ручной `act`/подавление warning'а (`FE-TEST-X8`), имена тестов не по-русски/невнятные.

## Что не входит

- Логика самого запроса/кеша/thunk — `ucp-fe-data-fetching-review`. Структура store/селекторов — `ucp-fe-state-review`. Рендер/props компонента — `ucp-fe-component-review`. Состояние формы — `ucp-fe-forms-review`.

$ARGUMENTS
