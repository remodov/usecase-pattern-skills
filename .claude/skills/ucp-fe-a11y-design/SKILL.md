---
name: ucp-fe-a11y-design
lang: any
track: frontend
description: Спроектировать доступность UI React+TS по UCP frontend-методологии (коды FE-A11Y-*) — семантика и компоненты @design-system/components вместо div, label и доступные ошибки полей, клавиатура и фокус в модалках, не-цветовые сигналы, точечные aria.
when_to_use: Триггеры — «доступность/a11y X», «aria для Y», «кнопка/модалка/форма доступна». При проектировании интерактива, форм, диалогов и сигналов состояния.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend A11y — проектирование (React + TS, @design-system/components)

Ты проектируешь доступность UI по `frontend/fe-a11y/fe-a11y-rules.md` (`FE-A11Y-*`). Часть трека `frontend`
(карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-a11y/fe-a11y-rules.md` (`FE-A11Y-*`). Связанные: `fe-component` (семантика вью, не div-суп), `fe-forms` (label и доступность ошибок поля), `fe-styling` (компоненты `@design-system/components` доступны из коробки). Коды — в обосновании, не в коде.

2. **Семантика и роли** (`FE-A11Y-1/2/3`): интерактив — через компоненты ДС/семантические элементы (`Button`, `Link`, `Tabs`), не `div`/`span` с `onClick` (`FE-A11Y-X1/X2`); страница — лендмарки (`nav`/`main`) и иерархия заголовков; иконочной кнопке — доступное имя.

3. **Формы и подписи** (`FE-A11Y-4/5/6`): каждое поле — связанный `label` (проп `label` у `Input`/`Select` ДС или `htmlFor`↔`id`, не `placeholder`); ошибки — через проп `error` ДС / `aria-describedby` + `aria-invalid`; группы — `fieldset`/`legend`. Детали — `ucp-fe-forms-design`.

4. **Клавиатура и фокус** (`FE-A11Y-7/8/9`): весь интерактив управляем с клавиатуры (Tab/Enter/Esc), порядок = визуальному; диалоги — `Modal` ДС с focus trap, Esc и возвратом фокуса на триггер; видимый `focus-outline` не убирай без замены (`FE-A11Y-X5/X6`).

5. **Цвет и aria** (`FE-A11Y-10/11/12`): состояние — не только цветом (`Status`/`Badge` ДС с текстом, `FE-A11Y-X7`); значимые иконки/картинки — с доступным именем, декоративные — скрыты (`FE-A11Y-X8`); `aria-*` — точечно, без дублирования нативной роли (`FE-A11Y-X9`).

6. **Самопроверка** (чеклист §5) + предложи `ucp-fe-a11y-review`. Вью/семантика — `ucp-fe-component-design`, формы — `ucp-fe-forms-design`, ДС-стили — `ucp-fe-styling-design`.

## Антипаттерны, которые НЕ генерировать

- `div`/`span` с `onClick` вместо `Button`/`Link` (`FE-A11Y-X1`); кастомный select/tabs/checkbox из `div` вместо компонента ДС (`FE-A11Y-X2`).
- Поле без связанного label (только `placeholder`) (`FE-A11Y-X3`); ошибка не связана с полем (`FE-A11Y-X4`).
- Снятие `outline` без видимой замены (`FE-A11Y-X5`); положительный `tabindex`, ломающий порядок (`FE-A11Y-X6`).
- Сигнал состояния только цветом (`FE-A11Y-X7`); значимая иконка без имени / декоративная озвучивается (`FE-A11Y-X8`); избыточные aria поверх нативной роли (`FE-A11Y-X9`).

После работы скилла — обязательно `ucp-fe-a11y-review`.

$ARGUMENTS
