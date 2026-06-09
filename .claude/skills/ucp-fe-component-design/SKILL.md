---
name: ucp-fe-component-design
lang: any
track: frontend
description: Спроектировать React+TS-компонент по UCP frontend-методологии (коды FE-CMP-*) — презентационный/контейнерный split, типизированные доменные props без any, композиция через children, данные и логика вне вью, точечная мемоизация.
when_to_use: Триггеры — «компонент X», «UI для Y», «React-компонент». При создании нового компонента или UI-блока.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*)
---

# Frontend Components — проектирование (React + TypeScript)

Ты проектируешь React+TS-компонент по `frontend/fe-component/fe-component-rules.md` (`FE-CMP-*`). Это часть
трека `frontend` (карта — `frontend/_index.md`). Backend-паттерны не применяй.

## Инструкции

1. **Прочитай** `frontend/fe-component/fe-component-rules.md` (`FE-CMP-*`). Связанные: `fe-data-fetching` (запросы), `fe-state` (состояние), `fe-a11y` (семантика), `fe-test` (тест). Коды в обосновании, не в JSX-комментариях.

2. **Реши слой:** презентационный (как выглядит, данные через props) или контейнерный (откуда данные/логика). Не смешивай (`FE-CMP-1/2`).

3. **Произведи компонент** (React+TS, без `any`):
   - Типизированные **доменные** props (`type`/`interface`), обязательные/опциональные через тип, props иммутабельны (`FE-CMP-4/5`, `FE-CMP-X3/X4`).
   - Данные/запросы — **вне вью**: через хук `fe-data-fetching`; состояние — `fe-state`. Бизнес-логику — в хуки/утилиты, не в JSX (`FE-CMP-2`, `FE-CMP-X1/X2`).
   - Композиция через `children`/слоты, не булевы флаги-режимы (`FE-CMP-6`, `FE-CMP-X5`); UI-примитивы — из дизайн-системы (`fe-styling`).
   - Мемоизация и `useEffect` — точечно по факту; деривативные данные считать при рендере (`FE-CMP-8/9`, `FE-CMP-X6/X7`).

4. **Самопроверка** (чеклист §5) + предложи `ucp-fe-component-review`. Запросы — `ucp-fe-data-fetching-design`, состояние — `ucp-fe-state-design`, тест — `ucp-fe-test-design` (когда наполнятся).

## Антипаттерны, которые НЕ генерировать

- `fetch`/API в презентационном компоненте (`FE-CMP-X1`); бизнес-правила в JSX (`FE-CMP-X2`); `any`/`object` в props (`FE-CMP-X3`); мутация props (`FE-CMP-X4`).
- God-компонент с флагами-режимами вместо композиции (`FE-CMP-X5`); `useEffect` для вывода стейта из пропсов (`FE-CMP-X6`); тотальная превентивная мемоизация (`FE-CMP-X7`).

После работы скилла — обязательно `ucp-fe-component-review`.

$ARGUMENTS
