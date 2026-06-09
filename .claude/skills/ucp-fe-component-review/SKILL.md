---
name: ucp-fe-component-review
lang: any
track: frontend
description: Ревью React+TS-компонента по UCP frontend-методологии (коды FE-CMP-*) — презентационный/контейнерный split, типизированные доменные props без any, композиция через children, точечная мемоизация, честный useEffect.
when_to_use: Изменения в *.tsx/*.jsx-компонентах и их props-типах; ревью UI-кода.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Components (React + TypeScript)

Ты ревьюишь React+TS-компонент на соответствие `frontend/fe-component/fe-component-rules.md` (`FE-CMP-*`).

## Зависимости

- **`.claude/docs/frontend/fe-component/fe-component-rules.md`** (`FE-CMP-*`).
- Парные: `fe-data-fetching`, `fe-state`, `fe-a11y`, `fe-test` (когда наполнятся).

## Инструкции

1. **Прочти** `fe-component-rules.md`. Цитируй конкретные коды (`FE-CMP-X1`), не префикс.

2. **Скоп.** `*.tsx`/`*.jsx`-компоненты, их props-типы; `git diff` на фронт-файлах.

3. **Прогон.**
   - **Разделение (`FE-CMP-1/2/3`):** вью отделено от контейнера? `fetch`/API в презентационном → `FE-CMP-X1`; бизнес-логика в JSX → `FE-CMP-X2`.
   - **Props (`FE-CMP-4/5`):** типизированы, доменные, без `any` (`FE-CMP-X3`); не мутируются (`FE-CMP-X4`); prop-drilling 3+ уровней → в контекст/стор.
   - **Композиция (`FE-CMP-6/7`):** `children`/слоты, не флаги-режимы (god-компонент → `FE-CMP-X5`); примитивы из дизайн-системы.
   - **Перформанс/эффекты (`FE-CMP-8/9`):** мемоизация точечная (превентивная тотальная → `FE-CMP-X7`); `useEffect` только для синхронизации с внешним миром (вывод стейта из пропсов → `FE-CMP-X6`); зависимости честные.

4. **Cross-check:** запросы — `ucp-fe-data-fetching-review`; состояние — `ucp-fe-state-review`; доступность — `ucp-fe-a11y-review`; тест — `ucp-fe-test-review` (когда наполнятся).

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `fetch`/API в презентационном (`FE-CMP-X1`), `any` в props (`FE-CMP-X3`), мутация props (`FE-CMP-X4`), бизнес-правила в JSX (`FE-CMP-X2`).
   - **Предупреждение** — god-компонент с флагами (`FE-CMP-X5`), `useEffect` для вывода стейта (`FE-CMP-X6`), prop-drilling 3+.
   - **Замечание** — превентивная мемоизация (`FE-CMP-X7`), не-доменные широкие props, компонент >150 строк.

## Что не входит

- Запросы к API — `ucp-fe-data-fetching-review`. Состояние/стор — `ucp-fe-state-review`. Стили/дизайн-система — `ucp-fe-styling-review`. Тесты — `ucp-fe-test-review`.

$ARGUMENTS
