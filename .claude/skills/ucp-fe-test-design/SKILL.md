---
name: ucp-fe-test-design
lang: any
track: frontend
description: Спроектировать тесты React+TS по UCP frontend-методологии (коды FE-TEST-*) на Jest + Testing Library — поведение вместо реализации, юзер-центричные запросы getByRole + userEvent, renderWithProviders, мок на сетевой границе, async через findBy.
when_to_use: Триггеры — «тест для X», «как протестировать компонент/хук», «покрыть Y тестами». При написании/проектировании *.test.tsx, выборе что и как проверять.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend Test — проектирование (React + TS, Jest + Testing Library)

Ты проектируешь тесты по `frontend/fe-test/fe-test-rules.md` (`FE-TEST-*`). Часть трека `frontend` (карта —
`frontend/_index.md`). Backend-паттерны не применяй. Стек: `jest` + `ts-jest` (запуск
`jest --coverage`), `@testing-library/react` + `@testing-library/react-hooks`, `userEvent`.

## Инструкции

1. **Прочитай** `frontend/fe-test/fe-test-rules.md` (`FE-TEST-*`). Связанные: `fe-component` (тестируем вывод вью, не внутренности), `fe-state` (рендерим с реальным store, не мокаем slice), `fe-data-fetching` (мок на границе — fetcher/thunk), `fe-forms` (поля через лейблы/`userEvent`), `fe-a11y` (роли как точка доступа). Коды — в обосновании теста, не в коде.

2. **Определи, что тестировать** (`FE-TEST-1/2/3`): наблюдаемое поведение — что пользователь видит/делает (DOM, текст, навигация, наружные колбэки, результат запроса), не внутренний стейт/приватные функции. Перечисли значимые ветки: загрузка / успех / ошибка / пусто / запрет.

3. **Спроектируй запросы и взаимодействия** (`FE-TEST-4/5/6`): элементы — по роли/тексту/лейблу (`getByRole`/`getByText`/`getByLabelText`); `getByTestId` — только без доступной семантики; действия — через `userEvent` (`await userEvent.click/type`), не `fireEvent`.

4. **Окружение рендера** (`FE-TEST-7/8/9`): рендер через общий `renderWithProviders` (реальные Redux store + Router); мок — на сетевой границе (fetcher/thunk/HTTP), не на внутренних модулях; изоляция — свежий store и `clearAllMocks`/`cleanup` на каждый тест.

5. **Async и имена** (`FE-TEST-10/11`): появление/исчезновение элементов — `findBy*`/`waitFor`/`waitForElementToBeRemoved`, без `setTimeout`; имена по-русски — `describe('<Фича>')`, `test('должна <поведение>')`.

6. **Самопроверка** (чеклист §5) + предложи `ucp-fe-test-review`. Запросы/thunks — `ucp-fe-data-fetching-design`, формы — `ucp-fe-forms-design`, вью — `ucp-fe-component-design`.

## Антипаттерны, которые НЕ генерировать

- Проверка внутреннего стейта/инстанса/приватных функций вместо DOM (`FE-TEST-X1`); тотальный `toMatchSnapshot` вместо осмысленных assert'ов (`FE-TEST-X2`).
- Запрос по `className`/`getByTestId` там, где есть роль (`FE-TEST-X3`); привязка к порядку DOM/верстке (`FE-TEST-X4`).
- `jest.mock` на внутренние хуки/функции/селекторы компонента вместо границы (`FE-TEST-X5`); общий мутируемый store между тестами (`FE-TEST-X6`).
- `setTimeout`/`sleep` вместо `findBy`/`waitFor` (`FE-TEST-X7`); ручные `act`-обёртки/подавление warning'ов вместо `await findBy*`/`await userEvent` (`FE-TEST-X8`).

После работы скилла — обязательно `ucp-fe-test-review`.

$ARGUMENTS
