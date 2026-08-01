---
name: ucp-fe-styling-review
lang: any
track: frontend
description: Ревью стилизации React+TS на дизайн-системе @design-system/components по UCP frontend-методологии (коды FE-STY-*) — примитивы ДС вместо сырого html, deep-import по компоненту, токены вместо магических hex/px, layout в CSS-модулях.
when_to_use: Изменения в верстке/стилях (*.tsx с html-тегами, *.module.css, импорты @design-system/*); ревью выбора примитивов, импортов и оформления.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Styling (React + TS, @design-system/components)

Ты ревьюишь стилизацию и верстку на соответствие `frontend/fe-styling/fe-styling-rules.md` (`FE-STY-*`).

## Зависимости

- **`.claude/docs/frontend/fe-styling/fe-styling-rules.md`** (`FE-STY-*`).
- Парные: `fe-component` (примитивы в ui-слое), `fe-a11y` (доступность компонентов ДС).

## Инструкции

1. **Прочти** `fe-styling-rules.md`. Цитируй конкретные коды (`FE-STY-X3`), не префикс.

2. **Скоп.** `*.tsx`/`*.jsx` с сырыми html-тегами, `*.module.css`, инлайн-`style`, импорты `@design-system/components` и `@design-system/icons`; `git diff` на этих файлах.

3. **Прогон.**
   - **Примитивы (`FE-STY-1/2/3`):** сырой `<button>`/`<input>`/`<select>`/`<h1>`/`<table>` при наличии аналога в ДС → `FE-STY-X1`; самодельный дубль компонента ДС → `FE-STY-X2`; текст не через `Typography`, раскладка не через `Grid`.
   - **Импорты (`FE-STY-4/5`):** `import {…} from '@design-system/components'` (пакет целиком) → `FE-STY-X3`; barrel-реэкспорт всей ДС → `FE-STY-X4`; вместо deep-import по компоненту/иконке.
   - **Токены (`FE-STY-6/7/8`):** хардкод-цвет (`#11A0FF`) или размер (`13px`) вместо токена/пропа → `FE-STY-X5`; `!important`/селекторы по внутренним классам ДС → `FE-STY-X6`; вид/состояние перекрытием стилей вместо пропов.
   - **CSS-модули (`FE-STY-9/10`):** инлайн-`style` с константой оформления вместо CSS-модуля → `FE-STY-X7`; глобальные несколь-скоупленные стили (вне `*.module.css`) → `FE-STY-X8`; презентационные имена классов вместо доменных.

4. **Cross-check:** примитивы/композиция — `ucp-fe-component-review`; доступность — `ucp-fe-a11y-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — импорт ДС целиком/barrel (`FE-STY-X3/X4`, ломает бандл), `!important` по внутренним классам ДС (`FE-STY-X6`).
   - **Предупреждение** — сырой html при наличии аналога ДС (`FE-STY-X1`), дубль компонента ДС (`FE-STY-X2`), хардкод hex/px вместо токена (`FE-STY-X5`), инлайн-константа оформления (`FE-STY-X7`), глобальные протекающие стили (`FE-STY-X8`).
   - **Замечание** — текст не через `Typography`/раскладка не через `Grid`, презентационные имена CSS-классов.

## Что не входит

- Разделение вью/контейнер и props — `ucp-fe-component-review`. Семантика/ARIA — `ucp-fe-a11y-review`. Состояние — `ucp-fe-state-review`.

$ARGUMENTS
