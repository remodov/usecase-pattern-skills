---
name: ucp-fe-a11y-review
lang: any
track: frontend
description: Ревью доступности UI React+TS по UCP frontend-методологии (коды FE-A11Y-*) — семантика вместо div-as-button, label и доступные ошибки полей, клавиатура и фокус в модалках, не-цветовые сигналы состояния, точечные aria поверх @design-system/components.
when_to_use: Изменения в JSX/TSX интерактиве, формах, модалках, стилях фокуса (*.tsx); ревью семантики, клавиатуры, aria и цветовых сигналов.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend A11y (React + TS, @design-system/components)

Ты ревьюишь доступность UI на соответствие `frontend/fe-a11y/fe-a11y-rules.md` (`FE-A11Y-*`).

## Зависимости

- **`.claude/docs/frontend/fe-a11y/fe-a11y-rules.md`** (`FE-A11Y-*`).
- Парные: `fe-component` (семантика вью), `fe-forms` (label/ошибки), `fe-styling` (доступность компонентов ДС).

## Инструкции

1. **Прочти** `fe-a11y-rules.md`. Цитируй конкретные коды (`FE-A11Y-X1`), не префикс.

2. **Скоп.** `*.tsx`/`*.jsx`, разметка интерактива, формы, модалки/оверлеи, стили фокуса (`outline`, `:focus`); `git diff` на этих файлах.

3. **Прогон.**
   - **Семантика и роли (`FE-A11Y-1/2/3`):** `div`/`span` с `onClick` вместо `Button`/`Link` → `FE-A11Y-X1`; кастомный select/tabs/checkbox из `div` вместо компонента ДС → `FE-A11Y-X2`; иконочная кнопка без доступного имени → нарушение `FE-A11Y-3`; отсутствие лендмарок/скачки заголовков → `FE-A11Y-2`.
   - **Формы (`FE-A11Y-4/5/6`):** поле без связанного label (только `placeholder`) → `FE-A11Y-X3`; ошибка не связана с полем (нет `error`-пропа ДС / `aria-describedby` / `aria-invalid`) → `FE-A11Y-X4`.
   - **Клавиатура и фокус (`FE-A11Y-7/8/9`):** интерактив недостижим с клавиатуры; модалка без trap/Esc/возврата фокуса (самодельный оверлей вместо `Modal` ДС) → нарушение `FE-A11Y-8`; `outline: none` без видимой замены → `FE-A11Y-X5`; положительный `tabindex` → `FE-A11Y-X6`.
   - **Цвет и aria (`FE-A11Y-10/11/12`):** состояние только цветом → `FE-A11Y-X7`; значимая иконка/картинка без имени или декоративная без `aria-hidden`/`alt=""` → `FE-A11Y-X8`; избыточные/неверные `aria` поверх нативной роли → `FE-A11Y-X9`.

4. **Cross-check:** семантика вью — `ucp-fe-component-review`; label/ошибки форм — `ucp-fe-forms-review`; ДС-стили — `ucp-fe-styling-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `div`-as-button без роли/клавиатуры (`FE-A11Y-X1`), поле без label (`FE-A11Y-X3`), модалка без управления фокусом, состояние только цветом для значимого сигнала (`FE-A11Y-X7`).
   - **Предупреждение** — кастомный интерактив вместо ДС (`FE-A11Y-X2`), ошибка не связана с полем (`FE-A11Y-X4`), снятие focus-outline без замены (`FE-A11Y-X5`), значимая иконка без имени (`FE-A11Y-X8`).
   - **Замечание** — положительный `tabindex` (`FE-A11Y-X6`), избыточные aria поверх нативной роли (`FE-A11Y-X9`), мелкие скачки иерархии заголовков.

## Что не входит

- Архитектура вью/props — `ucp-fe-component-review`. Логика валидации/состояние формы — `ucp-fe-forms-review`. Токены/верстка ДС — `ucp-fe-styling-review`.

$ARGUMENTS
