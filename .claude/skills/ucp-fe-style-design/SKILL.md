---
name: ucp-fe-style-design
lang: any
track: frontend
description: Привести код React+TS к стилю по UCP frontend-методологии (коды FE-STYLE-*) — прогнать eslint/prettier (общий пресет проекта, simple-import-sort), убрать any под strict tsconfig, отсортировать импорты, снять немые подавления и console.log/debugger.
when_to_use: Триггеры — «почини линт», «убери any», «отформатируй/нормализуй стиль». Перед коммитом фронтового кода, при приведении файла к eslint/prettier/tsconfig.
allowed-tools: Read Glob Grep Write Edit Bash(npm*) Bash(pnpm*) Bash(npx*) Bash(yarn*)
---

# Frontend Code Style — нормализация (React + TS, ESLint + Prettier + tsconfig)

Ты приводишь код к стилю по `frontend/fe-style/fe-style-rules.md` (`FE-STYLE-*`). Часть трека `frontend`
(карта — `frontend/_index.md`). Backend-паттерны не применяй. Коды — в обосновании правок, не в коде.

## Инструкции

1. **Прочитай** `frontend/fe-style/fe-style-rules.md` (`FE-STYLE-*`). Связанные: `fe-component`, `fe-state` —
   тот же код-стиль применяется к компонентам и стору (одни правила линта/типов).

2. **Линтер/форматтер — источник правды** (`FE-STYLE-1/2/3`): прогони `yarn lint` (`lint:scripts` + `lint:css`)
   и `yarn format` (Prettier); чини то, что показал линтер. Форматирование не правь руками вразрез с Prettier
   (`FE-STYLE-X1`) — дай отработать автофиксу.

3. **Типобезопасность** (`FE-STYLE-4/5/6`): не ослабляй strict в `tsconfig`; убери `any` — `unknown` + сужение
   (type guard), дженерики, доменные `type`/`interface`; внешние данные типизируй (`FE-STYLE-X2`). `@ts-ignore`/
   `@ts-expect-error` — только с причиной и тикетом рядом, предпочти `@ts-expect-error` (`FE-STYLE-X3`).

4. **Импорты и именование** (`FE-STYLE-7/8/9`): импорты отсортируй автофиксом `simple-import-sort`
   (`FE-STYLE-X5`), не руками; удали неиспользуемые импорты/переменные (`FE-STYLE-X4`); именование —
   `camelCase`/`PascalCase`/`UPPER_SNAKE_CASE`, имя файла = имя компонента.

5. **Подавления и мусор** (`FE-STYLE-10/11`): `eslint-disable` — точечно, `disable-next-line` с обоснованием
   рядом, не на файл/конфиг (`FE-STYLE-X6`); убери `console.log`/`debugger` и мёртвый код (`FE-STYLE-X7`).

6. **Самопроверка** (чеклист §5): финальный `yarn lint` зелёный, `yarn format` без правок. Затем предложи
   `ucp-fe-style-review`. Рендер/props — `ucp-fe-component-design`; стор/slice — `ucp-fe-state-design`.

## Антипаттерны, которые НЕ генерировать

- Ручное форматирование вразрез с Prettier (`FE-STYLE-X1`).
- `any`/`as any` вместо типа (`FE-STYLE-X2`); `@ts-ignore`/`@ts-expect-error` без причины и тикета (`FE-STYLE-X3`).
- Неиспользуемые импорты/переменные (`FE-STYLE-X4`); перемешанный порядок импортов вразрез с `simple-import-sort`
  (`FE-STYLE-X5`).
- `eslint-disable` без обоснования рядом (`FE-STYLE-X6`); `console.log`/`debugger` и мёртвый код в коммите
  (`FE-STYLE-X7`).

После работы скилла — обязательно `ucp-fe-style-review`.

$ARGUMENTS
