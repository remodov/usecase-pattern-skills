---
name: ucp-fe-styling-design
lang: any
track: frontend
description: Спроектировать стилизацию React+TS на дизайн-системе @design-system/components по UCP frontend-методологии (коды FE-STY-*) — примитивы ДС вместо сырого html, deep-import по компоненту, токены вместо магических hex/px, layout в CSS-модулях.
when_to_use: Триггеры — «свёрстать/стилизовать X», «кнопка/инпут/таблица/раскладка», «какой компонент ДС взять». При выборе примитивов, импортов и оформления.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend Styling — проектирование (React + TS, @design-system/components)

Ты проектируешь стилизацию и верстку по `frontend/fe-styling/fe-styling-rules.md` (`FE-STY-*`). Часть трека
`frontend` (карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-styling/fe-styling-rules.md` (`FE-STY-*`). Связанные: `fe-component` (переиспользуемые примитивы — в ui-слой, не во вью), `fe-a11y` (компоненты ДС доступны по умолчанию — не ломай их разметку). Коды — в обосновании, не в коде.

2. **Возьми примитивы из ДС** (`FE-STY-1/2/3`): где есть аналог в `@design-system/components` — используй его (`Button`/`Input`/`Select`/`Table`), не сырой html; текст — `Typography` (Title/Text); раскладка — `Grid`. Не верстай руками то, что уже есть в ДС (`FE-STY-X1`), не переизобретай компонент (`FE-STY-X2`).

3. **Импорты** (`FE-STY-4/5`): deep-import конкретного компонента (`@design-system/components/button`) и иконки по имени (`@design-system/icons`). Не импортируй пакет целиком и не делай barrel всей ДС (`FE-STY-X3/X4`) — бандл и tree-shaking.

4. **Токены и пропы** (`FE-STY-6/7/8`): цвета/отступы/шрифты — из токенов ДС (CSS-переменные) и пропов компонента (`view`, `size`, `block`); вид/состояние — через пропы, не перекрытием стилей. Никаких магических hex/px (`FE-STY-X5`) и `!important` по внутренним классам ДС (`FE-STY-X6`).

5. **Layout** (`FE-STY-9/10`): оформление — в CSS-модулях (`*.module.css`) с доменными именами классов; инлайн-`style` — только для динамических значений (рантайм), не для констант (`FE-STY-X7`); без глобальных протекающих стилей (`FE-STY-X8`).

6. **Самопроверка** (чеклист §5) + предложи `ucp-fe-styling-review`. Примитивы/композиция — `ucp-fe-component-design`, доступность — `ucp-fe-a11y-design`.

## Антипаттерны, которые НЕ генерировать

- Сырой `<button>`/`<input>`/`<h1>`/`<table>` при наличии аналога в ДС (`FE-STY-X1`); самодельный дубль компонента ДС (`FE-STY-X2`).
- Импорт `@design-system/components` целиком или barrel всей ДС (`FE-STY-X3/X4`).
- Хардкод-цвет/размер вместо токена (`FE-STY-X5`); `!important`/правка внутренних классов ДС (`FE-STY-X6`).
- Инлайн-`style` с константой оформления вместо CSS-модуля (`FE-STY-X7`); глобальные несколь-скоупленные стили (`FE-STY-X8`).

После работы скилла — обязательно `ucp-fe-styling-review`.

$ARGUMENTS
