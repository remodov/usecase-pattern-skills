---
name: ucp-fe-style-review
lang: any
track: frontend
description: Ревью code style React+TS по UCP frontend-методологии (коды FE-STYLE-*) — eslint/prettier (общий пресет проекта, simple-import-sort) чисто, strict tsconfig без any, отсортированные импорты, отсутствие немых подавлений и console.log/debugger.
when_to_use: Изменения в *.ts/*.tsx/*.css (любой фронтовый diff); ревью соответствия eslint/prettier/tsconfig перед коммитом/merge.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью Frontend Code Style (React + TS, ESLint + Prettier + tsconfig)

Ты ревьюишь code style на соответствие `frontend/fe-style/fe-style-rules.md` (`FE-STYLE-*`).

## Зависимости

- **`.claude/docs/frontend/fe-style/fe-style-rules.md`** (`FE-STYLE-*`).
- Парные: `fe-component`, `fe-state` (тот же код-стиль трека применяется к компонентам и стору).

## Инструкции

1. **Прочти** `fe-style-rules.md`. Цитируй конкретные коды (`FE-STYLE-X2`), не префикс.

2. **Скоп.** `*.ts`, `*.tsx`, `*.css`; `git diff` на этих файлах. Стиль ревьюишь по diff, а вердикт по чистоте
   линта/формата подкрепляй правилами (запуск `yarn lint`/`yarn format` — вне allowed-tools, опирайся на чтение).

3. **Прогон.**
   - **Линтер/форматтер (`FE-STYLE-1/2/3`):** ручное форматирование вразрез с Prettier → `FE-STYLE-X1`; следы
     того, что `yarn lint` не прогонялся (видимые нарушения правил пресета).
   - **Типы (`FE-STYLE-4/5/6`):** `any`/`as any` вместо типа → `FE-STYLE-X2`; ослабление strict в `tsconfig`
     под файл; `@ts-ignore`/`@ts-expect-error` без причины и тикета рядом → `FE-STYLE-X3`.
   - **Импорты/именование (`FE-STYLE-7/8/9`):** неиспользуемые импорты/переменные → `FE-STYLE-X4`; перемешанный
     порядок импортов вразрез с `simple-import-sort` → `FE-STYLE-X5`; рассогласованное именование
     (`camelCase`/`PascalCase`/`UPPER_SNAKE_CASE`), имя файла ≠ имя компонента.
   - **Подавления/мусор (`FE-STYLE-10/11`):** `eslint-disable` (особенно на файл) без обоснования рядом →
     `FE-STYLE-X6`; `console.log`/`debugger`/мёртвый закомментированный код → `FE-STYLE-X7`.

4. **Cross-check:** рендер/props — `ucp-fe-component-review`; стор/slice — `ucp-fe-state-review`.

5. **Формат findings** — `.claude/docs/shared/review-finding-format.md` (`RFF-*`), Read-проверка строки обязательна.

6. **Серьёзность** (`RFF-12`):
   - **Критично** — `any`/`as any` вместо типа (`FE-STYLE-X2`), `@ts-ignore`/`@ts-expect-error` без причины и
     тикета (`FE-STYLE-X3`), `eslint-disable` без обоснования (`FE-STYLE-X6`), `console.log`/`debugger` в коммите
     (`FE-STYLE-X7`).
   - **Предупреждение** — неиспользуемые импорты/переменные (`FE-STYLE-X4`), рассогласованное именование,
     ослабление strict под файл.
   - **Замечание** — перемешанный порядок импортов (`FE-STYLE-X5`), ручное форматирование вразрез с Prettier
     (`FE-STYLE-X1`) — чинится автофиксом.

## Что не входит

- Архитектура компонентов/props — `ucp-fe-component-review`. Форма стора/селекторы — `ucp-fe-state-review`.
  Логика тестов — `ucp-fe-test-review`.

$ARGUMENTS
